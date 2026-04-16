from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models import SlackEventDelivery, SlackJiraRequest

logger = logging.getLogger(__name__)

_DEVICE_ALIASES = {
    "android": "Android",
    "ios": "iOS",
    "web": "Web",
    "backend": "Backend",
    "api": "API",
}
_PRIORITY_ALIASES = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}
_APPROVE_PATTERNS = (
    re.compile(r"^\s*(approve|approved|looks good|ship it|create(?: the)? tickets?)\b", re.I),
)
_CHANGE_PATTERNS = (
    re.compile(r"^\s*(change|changes|revise|update|adjust|fix)\b", re.I),
)
_KNOWN_LABELS = [
    "summary",
    "title",
    "background",
    "description",
    "details",
    "purpose",
    "goal",
    "objective",
    "why",
    "device",
    "priority",
    "project",
    "project key",
    "jira project",
]


@dataclass
class SlackAction:
    kind: str
    text: str = ""
    thread_ts: str = ""
    channel_id: str = ""


def verify_slack_signature(
    *,
    signing_secret: str,
    timestamp: str,
    body: bytes,
    signature: str,
    now: Optional[int] = None,
) -> bool:
    if not signing_secret or not timestamp or not signature:
        return False
    current = now or int(time.time())
    try:
        ts_int = int(timestamp)
    except ValueError:
        return False
    if abs(current - ts_int) > 60 * 5:
        return False
    basestring = f"v0:{timestamp}:{body.decode('utf-8')}".encode("utf-8")
    digest = hmac.new(
        signing_secret.encode("utf-8"),
        basestring,
        hashlib.sha256,
    ).hexdigest()
    expected = f"v0={digest}"
    return hmac.compare_digest(expected, signature)


def _clean_text(text: str) -> str:
    text = re.sub(r"<@[A-Z0-9]+>", "", text)
    text = text.replace("&amp;", "&").strip()
    return re.sub(r"\s+", " ", text).strip()


def _find_labeled_value(text: str, labels: list[str]) -> str:
    all_labels = "|".join(sorted((re.escape(label) for label in _KNOWN_LABELS), key=len, reverse=True))
    pattern = (
        r"(?:^|\b)(?:"
        + "|".join(re.escape(label) for label in labels)
        + r")\s*:\s*(.+?)(?=(?:\s+(?:"
        + all_labels
        + r")\s*:)|$)"
    )
    match = re.search(pattern, text, re.I | re.M)
    return match.group(1).strip() if match else ""


def _extract_device(text: str) -> str:
    lower = text.lower()
    for needle, label in _DEVICE_ALIASES.items():
        if re.search(rf"\b{re.escape(needle)}\b", lower):
            return label
    return ""


def _extract_priority(text: str) -> str:
    lower = text.lower()
    for needle, label in _PRIORITY_ALIASES.items():
        if re.search(rf"\b{re.escape(needle)}(?:\s+priority)?\b", lower):
            return label
    return ""


def _extract_project_key(text: str) -> str:
    label_value = _find_labeled_value(text, ["project", "project key", "jira project"])
    if label_value:
        return re.sub(r"[^A-Z0-9-]", "", label_value.upper())
    match = re.search(r"\b([A-Z][A-Z0-9]{1,9})-\d+\b", text)
    if match:
        return match.group(1)
    return ""


def _extract_purpose(text: str) -> str:
    labeled = _find_labeled_value(text, ["purpose", "goal", "objective", "why"])
    if labeled:
        return labeled
    match = re.search(r"\bso that\s+(.+)", text, re.I)
    if match:
        return match.group(1).strip().rstrip(".")
    match = re.search(r"\bto\s+([a-z].+)", text, re.I)
    if match and len(match.group(1).split()) >= 4:
        return match.group(1).strip().rstrip(".")
    return ""


def _first_sentence(text: str) -> str:
    sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    sentence = sentence.strip(" .")
    return sentence[:120]


def _normalize_summary(text: str) -> str:
    explicit = _find_labeled_value(text, ["summary", "title"])
    if explicit:
        return explicit[:255]
    sentence = _first_sentence(text)
    sentence = re.sub(r"^(create|new project|please|help)\s+", "", sentence, flags=re.I).strip()
    return sentence[:255]


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


