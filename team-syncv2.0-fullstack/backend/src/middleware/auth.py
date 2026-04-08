from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_db_session
from src.models import AppSession, AuthSession, User
from src.security import hash_session_token


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def require_current_user(
    session_token: Optional[str] = Cookie(default=None, alias=settings.auth_cookie_name),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    hashed_token = hash_session_token(session_token)
    result = await db.execute(
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(AuthSession.token_hash == hashed_token)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    session_result = await db.execute(
        select(AuthSession).where(AuthSession.token_hash == hashed_token)
    )
    auth_session = session_result.scalar_one_or_none()
    if not auth_session or _as_utc(auth_session.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
        )

    auth_session.last_seen_at = datetime.now(timezone.utc)
    await db.commit()
    return user


async def require_session_owner(
    session_id: str,
    current_user: User,
    db: AsyncSession,
) -> AppSession:
    result = await db.execute(select(AppSession).where(AppSession.session_id == session_id))
    app_session = result.scalar_one_or_none()
    if not app_session or app_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )
    return app_session
