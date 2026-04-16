import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.config import settings
from src.models import Base
from src.services.slack_helper import SlackJiraHelperService, verify_slack_signature


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def test_verify_slack_signature_accepts_valid_request() -> None:
    body = b'{"type":"url_verification"}'
    timestamp = "1710000000"
    import hashlib
    import hmac

    digest = hmac.new(
        b"secret",
        f"v0:{timestamp}:{body.decode('utf-8')}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    assert verify_slack_signature(
        signing_secret="secret",
        timestamp=timestamp,
        body=body,
        signature=f"v0={digest}",
        now=1710000000,
    )


@pytest.mark.asyncio
async def test_service_collects_fields_and_builds_proposal(db_session) -> None:
    service = SlackJiraHelperService(db_session)
    record = await service.get_or_create_request(
        workspace_id="T1",
        channel_id="C1",
        thread_ts="1000.01",
        root_message_ts="1000.01",
        requester_slack_id="U1",
        requester_name="Alice",
    )

    service.apply_message(
        record,
        "Summary: Channel 45 should always show a pre-roll ad. "
        "Background: There is a 10 minute cooldown for pre-rolls today. "
        "Device: Android. Priority: High.",
        slack_user_id="U1",
        slack_user_name="Alice",
    )

    assert service.missing_fields(record) == ["purpose"]

    service.apply_message(
        record,
        "Purpose: ensure promotional ads are always delivered on channel 45.",
        slack_user_id="U1",
        slack_user_name="Alice",
    )

    proposal = service.build_ticket_proposal(record)
    saved = await service.save_proposal(record, proposal)

    assert saved.status == "awaiting_approval"
    assert proposal["parent"]["summary"] == "Channel 45 should always show a pre-roll ad."
    assert proposal["project_key"] == settings.jira_project_key
    assert any(task["summary"].startswith("QA validation") for task in proposal["subtasks"])
    assert "Purpose" in saved.confluence_draft


@pytest.mark.asyncio
async def test_service_allows_revision_updates_after_proposal(db_session) -> None:
    service = SlackJiraHelperService(db_session)
    record = await service.get_or_create_request(
        workspace_id="T1",
        channel_id="C1",
        thread_ts="2000.01",
        root_message_ts="2000.01",
        requester_slack_id="U1",
        requester_name="Alice",
    )
    record.summary = "Original summary"
    record.background = "Original background"
    record.purpose = "Original purpose"
    record.device = "Web"
    record.priority = "Medium"
    await service.save_record(record)

    proposal = service.build_ticket_proposal(record)
    await service.save_proposal(record, proposal)
    service.apply_message(
        record,
        "Change summary: Updated summary. Priority: High.",
        slack_user_id="U2",
        slack_user_name="Bob",
    )

    assert record.status == "collecting"
    assert record.summary == "Updated summary."
    assert record.priority == "High"


@pytest.mark.asyncio
async def test_service_respects_approver_whitelist(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "slack_jira_approver_ids", "U-PDM,U-LEAD")
    service = SlackJiraHelperService(db_session)

    assert service.is_user_allowed_to_approve("U-PDM")
    assert not service.is_user_allowed_to_approve("U-OTHER")


@pytest.mark.asyncio
async def test_mark_created_persists_ticket_keys(db_session) -> None:
    service = SlackJiraHelperService(db_session)
    record = await service.get_or_create_request(
        workspace_id="T1",
        channel_id="C1",
        thread_ts="3000.01",
        root_message_ts="3000.01",
        requester_slack_id="U1",
        requester_name="Alice",
    )

    await service.mark_created(record, ["TSA-101", "TSA-102"])

    assert record.status == "created"
    assert json.loads(record.created_ticket_keys_json) == ["TSA-101", "TSA-102"]
