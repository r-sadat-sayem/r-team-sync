from __future__ import annotations

"""
Email service — two auth modes:

  1. Gmail OAuth (preferred)
     User connects via /api/v1/email/auth/connect → OAuth popup.
     Emails sent via Gmail API under the user's own identity.
     No App Password or admin credentials needed.

  2. SMTP App Password (fallback)
     Set GMAIL_SENDER + GMAIL_APP_PASSWORD in .env.
     Used when no OAuth token is present for the session.

Both modes send PRD as a .md attachment and JIRA notification emails.
"""
import asyncio
import base64
import logging
import smtplib
import ssl
from typing import Optional
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.services.oauth_connections import get_oauth_connection

logger = logging.getLogger(__name__)

_GMAIL_SEND_URL   = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


# ── Gmail API send (OAuth) ────────────────────────────────────────────────────

async def _send_via_api(access_token: str, msg: MIMEMultipart) -> None:
    """Send a pre-built MIME message using the Gmail REST API."""
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    async with httpx.AsyncClient() as client:
        r = await client.post(
            _GMAIL_SEND_URL,
            json={"raw": raw},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        if not r.is_success:
            logger.error("Gmail API send failed: %s %s", r.status_code, r.text)
            r.raise_for_status()
        # Log the message ID so delivery can be verified in Gmail's Sent folder
        message_id = r.json().get("id", "unknown")
        logger.info("Gmail API accepted message id=%s to=%s", message_id, msg["To"])


# ── SMTP send (App Password fallback) ────────────────────────────────────────

def _smtp_send(sender: str, recipient: str, raw_message: str) -> None:
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
        server.login(sender, settings.gmail_app_password)
        server.sendmail(sender, recipient, raw_message)


def _resolve_sender(access_token: Optional[str], session_email: Optional[str]) -> str:
    """
    Pick the From address.
    When sending via Gmail API the From: header MUST match the authenticated
    account — if it doesn't, Gmail silently rewrites it, breaking SPF/DKIM
    alignment and causing spam filters to flag the message.
    """
    if access_token and session_email:
        return session_email          # OAuth: use the connected account email
    if session_email:
        return session_email
    return settings.gmail_sender     # SMTP fallback


async def get_gmail_connection(db: AsyncSession, user_id: int):
    return await get_oauth_connection(db, user_id, "gmail")


async def refresh_gmail_token(db: AsyncSession, user_id: int) -> Optional[str]:
    """
    Refresh the stored Gmail access token using the stored refresh_token.
    Updates the DB record and returns the new access_token.
    Falls back to the existing token if refresh fails or no refresh_token is stored.
    Returns None if no connection exists at all.
    """
    from src.services.oauth_connections import upsert_oauth_connection

    token = await get_oauth_connection(db, user_id, "gmail")
    if not token:
        return None
    if not token.refresh_token:
        return token.access_token

    async with httpx.AsyncClient() as client:
        r = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "client_id":     settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": token.refresh_token,
                "grant_type":    "refresh_token",
            },
            timeout=15,
        )
        if not r.is_success:
            logger.warning("Gmail token refresh failed: %s %s", r.status_code, r.text)
            return token.access_token  # fallback — let the send attempt proceed

    new_access_token = r.json().get("access_token", token.access_token)
    await upsert_oauth_connection(db, user_id, "gmail", access_token=new_access_token)
    logger.info("Gmail access token refreshed for user_id=%d", user_id)
    return new_access_token


# ── Public API ────────────────────────────────────────────────────────────────

