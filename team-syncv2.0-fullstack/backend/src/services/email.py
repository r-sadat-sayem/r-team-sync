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
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

_GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


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


# ── SMTP send (App Password fallback) ────────────────────────────────────────

def _smtp_send(sender: str, recipient: str, raw_message: str) -> None:
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
        server.login(sender, settings.gmail_app_password)
        server.sendmail(sender, recipient, raw_message)


def _resolve_sender(access_token: str | None, session_email: str | None) -> str:
    """Pick the From address — OAuth email first, then SMTP sender."""
    if session_email:
        return session_email
    return settings.gmail_sender


# ── Public API ────────────────────────────────────────────────────────────────

async def send_prd_email(
    recipient_name: str,
    recipient_email: str,
    prd_markdown: str,
    file_name: str,
    quality_score: int,
    grade: str,
    access_token: str | None = None,
    sender_email: str | None = None,
) -> None:
    sender = _resolve_sender(access_token, sender_email)

    body = (
        f"Hi {recipient_name},\n\n"
        f"Your Product Requirements Document has been generated and scored.\n\n"
        f"Quality Score: {quality_score}/100 (Grade {grade})\n\n"
        f"The full PRD is attached as a markdown file.\n\n"
        f"Best regards,\nSam — TeamSync AI"
    )

    msg = MIMEMultipart()
    msg["From"]    = sender
    msg["To"]      = recipient_email
    msg["Subject"] = f"Your PRD is ready — {file_name}"
    msg.attach(MIMEText(body, "plain"))

    attachment = MIMEBase("text", "markdown")
    attachment.set_payload(prd_markdown.encode("utf-8"))
    encoders.encode_base64(attachment)
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
    access_token: str | None = None,
    sender_email: str | None = None,
) -> None:
    sender = _resolve_sender(access_token, sender_email)

    task_lines = "\n".join(
        f"  • {key}: {settings.jira_base_url}/browse/{key}" for key in task_keys
    )
    body = (
        f"Hi {assignee_name or assignee_email},\n\n"
        f"JIRA tickets have been created for the PRD: {prd_title}\n\n"
        f"Epic ({epic_key}):\n  {epic_url}\n\n"
        f"Stories:\n{task_lines or '  (none created)'}\n\n"
    )
    if notes:
        body += f"Notes from reviewer:\n{notes}\n\n"
    body += "Best regards,\nSam — TeamSync AI"

    msg = MIMEMultipart()
    msg["From"]    = sender
    msg["To"]      = assignee_email
    msg["Subject"] = f"JIRA tickets created — {prd_title} [{epic_key}]"
    msg.attach(MIMEText(body, "plain"))

    logger.info("Sending JIRA notification to %s", assignee_email)

    if access_token:
        await _send_via_api(access_token, msg)
    else:
        await asyncio.to_thread(_smtp_send, sender, assignee_email, msg.as_string())

    logger.info("JIRA notification sent to %s", assignee_email)
