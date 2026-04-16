from __future__ import annotations

import json
import logging
from urllib.parse import parse_qs

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import SessionLocal
from src.services.jira import JiraService
from src.services.slack_helper import SlackJiraHelperService, verify_slack_signature

router = APIRouter(prefix="/api/v1/slack", tags=["Slack Helper"])
logger = logging.getLogger(__name__)


def _extract_user_name(event: dict) -> str:
    return (
        event.get("user_profile", {}).get("display_name")
        or event.get("username")
        or event.get("user")
        or "Slack user"
    )


async def _process_thread_message(db: AsyncSession, payload: dict, event: dict) -> None:
    service = SlackJiraHelperService(db)
    workspace_id = payload.get("team_id") or payload.get("authorizations", [{}])[0].get("team_id") or "unknown"
    channel_id = event.get("channel", "")
    thread_ts = event.get("thread_ts") or event.get("ts") or ""
    if not channel_id or not thread_ts:
        return

    is_new = await service.register_event_delivery(payload.get("event_id", ""), event.get("type", ""))
    if not is_new:
        logger.info("Ignoring duplicate Slack delivery %s", payload.get("event_id"))
        return

    record = await service.get_or_create_request(
        workspace_id=workspace_id,
        channel_id=channel_id,
        thread_ts=thread_ts,
        root_message_ts=event.get("ts", thread_ts),
        requester_slack_id=event.get("user", ""),
        requester_name=_extract_user_name(event),
    )
    text = event.get("text", "")
    slack_user_id = event.get("user", "")
    slack_user_name = _extract_user_name(event)
    service.apply_message(record, text, slack_user_id=slack_user_id, slack_user_name=slack_user_name)

    if record.status == "created":
        await service.post_thread_message(
            channel_id=channel_id,
            thread_ts=thread_ts,
            text="This request has already created Jira tickets. Start a new thread if you need another ticket set.",
        )
        return

    if service.is_approval_message(text):
        if not record.proposal_json:
            proposal = service.build_ticket_proposal(record)
            await service.save_proposal(record, proposal)
        if not service.is_user_allowed_to_approve(slack_user_id):
            await service.post_thread_message(
                channel_id=channel_id,
                thread_ts=thread_ts,
                text="You are not allowed to approve this Jira structure. Ask a configured PDM approver to confirm it.",
            )
            return
        await service.mark_approved(record, slack_user_id=slack_user_id, slack_user_name=slack_user_name)
        try:
            jira = await JiraService.for_user(db, None)
            proposal = service.load_proposal(record)
            result = await jira.create_from_ticket_plan(
                proposal,
                project_key=proposal.get("project_key", ""),
            )
        except httpx.HTTPStatusError as exc:
            record.status = "awaiting_approval"
            await service.save_record(record)
            logger.exception("Slack Jira creation failed: %s", exc)
            if exc.response.status_code == 401:
                error_text = (
                    "Jira ticket creation failed: authentication rejected (401).\n\n"
                    "The Jira credentials stored for this integration are no longer valid. "
                    "Please ask your admin to disconnect the Jira service account and reconnect it:\n"
                    "1. Open the TeamSync app and go to *JIRA Settings*.\n"
                    "2. Click *Disconnect*.\n"
                    "3. Log in again with valid credentials or a fresh Personal Access Token.\n\n"
                    "Once reconnected, reply `approve` to retry ticket creation."
                )
            else:
                error_text = f"Jira ticket creation failed: {exc}"
            await service.post_thread_message(
                channel_id=channel_id,
                thread_ts=thread_ts,
                text=error_text,
            )
            return
        except Exception as exc:
            record.status = "awaiting_approval"
            await service.save_record(record)
            logger.exception("Slack Jira creation failed: %s", exc)
            await service.post_thread_message(
                channel_id=channel_id,
                thread_ts=thread_ts,
                text=f"Jira ticket creation failed: {exc}",
            )
            return

        issue_keys = [result["parent_key"], *result["task_keys"]]
        await service.mark_created(record, issue_keys)
        await service.post_thread_message(
            channel_id=channel_id,
            thread_ts=thread_ts,
            text=(
                "Jira tickets created:\n"
                f"- Parent: {result['parent_key']} {result['parent_url']}\n"
                + "\n".join(f"- Subtask: {key}" for key in result["task_keys"])
                + "\n\nConfluence draft:\n"
                + record.confluence_draft
            ),
        )
        return

    missing = service.missing_fields(record)
    if missing:
        await service.save_record(record)
        await service.post_thread_message(
            channel_id=channel_id,
            thread_ts=thread_ts,
            text=service.build_missing_info_prompt(record),
        )
        return

    proposal = service.build_ticket_proposal(record)
    await service.save_proposal(record, proposal)
    await service.post_thread_message(
        channel_id=channel_id,
        thread_ts=thread_ts,
        text=service.format_proposal_for_slack(proposal, record),
    )


@router.post("/events")
async def slack_events(request: Request) -> dict:
    body = await request.body()
    if not verify_slack_signature(
        signing_secret=settings.slack_signing_secret,
        timestamp=request.headers.get("X-Slack-Request-Timestamp", ""),
        body=body,
        signature=request.headers.get("X-Slack-Signature", ""),
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Slack signature")

    payload = json.loads(body.decode("utf-8") or "{}")
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge", "")}
    if payload.get("type") != "event_callback":
        return {"ok": True}

    event = payload.get("event", {})
    if event.get("type") not in {"app_mention", "message"}:
        return {"ok": True}
    if event.get("subtype") in {"bot_message", "message_changed", "message_deleted"}:
        return {"ok": True}
    if event.get("type") == "message" and not event.get("thread_ts"):
        return {"ok": True}

    async with SessionLocal() as db:
        await _process_thread_message(db, payload, event)
    return {"ok": True}


@router.post("/interactions")
async def slack_interactions(request: Request) -> dict:
    body = await request.body()
    if not verify_slack_signature(
        signing_secret=settings.slack_signing_secret,
        timestamp=request.headers.get("X-Slack-Request-Timestamp", ""),
        body=body,
        signature=request.headers.get("X-Slack-Signature", ""),
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Slack signature")

    form = parse_qs(body.decode("utf-8"))
    payload_raw = form.get("payload", ["{}"])[0]
    payload = json.loads(payload_raw)
    return {"ok": True, "type": payload.get("type", "unknown")}
