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
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse

from src.config import settings
from src.middleware.auth import require_api_key

router = APIRouter(prefix="/api/v1/jira/auth", tags=["JIRA Auth"])
logger = logging.getLogger(__name__)

# ── Atlassian OAuth constants ─────────────────────────────────────────────────

_AUTH_URL      = "https://auth.atlassian.com/authorize"
_TOKEN_URL     = "https://auth.atlassian.com/oauth/token"
_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"
_SCOPES        = "read:jira-work write:jira-work offline_access"

# ── In-process token store ────────────────────────────────────────────────────
# Keyed by session_id. Replace with a PostgreSQL table in production.

_token_store: dict[str, dict] = {}


def get_token(session_id: str) -> dict | None:
    return _token_store.get(session_id)


def set_token(session_id: str, data: dict) -> None:
    _token_store[session_id] = data


def clear_token(session_id: str) -> None:
    _token_store.pop(session_id, None)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/connect", dependencies=[Depends(require_api_key)])
async def connect(
    request: Request,
    session_id: str = Query(..., description="LangGraph session / thread ID"),
) -> dict:
    """
    Return the Atlassian OAuth URL for this session.
    Frontend opens it in a new tab or popup.
    """
    if not settings.atlassian_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="ATLASSIAN_CLIENT_ID not configured. See .env.example.",
        )

    callback = str(request.url_for("jira_oauth_callback"))
    params = {
        "audience":      "api.atlassian.com",
        "client_id":     settings.atlassian_client_id,
        "scope":         _SCOPES,
        "redirect_uri":  callback,
        "state":         session_id,          # carries session_id through the flow
        "response_type": "code",
        "prompt":        "consent",
    }
    url = _AUTH_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return {"url": url, "session_id": session_id}


@router.get("/callback", name="jira_oauth_callback", include_in_schema=False)
async def callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),     # this is the session_id
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> HTMLResponse:
    """
    Atlassian redirects here after the user grants (or denies) permission.
    Exchanges auth code for tokens, fetches cloud instance info, stores both.
    Returns a self-closing HTML page — the OAuth tab closes itself.
    """
    if error:
        logger.warning("JIRA OAuth error for session %s: %s — %s", state, error, error_description)
        return _close_tab_html(
            success=False,
            message=f"JIRA connection failed: {error_description or error}",
        )

    session_id = state
    callback_url = str(request.url_for("jira_oauth_callback"))

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

            # 3. Fetch the user's own profile for display name / email
            me_resp = await client.get(
                f"https://api.atlassian.com/ex/jira/{cloud['id']}/rest/api/3/myself",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            me_resp.raise_for_status()
            me = me_resp.json()

    except Exception as exc:
        logger.exception("JIRA OAuth callback failed for session %s: %s", session_id, exc)
        return _close_tab_html(success=False, message=f"Connection failed: {exc}")

    # 4. Store everything keyed by session_id
    set_token(session_id, {
        "access_token":   access_token,
        "refresh_token":  refresh_token,
        "cloud_id":       cloud["id"],
        "cloud_name":     cloud["name"],
        "cloud_url":      cloud["url"],
        "user_email":     me.get("emailAddress", ""),
        "user_name":      me.get("displayName", ""),
        "account_id":     me.get("accountId", ""),
    })

    logger.info(
        "JIRA connected: session=%s user=%s cloud=%s",
        session_id, me.get("displayName"), cloud["name"],
    )

    return _close_tab_html(
        success=True,
        message=f"Connected as {me.get('displayName')} on {cloud['name']}",
    )


@router.get("/status", dependencies=[Depends(require_api_key)])
async def auth_status(
    session_id: str = Query(...),
) -> dict:
    """Check whether this session has a connected JIRA account."""
    token = get_token(session_id)
    if not token:
        return {
            "connected":  False,
            "user_name":  None,
            "user_email": None,
            "cloud_name": None,
        }
    return {
        "connected":  True,
        "user_name":  token["user_name"],
        "user_email": token["user_email"],
        "cloud_name": token["cloud_name"],
    }


@router.delete("/disconnect", dependencies=[Depends(require_api_key)])
async def disconnect(session_id: str = Query(...)) -> dict:
    """Remove stored JIRA credentials for this session."""
    clear_token(session_id)
    return {"disconnected": True, "session_id": session_id}


# ── HTML helper ───────────────────────────────────────────────────────────────

def _close_tab_html(success: bool, message: str) -> HTMLResponse:
    """
    Returns a minimal HTML page that:
    - Shows the result to the user for 2 seconds
    - Calls window.opener.postMessage so the parent tab knows the result
    - Closes itself
    """
    color   = "#16a34a" if success else "#dc2626"
    icon    = "✅" if success else "❌"
    payload = '{"type":"jira_oauth","success":' + ("true" if success else "false") + '}'

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