async def send_prd_email(
    recipient_name: str,
    recipient_email: str,
    prd_markdown: str,
    file_name: str,
    quality_score: int,
    grade: str,
    access_token: Optional[str] = None,
    sender_email: Optional[str] = None,
) -> None:
    sender = _resolve_sender(access_token, sender_email)

    plain_body = (
        f"Hi {recipient_name},\n\n"
        f"Your Product Requirements Document has been generated and scored.\n\n"
        f"  Quality Score : {quality_score}/100\n"
        f"  Grade         : {grade}\n"
        f"  File          : {file_name}\n\n"
        f"The full PRD is attached as a Markdown file (.md).\n"
        f"You can open it in any text editor or Markdown viewer.\n\n"
        f"Best regards,\nSam — TeamSync AI"
    )

    html_body = f"""\
<html><body style="font-family:sans-serif;color:#1f2937;line-height:1.6">
  <p>Hi {recipient_name},</p>
  <p>Your <strong>Product Requirements Document</strong> has been generated and scored.</p>
  <table style="border-collapse:collapse;margin:12px 0">
    <tr><td style="padding:4px 16px 4px 0;color:#6b7280">Quality Score</td>
        <td style="padding:4px 0"><strong>{quality_score}/100</strong></td></tr>
    <tr><td style="padding:4px 16px 4px 0;color:#6b7280">Grade</td>
        <td style="padding:4px 0"><strong>{grade}</strong></td></tr>
    <tr><td style="padding:4px 16px 4px 0;color:#6b7280">File</td>
        <td style="padding:4px 0"><code>{file_name}</code></td></tr>
  </table>
  <p>The full PRD is <strong>attached</strong> as a Markdown file (.md).<br>
     Open it in any text editor or Markdown viewer.</p>
  <p style="color:#6b7280;font-size:.9em">Best regards,<br>Sam — TeamSync AI</p>
</body></html>"""

    # Multipart/alternative wraps the two body variants; the outer mixed carries the attachment
    msg = MIMEMultipart("mixed")
    msg["From"]    = sender
    msg["To"]      = recipient_email
    msg["Subject"] = f"Your PRD is ready — {file_name}"

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(plain_body, "plain", "utf-8"))
    alt.attach(MIMEText(html_body,  "html",  "utf-8"))
    msg.attach(alt)

    # Attachment — use application/octet-stream so all clients offer a download prompt
    attachment = MIMEBase("application", "octet-stream")
    attachment.set_payload(prd_markdown.encode("utf-8"))
    encoders.encode_base64(attachment)
    attachment.add_header("Content-Type", "application/octet-stream; charset=utf-8")
    attachment.add_header("Content-Disposition", f'attachment; filename="{file_name}"')
    msg.attach(attachment)

    logger.info("Sending PRD email to %s (mode=%s)", recipient_email,
                "oauth" if access_token else "smtp")

    if access_token:
        await _send_via_api(access_token, msg)
    else:
        await asyncio.to_thread(_smtp_send, sender, recipient_email, msg.as_string())

    logger.info("PRD email sent to %s", recipient_email)


async def send_jira_notification(
    assignee_email: str,
    assignee_name: str,
    epic_key: str,
    epic_url: str,
    task_keys: list[str],
    project_key: str,
    prd_title: str,
    notes: str,
    access_token: Optional[str] = None,
    sender_email: Optional[str] = None,
) -> None:
    sender      = _resolve_sender(access_token, sender_email)
    name        = assignee_name or assignee_email
    story_items = "\n".join(
        f"  • {key}: {settings.jira_base_url}/browse/{key}" for key in task_keys
    )
    story_html  = "".join(
        f'<li><a href="{settings.jira_base_url}/browse/{key}">{key}</a></li>'
        for key in task_keys
    )

    plain_body = (
        f"Hi {name},\n\n"
        f"JIRA tickets have been created for the PRD: {prd_title}\n\n"
        f"Epic ({epic_key}):\n  {epic_url}\n\n"
        f"Stories:\n{story_items or '  (none created)'}\n\n"
    )
    if notes:
        plain_body += f"Notes from reviewer:\n{notes}\n\n"
    plain_body += "Best regards,\nSam — TeamSync AI"

    html_body = f"""\
<html><body style="font-family:sans-serif;color:#1f2937;line-height:1.6">
  <p>Hi {name},</p>
  <p>JIRA tickets have been created for the PRD: <strong>{prd_title}</strong></p>
  <p><strong>Epic:</strong> <a href="{epic_url}">{epic_key}</a></p>
  {"<p><strong>Stories:</strong></p><ul>" + story_html + "</ul>" if story_html else ""}
  {"<p><strong>Notes:</strong><br>" + notes.replace(chr(10), "<br>") + "</p>" if notes else ""}
  <p style="color:#6b7280;font-size:.9em">Best regards,<br>Sam — TeamSync AI</p>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["From"]    = sender
    msg["To"]      = assignee_email
    msg["Subject"] = f"JIRA tickets created — {prd_title} [{epic_key}]"
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body,  "html",  "utf-8"))

    logger.info("Sending JIRA notification to %s", assignee_email)

    if access_token:
        await _send_via_api(access_token, msg)
    else:
        await asyncio.to_thread(_smtp_send, sender, assignee_email, msg.as_string())

    logger.info("JIRA notification sent to %s", assignee_email)
