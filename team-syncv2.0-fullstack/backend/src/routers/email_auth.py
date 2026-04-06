"""
Gmail OAuth 2.0 flow — same pattern as JIRA auth.

Endpoints:
  GET /api/v1/email/auth/connect?session_id={id}
      Returns the Google OAuth URL. Frontend opens it in a popup.

  GET /api/v1/email/auth/callback
      Google redirects here after user grants access.
      Exchanges code for tokens, stores in token store, closes tab.

  GET /api/v1/email/auth/status?session_id={id}
      Returns {connected, email} — frontend polls after popup closes.

  DELETE /api/v1/email/auth/disconnect?session_id={id}
      Clears stored token for this session.

Setup (one-time, team admin):
  1. console.cloud.google.com → New project → Enable Gmail API
  2. APIs & Services → Credentials → OAuth 2.0 Client ID → Web application
  3. Authorised redirect URI: http://localhost:8000/api/v1/email/auth/callback
  4. Copy Client ID + Secret → GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET in .env
"""
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse

from src.config import settings
from src.middleware.auth import require_api_key

router = APIRouter(prefix="/api/v1/email/auth", tags=["Gmail Auth"])
logger = logging.getLogger(__name__)

# ── Google OAuth constants ────────────────────────────────────────────────────

_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SCOPES    = " ".join([
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
])

# ── In-process token store ────────────────────────────────────────────────────

_token_store: dict[str, dict] = {}


def get_gmail_token(session_id: str) -> dict | None:
    return _token_store.get(session_id)


def set_gmail_token(session_id: str, data: dict) -> None:
    _token_store[session_id] = data


def clear_gmail_token(session_id: str) -> None:
    _token_store.pop(session_id, None)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/connect", dependencies=[Depends(require_api_key)])
async def connect(
    request: Request,
    session_id: str = Query(...),
) -> dict:
    """Return the Google OAuth URL for this session."""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GOOGLE_CLIENT_ID not configured. See .env.example.",
        )

    callback = str(request.url_for("gmail_oauth_callback"))
    params = {
        "client_id":     settings.google_client_id,
        "redirect_uri":  callback,
        "response_type": "code",
        "scope":         _SCOPES,
        "access_type":   "offline",   # get refresh token
        "prompt":        "consent",   # always show consent to get refresh token
        "state":         session_id,
    }
    url = _AUTH_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return {"url": url, "session_id": session_id}


@router.get("/callback", name="gmail_oauth_callback", include_in_schema=False)
async def callback(
    request: Request,
    code: str | None      = Query(default=None),
    state: str            = Query(...),
    error: str | None     = Query(default=None),
    error_description: str | None = Query(default=None),
) -> HTMLResponse:
    """Google redirects here. Exchange code for tokens, close tab."""
    if error:
        logger.warning("Gmail OAuth error for session %s: %s", state, error)
        return _close_tab_html(False, f"Gmail connection failed: {error_description or error}")

    session_id   = state
    callback_url = str(request.url_for("gmail_oauth_callback"))

    try:
        async with httpx.AsyncClient() as client:
            # Exchange auth code for access + refresh tokens
            token_resp = await client.post(
                _TOKEN_URL,
                data={
                    "code":          code,
                    "client_id":     settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri":  callback_url,
                    "grant_type":    "authorization_code",
                },
                timeout=15,
            )
            token_resp.raise_for_status()
            tokens = token_resp.json()

            # Fetch user email
            profile_resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                timeout=10,
            )
            profile_resp.raise_for_status()
            profile = profile_resp.json()

    except Exception as exc:
        logger.exception("Gmail OAuth callback failed for session %s: %s", session_id, exc)
        return _close_tab_html(False, f"Connection failed: {exc}")

    set_gmail_token(session_id, {
        "access_token":  tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "email":         profile.get("email", ""),
        "name":          profile.get("name", ""),
    })

    logger.info("Gmail connected: session=%s email=%s", session_id, profile.get("email"))
    return _close_tab_html(True, f"Connected as {profile.get('email')}")


@router.get("/status", dependencies=[Depends(require_api_key)])
async def auth_status(session_id: str = Query(...)) -> dict:
    token = get_gmail_token(session_id)
    if not token:
        return {"connected": False, "email": None, "name": None}
    return {"connected": True, "email": token["email"], "name": token["name"]}


@router.delete("/disconnect", dependencies=[Depends(require_api_key)])
async def disconnect(session_id: str = Query(...)) -> dict:
    clear_gmail_token(session_id)
    return {"disconnected": True}


# ── HTML helper (identical pattern to jira_auth) ─────────────────────────────

def _close_tab_html(success: bool, message: str) -> HTMLResponse:
    color   = "#16a34a" if success else "#dc2626"
    icon    = "✅" if success else "❌"
    payload = '{"type":"gmail_oauth","success":' + ("true" if success else "false") + '}'
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Gmail</title>
<style>
  body{{font-family:system-ui,sans-serif;display:grid;place-items:center;min-height:100vh;margin:0;background:#f9fafb}}
  .card{{background:white;border-radius:16px;padding:40px 48px;box-shadow:0 4px 24px rgba(0,0,0,.08);text-align:center;max-width:400px}}
  h2{{color:{color};margin:0 0 12px;font-size:1.5rem}}
  p{{color:#6b7280;margin:0;line-height:1.6}}
</style></head><body>
<div class="card">
  <h2>{icon} {"Connected" if success else "Failed"}</h2>
  <p>{message}</p>
  <p style="margin-top:16px;font-size:.85rem">This tab will close automatically…</p>
</div>
<script>
  try{{if(window.opener)window.opener.postMessage({payload},"*");}}catch(e){{}}
  setTimeout(()=>window.close(),2000);
</script></body></html>"""
    return HTMLResponse(content=html)
