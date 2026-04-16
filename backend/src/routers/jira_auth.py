from __future__ import annotations

"""
JIRA OAuth 2.0 — Atlassian 3-legged OAuth flow.

Endpoints:
  GET /api/v1/jira/auth/connect?session_id={id}
      Returns the Atlassian authorization URL. Frontend opens this in a new tab.

  GET /api/v1/jira/auth/callback?code=...&state={session_id}
      Atlassian redirects here after user grants permission.
      Exchanges code for tokens, resolves cloud instance, stores in token store.
      Returns a small HTML page the tab can close itself.

  GET /api/v1/jira/auth/status?session_id={id}
      Returns {connected, user_name, cloud_name} — frontend polls this after
      the OAuth tab closes to confirm the connection succeeded.

  DELETE /api/v1/jira/auth/disconnect?session_id={id}
      Clears stored token for this session.

Setup (one-time, done by the team admin):
  1. https://developer.atlassian.com/console/myapps/ → Create app → OAuth 2.0
  2. Add callback URL: http://localhost:8000/api/v1/jira/auth/callback
  3. Scopes: read:jira-work  write:jira-work  offline_access
  4. Copy Client ID + Secret → ATLASSIAN_CLIENT_ID / ATLASSIAN_CLIENT_SECRET in .env
"""
import logging
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_db_session
from src.middleware.auth import require_current_user, require_session_owner
from src.models import User
from src.services.jira import JiraService
from src.services.oauth_connections import (
    delete_oauth_connection,
    get_oauth_connection,
    upsert_oauth_connection,
)

router = APIRouter(prefix="/api/v1/jira/auth", tags=["JIRA Auth"])
logger = logging.getLogger(__name__)

# ── Atlassian OAuth constants ─────────────────────────────────────────────────

_AUTH_URL      = "https://auth.atlassian.com/authorize"
_TOKEN_URL     = "https://auth.atlassian.com/oauth/token"
_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"
_SCOPES        = "read:jira-work write:jira-work read:jira-user read:me offline_access"


def _public_jira_base_url(fallback_url: Optional[str]) -> Optional[str]:
    """
    Prefer the configured public Jira base URL so self-hosted context paths like `/jira`
    are preserved in UI links.
    """
    configured = settings.jira_base_url.strip().rstrip("/")
    if configured:
        return configured
    if fallback_url:
        return fallback_url.rstrip("/")
    return None

# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/connect")
async def connect(
    request: Request,
    session_id: str = Query(..., description="LangGraph session / thread ID"),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Return the Atlassian OAuth URL for this session.
    Frontend opens it in a new tab or popup.
    """
    await require_session_owner(session_id, current_user, db)
    if not settings.atlassian_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="ATLASSIAN_CLIENT_ID not configured. See .env.example.",
        )

    callback = f"{settings.backend_url.rstrip('/')}/api/v1/jira/auth/callback"
    params = {
        "audience":      "api.atlassian.com",
        "client_id":     settings.atlassian_client_id,
        "scope":         _SCOPES,
        "redirect_uri":  callback,
        "state":         session_id,          # carries session_id through the flow
        "response_type": "code",
        "prompt":        "consent",
    }
    url = _AUTH_URL + "?" + urlencode(params)
    return {"url": url, "session_id": session_id}


@router.get("/callback", name="jira_oauth_callback", include_in_schema=False)
async def callback(
    request: Request,
    code: Optional[str] = Query(default=None),   # absent when Atlassian returns an error
    state: str = Query(...),     # session_id  OR  "user:{user_id}" for tab-level connect
    error: Optional[str] = Query(default=None),
    error_description: Optional[str] = Query(default=None),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    """
    Atlassian redirects here after the user grants (or denies) permission.
    Exchanges auth code for tokens, fetches cloud instance info, stores both.
    Returns a self-closing HTML page — the OAuth tab closes itself.
    """
    # state is either a LangGraph session_id or "user:{id}" from the JIRA tab
    if state.startswith("user:"):
        # Verify the state user matches the cookie-authenticated user to prevent
        # one user's OAuth flow from overwriting another user's tokens.
        try:
            state_user_id = int(state.split(":", 1)[1])
        except (ValueError, IndexError):
            state_user_id = -1
        if state_user_id != current_user.id:
            logger.warning(
                "JIRA OAuth state user %s does not match authenticated user %s — rejecting",
                state_user_id, current_user.id,
            )
            return _close_tab_html(success=False, message="JIRA connection failed: session mismatch.")
    else:
        await require_session_owner(state, current_user, db)
    if error:
        logger.warning("JIRA OAuth error for session %s: %s — %s", state, error, error_description)
        return _close_tab_html(
            success=False,
            message=f"JIRA connection failed: {error_description or error}",
        )

    if not code:
        logger.warning("JIRA OAuth callback for session %s: no code and no error", state)
        return _close_tab_html(success=False, message="JIRA connection failed: no authorisation code received.")

    callback_url = f"{settings.backend_url.rstrip('/')}/api/v1/jira/auth/callback"

    try:
        async with httpx.AsyncClient() as client:
            # 1. Exchange auth code for access + refresh tokens
            token_resp = await client.post(
                _TOKEN_URL,
                json={
                    "grant_type":    "authorization_code",
                    "client_id":     settings.atlassian_client_id,
                    "client_secret": settings.atlassian_client_secret,
                    "code":          code,
                    "redirect_uri":  callback_url,
                },
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            token_resp.raise_for_status()
            tokens = token_resp.json()
            access_token  = tokens["access_token"]
            refresh_token = tokens.get("refresh_token", "")

            # 2. Resolve the Atlassian cloud instance (first accessible resource)
            resources_resp = await client.get(
                _RESOURCES_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            resources_resp.raise_for_status()
            resources = resources_resp.json()
            if not resources:
                raise ValueError("No accessible Atlassian sites found for this account")

            cloud = resources[0]   # use first site; could let user choose in future

            # 3. Fetch the user's own profile for display name / email.
            # Non-fatal — if read:me scope is missing the token is still stored.
            me: dict = {}
            for profile_url in [
                "https://api.atlassian.com/me",
                f"https://api.atlassian.com/ex/jira/{cloud['id']}/rest/api/3/myself",
            ]:
                try:
                    me_resp = await client.get(
                        profile_url,
                        headers={"Authorization": f"Bearer {access_token}"},
                        timeout=10,
                    )
                    if me_resp.is_success:
                        me = me_resp.json()
                        break
                except Exception:
                    pass

    except Exception as exc:
        logger.exception("JIRA OAuth callback failed for user %s: %s", current_user.id, exc)
        return _close_tab_html(success=False, message=f"Connection failed: {exc}")

    await upsert_oauth_connection(
        db,
        current_user.id,
        "jira",
        access_token=access_token,
        refresh_token=refresh_token,
        cloud_id=cloud["id"],
        cloud_name=cloud["name"],
        cloud_url=cloud["url"],
        account_email=me.get("emailAddress", ""),
        account_name=me.get("displayName", ""),
        account_id=me.get("accountId", ""),
    )

    logger.info(
        "JIRA connected: user=%s account=%s cloud=%s",
        current_user.id, me.get("displayName"), cloud["name"],
    )

    return _close_tab_html(
        success=True,
        message=f"Connected as {me.get('displayName')} on {cloud['name']}",
    )


@router.get("/status")
async def auth_status(
    session_id: str = Query(...),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Check whether this session has a connected JIRA account."""
    await require_session_owner(session_id, current_user, db)
    token = await get_oauth_connection(db, current_user.id, "jira")
    if not token:
        return {
            "connected":  False,
            "user_name":  None,
            "user_email": None,
            "cloud_name": None,
        }
    return {
        "connected":  True,
        "user_name":  token.account_name,
        "user_email": token.account_email,
        "cloud_name": token.cloud_name,
    }


@router.delete("/disconnect")
async def disconnect(
    session_id: str = Query(...),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Remove stored JIRA credentials for this session."""
    await require_session_owner(session_id, current_user, db)
    await delete_oauth_connection(db, current_user.id, "jira")
    return {"disconnected": True, "session_id": session_id}


# ── User-scoped endpoints (no session_id needed — for JIRA tab) ───────────────

@router.get("/me/status")
async def me_status(
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return JIRA connection status for the logged-in user (no session required)."""
    token = await get_oauth_connection(db, current_user.id, "jira")
    if token:
        public_base = _public_jira_base_url(token.cloud_url)
        project_url = f"{public_base}/projects/{settings.jira_project_key}" if public_base else None
        return {
            "connected":   True,
            "user_name":   token.account_name,
            "user_email":  token.account_email,
            "cloud_name":  token.cloud_name,
            "auth_mode":   "oauth",
            "project_url": project_url,
        }
    pat = await get_oauth_connection(db, current_user.id, "jira_pat")
    if pat:
        project_key = pat.cloud_id or settings.jira_project_key
        public_base = _public_jira_base_url(pat.cloud_url)
        project_url = f"{public_base}/projects/{project_key}" if public_base else None
        return {
            "connected":   True,
            "user_name":   pat.account_name,
            "user_email":  pat.account_email,
            "cloud_name":  pat.cloud_url,
            "auth_mode":   "pat",
            "project_url": project_url,
        }
    return {"connected": False, "user_name": None, "user_email": None, "cloud_name": None, "auth_mode": None, "project_url": None}


@router.post("/me/pat")
async def me_save_pat(
    payload: dict,
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Save user-supplied JIRA PAT credentials and verify them before storing.
    Returns 401 if the credentials are rejected by Jira so the UI can surface
    a clear error rather than saving bad credentials that look "connected".
    """
    base_url    = (payload.get("base_url") or "").strip().rstrip("/")
    username    = (payload.get("username") or "").strip()
    api_token   = (payload.get("api_token") or "").strip()
    project_key = (payload.get("project_key") or "").strip()

    if not base_url or not username or not api_token:
        raise HTTPException(status_code=422, detail="base_url, username and api_token are required")

    # ── Verify credentials against Jira before saving ─────────────────────────
    # Try Bearer first (PAT on Jira DC/Server with SSO/LDAP where Basic auth is disabled),
    # then fall back to Basic auth (older Jira or password-based auth).
    # Store which method worked in refresh_token so JiraService can use the right one.
    import httpx as _httpx

    async def _probe(client: _httpx.AsyncClient, **kwargs) -> _httpx.Response:
        return await client.get(
            f"{base_url}/rest/api/2/myself",
            timeout=10,
            follow_redirects=False,
            **kwargs,
        )

    me: dict = {}
    auth_method: str = ""

    try:
        async with _httpx.AsyncClient() as client:
            # 1. Bearer (PAT)
            r = await _probe(client, headers={"Authorization": f"Bearer {api_token}"})
            if r.is_success:
                me, auth_method = r.json(), "bearer"
            else:
                # 2. Basic auth (username:password or username:PAT)
                r = await _probe(client, auth=(username, api_token))
                if r.is_success:
                    me, auth_method = r.json(), "basic"
                else:
                    code = r.status_code
                    if code in (301, 302, 303, 307, 308):
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=(
                                "Jira redirected to the login page — neither Bearer nor Basic auth "
                                "was accepted. Ensure your PAT is valid or contact your Jira admin."
                            ),
                        )
                    if code == 401:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=(
                                "Jira rejected both Bearer and Basic auth (401). "
                                "If your organisation uses SSO, generate a Personal Access Token at "
                                "Profile → Personal Access Tokens and paste it in the token field."
                            ),
                        )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Jira returned {code} while verifying credentials.",
                    )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not reach Jira at {base_url}: {exc}",
        )

    display_name = me.get("displayName") or username

    # ── Credentials verified — save (store auth_method in refresh_token) ──────
    await upsert_oauth_connection(
        db,
        current_user.id,
        "jira_pat",
        access_token=api_token,
        refresh_token=auth_method,          # "bearer" | "basic"
        account_email=username,
        account_name=display_name,
        cloud_url=base_url,
        cloud_id=project_key,
        cloud_name=base_url,
        account_id=me.get("accountId", me.get("name", "")),
    )
    return {"saved": True, "username": display_name, "base_url": base_url, "auth_method": auth_method}


@router.get("/me/connect")
async def me_connect(
    request: Request,
    current_user: User = Depends(require_current_user),
) -> dict:
    """Return Atlassian OAuth URL for the JIRA tab (no session required)."""
    if not settings.atlassian_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="ATLASSIAN_CLIENT_ID not configured. See .env.example.",
        )
    callback = f"{settings.backend_url.rstrip('/')}/api/v1/jira/auth/callback"
    # Use "user:{id}" as state so the callback can skip session ownership check
    params = {
        "audience":      "api.atlassian.com",
        "client_id":     settings.atlassian_client_id,
        "scope":         _SCOPES,
        "redirect_uri":  callback,
        "state":         f"user:{current_user.id}",
        "response_type": "code",
        "prompt":        "consent",
    }
    return {"url": _AUTH_URL + "?" + urlencode(params)}


@router.delete("/me/disconnect")
async def me_disconnect(
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Remove all JIRA credentials (OAuth + PAT) for the logged-in user."""
    await delete_oauth_connection(db, current_user.id, "jira")
    await delete_oauth_connection(db, current_user.id, "jira_pat")
    return {"disconnected": True}


# ── Data endpoints ───────────────────────────────────────────────────────────

def _raise_jira_http_error(exc: Exception, operation: str) -> None:
    """Convert JIRA HTTP errors into user-friendly FastAPI exceptions."""
    import httpx as _httpx
    if isinstance(exc, _httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (301, 302, 303, 307, 308):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "JIRA redirected to the login page — your credentials were not recognised. "
                    "Go to JIRA Settings, re-enter your username and password (or PAT), and try again."
                ),
            )
        if code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "JIRA authentication failed (401). "
                    "Your username or token is incorrect. "
                    "Go to JIRA Settings and re-enter your credentials."
                ),
            )
        if code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="JIRA returned 403 — your account may not have permission for this project.",
            )
    logger.exception("%s failed: %s", operation, exc)
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"JIRA request failed: {exc}",
    )