class SlackJiraHelperService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register_event_delivery(self, event_id: str, event_type: str) -> bool:
        if not event_id:
            return True
        record = SlackEventDelivery(event_id=event_id, event_type=event_type)
        self.db.add(record)
        try:
            await self.db.commit()
            return True
        except IntegrityError:
            await self.db.rollback()
            return False

    async def get_or_create_request(
        self,
        *,
        workspace_id: str,
        channel_id: str,
        thread_ts: str,
        root_message_ts: str,
        requester_slack_id: str,
        requester_name: str,
    ) -> SlackJiraRequest:
        result = await self.db.execute(
            select(SlackJiraRequest).where(
                SlackJiraRequest.workspace_id == workspace_id,
                SlackJiraRequest.channel_id == channel_id,
                SlackJiraRequest.thread_ts == thread_ts,
            )
        )
        record = result.scalar_one_or_none()
        if record:
            return record
        record = SlackJiraRequest(
            workspace_id=workspace_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
            root_message_ts=root_message_ts,
            requester_slack_id=requester_slack_id,
            requester_name=requester_name,
            project_key=(settings.slack_jira_default_project_key or settings.jira_project_key).strip(),
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    def apply_message(self, record: SlackJiraRequest, text: str, *, slack_user_id: str, slack_user_name: str) -> None:
        cleaned = _clean_text(text)
        if not cleaned:
            return
        transcript_entry = f"[{slack_user_name or slack_user_id}] {cleaned}"
        record.transcript = "\n".join(filter(None, [record.transcript, transcript_entry]))
        explicit_summary = _find_labeled_value(cleaned, ["summary", "title"])
        if explicit_summary:
            record.summary = explicit_summary[:255]
        elif not record.summary:
            record.summary = _normalize_summary(cleaned)
        labeled_background = _find_labeled_value(cleaned, ["background", "description", "details"])
        if labeled_background:
            record.background = labeled_background
        elif not record.background and len(cleaned.split()) >= 10:
            record.background = cleaned
        purpose = _extract_purpose(cleaned)
        if purpose:
            record.purpose = purpose
        device = _extract_device(cleaned)
        if device:
            record.device = device
        priority = _extract_priority(cleaned)
        if priority:
            record.priority = priority
        project_key = _extract_project_key(cleaned)
        if project_key:
            record.project_key = project_key
        if record.status == "awaiting_approval" and self.is_change_request(cleaned):
            record.status = "collecting"
            record.approval_notes = cleaned

    def missing_fields(self, record: SlackJiraRequest) -> list[str]:
        missing: list[str] = []
        if not record.summary:
            missing.append("summary")
        if not record.background:
            missing.append("background")
        if not record.purpose:
            missing.append("purpose")
        if not record.device:
            missing.append("device")
        if not record.priority:
            missing.append("priority")
        return missing

    def summarize_intake(self, record: SlackJiraRequest) -> str:
        lines = [
            "Current intake:",
            f"- Summary: {record.summary or 'Missing'}",
            f"- Background: {record.background or 'Missing'}",
            f"- Purpose: {record.purpose or 'Missing'}",
            f"- Device: {record.device or 'Missing'}",
            f"- Priority: {record.priority or 'Missing'}",
            f"- Jira Project: {record.project_key or settings.jira_project_key}",
        ]
        return "\n".join(lines)

    def build_missing_info_prompt(self, record: SlackJiraRequest) -> str:
        missing = self.missing_fields(record)
        questions = {
            "summary": "What short summary should I use for the parent ticket?",
            "background": "What is the current behavior or problem that needs to change?",
            "purpose": "What is the business or user outcome we want from this work?",
            "device": "Which device or platform does this apply to: Android, iOS, Web, Backend, or API?",
            "priority": "What priority should I use: Critical, High, Medium, or Low?",
        }
        prompts = [questions[field] for field in missing]
        return self.summarize_intake(record) + "\n\nMissing information:\n- " + "\n- ".join(prompts)

    def _derive_acceptance_criteria(self, record: SlackJiraRequest) -> list[str]:
        criteria = [
            f"The requested behavior is implemented for {record.device}.",
            "The previous behavior is replaced or updated without obvious regressions.",
            f"The outcome supports this purpose: {record.purpose}.",
        ]
        return _dedupe_keep_order(criteria)

    def _derive_subtasks(self, record: SlackJiraRequest) -> list[dict[str, str]]:
        seed_text = " ".join(filter(None, [record.background, record.purpose]))
        segments = re.split(r"(?<=[.!?])\s+|(?:\badditionally\b)|(?:\balso\b)", seed_text, flags=re.I)
        task_titles: list[str] = []
        for segment in segments:
            cleaned = segment.strip(" .")
            if len(cleaned.split()) < 4:
                continue
            cleaned = cleaned[0].upper() + cleaned[1:]
            task_titles.append(cleaned[:120])
        task_titles = _dedupe_keep_order(task_titles)[:3]
        if not task_titles:
            task_titles = [f"Implement {record.summary}"]
        subtasks = [
            {
                "summary": title,
                "description": (
                    f"Deliver the required change for {record.device}.\n\n"
                    f"Context:\n{record.background}"
                ),
            }
            for title in task_titles
        ]
        subtasks.append(
            {
                "summary": f"QA validation for {record.summary}",
                "description": "Verify the implemented behavior, regression risks, and edge cases before release.",
            }
        )
        if re.search(r"\b(doc|spec|documentation|confluence|readme)\b", seed_text, re.I):
            subtasks.append(
                {
                    "summary": f"Update documentation for {record.summary}",
                    "description": "Document the agreed behavior and any operational notes.",
                }
            )
        return subtasks

    def build_ticket_proposal(self, record: SlackJiraRequest) -> dict[str, Any]:
        acceptance = self._derive_acceptance_criteria(record)
        parent_description = "\n".join(
            [
                f"Background:\n{record.background}",
                f"Purpose:\n{record.purpose}",
                f"Platform: {record.device}",
                f"Priority: {record.priority}",
                "Acceptance Criteria:",
                *[f"- {item}" for item in acceptance],
            ]
        )
        return {
            "project_key": record.project_key or settings.jira_project_key,
            "parent": {
                "issue_type": settings.jira_story_type,
                "summary": record.summary,
                "description": parent_description,
            },
            "subtasks": self._derive_subtasks(record),
        }

    def build_confluence_draft(self, record: SlackJiraRequest, proposal: dict[str, Any]) -> str:
        lines = [
            f"# {record.summary}",
            "",
            "## Background",
            record.background,
            "",
            "## Purpose",
            record.purpose,
            "",
            "## Scope Summary",
            f"- Platform: {record.device}",
            f"- Priority: {record.priority}",
            f"- Jira Project: {proposal['project_key']}",
            "",
            "## Proposed Ticket Breakdown",
            f"- Parent: {proposal['parent']['summary']}",
        ]
        lines.extend(f"- Subtask: {task['summary']}" for task in proposal["subtasks"])
        return "\n".join(lines)

    def format_proposal_for_slack(self, proposal: dict[str, Any], record: SlackJiraRequest) -> str:
        lines = [
            "Proposed JIRA structure:",
            f"Parent {proposal['parent']['issue_type']}: {proposal['parent']['summary']}",
            f"Project: {proposal['project_key']}",
            f"Priority: {record.priority}",
            f"Device: {record.device}",
            "",
            "Subtasks:",
        ]
        lines.extend(f"- {task['summary']}" for task in proposal["subtasks"])
        lines.extend(
            [
                "",
                "Reply with `approve` to create the tickets, or send changes in this thread and I will revise the proposal.",
            ]
        )
        return "\n".join(lines)

    async def save_record(self, record: SlackJiraRequest) -> SlackJiraRequest:
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def save_proposal(self, record: SlackJiraRequest, proposal: dict[str, Any]) -> SlackJiraRequest:
        record.proposal_json = json.dumps(proposal)
        record.confluence_draft = self.build_confluence_draft(record, proposal)
        record.status = "awaiting_approval"
        return await self.save_record(record)

    def load_proposal(self, record: SlackJiraRequest) -> dict[str, Any]:
        return json.loads(record.proposal_json) if record.proposal_json else self.build_ticket_proposal(record)

    def is_approval_message(self, text: str) -> bool:
        cleaned = _clean_text(text)
        return any(pattern.search(cleaned) for pattern in _APPROVE_PATTERNS)

    def is_change_request(self, text: str) -> bool:
        cleaned = _clean_text(text)
        return any(pattern.search(cleaned) for pattern in _CHANGE_PATTERNS)

    def is_user_allowed_to_approve(self, slack_user_id: str) -> bool:
        raw = settings.slack_jira_approver_ids.strip()
        if not raw:
            return True
        allowed = {item.strip() for item in raw.split(",") if item.strip()}
        return slack_user_id in allowed

    async def mark_approved(self, record: SlackJiraRequest, *, slack_user_id: str, slack_user_name: str) -> SlackJiraRequest:
        record.status = "approved"
        record.approved_by_slack_id = slack_user_id
        record.approved_by_name = slack_user_name
        return await self.save_record(record)

    async def mark_created(self, record: SlackJiraRequest, issue_keys: list[str]) -> SlackJiraRequest:
        record.status = "created"
        record.created_ticket_keys_json = json.dumps(issue_keys)
        return await self.save_record(record)

    async def post_thread_message(
        self,
        *,
        channel_id: str,
        thread_ts: str,
        text: str,
    ) -> None:
        token = settings.slack_bot_token.strip()
        if not token:
            logger.warning("Slack bot token is not configured; skipping outbound message")
            return
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "channel": channel_id,
                    "thread_ts": thread_ts,
                    "text": text,
                    "mrkdwn": True,
                },
            )
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                raise RuntimeError(f"Slack API error: {data.get('error', 'unknown_error')}")
