from __future__ import annotations

from datetime import datetime, timezone
import secrets
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_db_session
from src.middleware.auth import require_current_user
from src.models import AuthSession, User
from src.security import (
    auth_session_expiry,
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_GOOGLE_LOGIN_SCOPES = "openid email profile"


class SignupRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)


class CurrentUserResponse(BaseModel):
    id: int
    email: str
    display_name: str


def _set_google_state_cookie(response: Response, state: str) -> None:
    response.set_cookie(
        key=settings.google_oauth_state_cookie_name,
        value=state,
        max_age=10 * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )


def _clear_google_state_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.google_oauth_state_cookie_name,
        path="/",
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
    )


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_session_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
    )


def _to_user_response(user: User) -> CurrentUserResponse:
    return CurrentUserResponse(id=user.id, email=user.email, display_name=user.display_name)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def _create_auth_session(
    db: AsyncSession,
    user: User,
    response: Response,
) -> CurrentUserResponse:
    raw_token = generate_session_token()
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_session_token(raw_token),
            expires_at=auth_session_expiry(),
        )
    )
    await db.commit()
    _set_auth_cookie(response, raw_token)
    return _to_user_response(user)


def _google_callback_url(request: Request) -> str:
    return str(request.url_for("google_login_callback"))


def _frontend_auth_redirect(path: str, error: Optional[str] = None) -> str:
    base = settings.frontend_url.rstrip("/")
    target = f"{base}{path}"
    if error:
        return f"{target}?{urlencode({'auth_error': error})}"
    return target


async def _find_or_create_google_user(
    db: AsyncSession,
    email: str,
    display_name: str,
) -> User:
    normalized_email = email.lower().strip()
    result = await db.execute(select(User).where(User.email == normalized_email))
    user = result.scalar_one_or_none()
    if user:
        if not user.display_name.strip() and display_name.strip():
            user.display_name = display_name.strip()
            await db.commit()
        return user

    user = User(
        email=normalized_email,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        display_name=display_name.strip() or normalized_email.split("@", 1)[0],
    )
    db.add(user)
    await db.flush()
    return user


@router.post("/signup", response_model=CurrentUserResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> CurrentUserResponse:
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        display_name=body.display_name.strip(),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )
    return await _create_auth_session(db, user, response)


@router.post("/login", response_model=CurrentUserResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> CurrentUserResponse:
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    return await _create_auth_session(db, user, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    result = await db.execute(
        select(AuthSession).where(AuthSession.user_id == current_user.id)
    )
    sessions = result.scalars().all()
    now = datetime.now(timezone.utc)
    for auth_session in sessions:
        if _as_utc(auth_session.expires_at) > now:
            await db.delete(auth_session)
    await db.commit()
    _clear_auth_cookie(response)
    return response


@router.get("/me", response_model=CurrentUserResponse)
async def me(current_user: User = Depends(require_current_user)) -> CurrentUserResponse:
    return _to_user_response(current_user)


@router.get("/google/login")
async def google_login(request: Request) -> RedirectResponse:
    if not settings.google_login_client_id or not settings.google_login_client_secret:
        return RedirectResponse(
            url=_frontend_auth_redirect("/login", "Google login is not configured."),
            status_code=status.HTTP_302_FOUND,
        )

    state = secrets.token_urlsafe(24)
    params = {
        "client_id": settings.google_login_client_id,
        "redirect_uri": _google_callback_url(request),
        "response_type": "code",
        "scope": _GOOGLE_LOGIN_SCOPES,
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    response = RedirectResponse(
        url=f"{_GOOGLE_AUTH_URL}?{urlencode(params)}",
        status_code=status.HTTP_302_FOUND,
    )
    _set_google_state_cookie(response, state)
    return response


@router.get("/google/callback", name="google_login_callback")
async def google_login_callback(
    request: Request,
    code: Optional[str] = Query(default=None),
    state: str = Query(...),
    error: Optional[str] = Query(default=None),
    stored_state: Optional[str] = Cookie(default=None, alias=settings.google_oauth_state_cookie_name),
    db: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    def error_redirect(message: str) -> RedirectResponse:
        redirect = RedirectResponse(
            url=_frontend_auth_redirect("/login", message),
            status_code=status.HTTP_302_FOUND,
        )
        _clear_google_state_cookie(redirect)
        return redirect

    if not stored_state or stored_state != state:
        return error_redirect("Google login state validation failed.")

    if error or not code:
        return error_redirect(error or "Google login was cancelled.")

    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_login_client_id,
                    "client_secret": settings.google_login_client_secret,
                    "redirect_uri": _google_callback_url(request),
                    "grant_type": "authorization_code",
                },
                timeout=15,
            )
            token_response.raise_for_status()
            tokens = token_response.json()

            profile_response = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                timeout=10,
            )
            profile_response.raise_for_status()
            profile = profile_response.json()
    except Exception:
        return error_redirect("Unable to complete Google login.")

    if not profile.get("email") or not profile.get("email_verified"):
        return error_redirect("Google account email is not verified.")

    user = await _find_or_create_google_user(
        db,
        email=profile["email"],
        display_name=profile.get("name", ""),
    )

    redirect_response = RedirectResponse(
        url=_frontend_auth_redirect("/"),
        status_code=status.HTTP_302_FOUND,
    )
    await _create_auth_session(db, user, redirect_response)
    _clear_google_state_cookie(redirect_response)
    return redirect_response