@router.get("/boards")
async def list_boards(
    project_key: Optional[str] = Query(default=None, description="Filter by project key"),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return all Agile boards visible to the authenticated user, optionally filtered by project."""
    try:
        svc = await JiraService.for_user(db, current_user.id)
        boards = await svc.fetch_all_boards(project_key=project_key)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        _raise_jira_http_error(exc, "list_boards")
    return {"boards": boards, "total": len(boards)}


@router.get("/projects")
async def list_projects(
    q: str = Query(default="", description="Filter projects by name or key (case-insensitive)"),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return all projects visible to the authenticated user, optionally filtered by a query string."""
    try:
        svc = await JiraService.for_user(db, current_user.id)
        projects = await svc.search_projects(query=q)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        _raise_jira_http_error(exc, "list_projects")
    return {"projects": projects, "total": len(projects)}


@router.get("/epics")
async def list_epics(
    project_key: str = Query(..., description="Project key to search epics in"),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return existing Epics for a project — used to populate the parent-epic selector."""
    try:
        svc = await JiraService.for_user(db, current_user.id)
        epics = await svc.search_epics(project_key)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        _raise_jira_http_error(exc, "list_epics")
    return {"epics": epics, "total": len(epics)}


class JiraCreateRequest(BaseModel):
    prd_markdown: str
    feature_name: str = "Feature"
    project_key: str = ""
    assignee_email: str = ""


@router.post("/create")
async def direct_create(
    payload: JiraCreateRequest,
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Create a JIRA Epic → Stories → Subtasks hierarchy directly from PRD markdown.
    Works outside the LangGraph chat flow — useful from the Projects page or any
    standalone trigger. Returns {epic_key, epic_url, task_keys, cloud_url}.
    """
    try:
        svc = await JiraService.for_user(db, current_user.id)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return await svc.create_from_prd(
        prd_markdown=payload.prd_markdown,
        feature_name=payload.feature_name,
        assignee_email=payload.assignee_email,
        project_key=payload.project_key,
    )


# ── HTML helper ───────────────────────────────────────────────────────────────

def _close_tab_html(success: bool, message: str) -> HTMLResponse:
    """
    Returns a minimal HTML page that:
    - Shows the result to the user for 2 seconds
    - Calls window.opener.postMessage so the parent tab knows the result
    - Closes itself
    """
    import json as _json
    color   = "#16a34a" if success else "#dc2626"
    icon    = "✅" if success else "❌"
    payload = _json.dumps({"type": "jira_oauth", "success": success, "message": message})

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>JIRA Connection</title>
<style>
  body {{ font-family: system-ui, sans-serif; display: grid; place-items: center;
         min-height: 100vh; margin: 0; background: #f9fafb; }}
  .card {{ background: white; border-radius: 16px; padding: 40px 48px;
           box-shadow: 0 4px 24px rgba(0,0,0,.08); text-align: center; max-width: 400px; }}
  h2 {{ color: {color}; margin: 0 0 12px; font-size: 1.5rem; }}
  p  {{ color: #6b7280; margin: 0; line-height: 1.6; }}
</style>
</head><body>
<div class="card">
  <h2>{icon} {"Connected" if success else "Failed"}</h2>
  <p>{message}</p>
  <p style="margin-top:16px;font-size:.85rem">This tab will close automatically…</p>
</div>
<script>
  try {{
    if (window.opener) window.opener.postMessage({payload}, "*");
  }} catch(e) {{}}
  setTimeout(() => window.close(), 2000);
</script>
</body></html>"""
    return HTMLResponse(content=html)
