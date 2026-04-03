"""
Gmail SMTP service.

Uses an App Password — simpler than copying OAuth tokens out of n8n.
Setup: Google Account → Security → 2-Step Verification → App passwords → generate one.
Store GMAIL_SENDER and GMAIL_APP_PASSWORD in .env.

All public functions are async; smtplib calls run in a thread pool
via asyncio.to_thread so they don't block the event loop.
"""
import asyncio
import logging
import smtplib
import ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import settings

logger = logging.getLogger(__name__)


async def send_prd_email(
    recipient_name: str,
    recipient_email: str,
    prd_markdown: str,
    file_name: str,
    quality_score: int,
    grade: str,
) -> None:
    """
    Send PRD as a markdown attachment via Gmail SMTP.
    Raises on failure — caller should handle and surface to user.
    """
    subject = f"Your PRD is ready — {file_name}"

    body = (
        f"Hi {recipient_name},\n\n"
        f"Your Product Requirements Document has been generated and scored.\n\n"
        f"Quality Score: {quality_score}/100 (Grade {grade})\n\n"
        f"The full PRD is attached as a markdown file.\n\n"
        f"Best regards,\nSam — TeamSync AI"
    )

    msg = MIMEMultipart()
    msg["From"]    = settings.gmail_sender
    msg["To"]      = recipient_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    # Attach PRD as .md file
    attachment = MIMEBase("text", "markdown")
    attachment.set_payload(prd_markdown.encode("utf-8"))
    encoders.encode_base64(attachment)
    attachment.add_header(
        "Content-Disposition",
        f'attachment; filename="{file_name}"',
    )
    msg.attach(attachment)

    logger.info("Sending PRD email to %s (%s)", recipient_email, file_name)
    raw = msg.as_string()
    await asyncio.to_thread(_smtp_send, settings.gmail_sender, recipient_email, raw)
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
) -> None:
    """
    Notify the JIRA assignee that tickets have been created with direct links.
    """
    task_lines = "\n".join(
        f"  • {key}: {settings.jira_base_url}/browse/{key}"
        for key in task_keys
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
    msg["From"]    = settings.gmail_sender
    msg["To"]      = assignee_email
    msg["Subject"] = f"JIRA tickets created — {prd_title} [{epic_key}]"
    msg.attach(MIMEText(body, "plain"))

    logger.info("Sending JIRA notification to %s", assignee_email)
    raw = msg.as_string()
    await asyncio.to_thread(_smtp_send, settings.gmail_sender, assignee_email, raw)
    logger.info("JIRA notification sent to %s", assignee_email)


def _smtp_send(sender: str, recipient: str, raw_message: str) -> None:
    """Synchronous SMTP send — always called via asyncio.to_thread."""
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender, settings.gmail_app_password)
        server.sendmail(sender, recipient, raw_message)
