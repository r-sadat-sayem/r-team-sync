"""
Session and PRD endpoints.

GET  /api/v1/sessions/{id}        — current session state
GET  /api/v1/sessions/{id}/prd    — fetch generated PRD markdown
POST /api/v1/sessions/{id}/resume — resume after HITL interrupt (SSE stream)
"""
import json
import logging
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db_session
from src.middleware.auth import require_current_user, require_session_owner
from src.models import User

router = APIRouter(prefix="/api/v1/sessions", tags=["Sessions"])
logger = logging.getLogger(__name__)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _pending_interrupt_payload(snapshot) -> Optional[dict]:
    values = getattr(snapshot, "values", None) or {}
    payload = values.get("pending_interrupt")
    return payload if isinstance(payload, dict) and payload.get("form") else None


def _build_resume_command(interrupt_payload: dict, form_data: dict):
    from langgraph.types import Command

    form = interrupt_payload.get("form")

    if form == "prd_outline_form":
        decision = form_data.get("decision", "approve").lower().strip()
        if decision == "approve":
            return Command(
                update={"pending_interrupt": None, "outline_feedback": ""},
                goto="generate_prd",
            )

        feedback = form_data.get("feedback", "").strip()
        return Command(
            update={
                "pending_interrupt": None,
                "mode": "analyze",
                "prd_outline": "",
                "outline_feedback": feedback,
                "messages": [{
                    "role": "user",
                    "content": f"Please revise the PRD plan. Feedback: {feedback}",
                }],
            },
            goto="analyze",
        )

    if form == "email_form":
        return Command(
            update={
                "pending_interrupt": None,
                "recipient_name": form_data.get("name", "").strip(),
                "recipient_email": form_data.get("email", "").strip(),
            },
            goto="send_email",
        )

    if form in {"jira_form", "jira_auto_confirm"}:
        decision = form_data.get(
            "decision",
            "approve" if form == "jira_auto_confirm" else "skip",
        ).lower().strip()
        project_key = (
            form_data.get("project_key", "").strip()
            or interrupt_payload.get("default_project", "").strip()
        )
        update = {
            "pending_interrupt": None,
            "jira_decision": decision,
            "jira_assignee_email": form_data.get("assignee_email", "").strip(),
            "jira_notes": form_data.get("notes", "").strip(),
            "jira_project_key": project_key,
        }
        if decision == "approve":
            return Command(update=update, goto="create_jira")
        return Command(update=update)

    if form == "post_prd_actions":
        action = form_data.get("action", "done").lower().strip()
        update = {"pending_interrupt": None}
        if action == "email":
            return Command(update=update, goto="email_interrupt")
        if action == "test_cases":
            return Command(update=update, goto="generate_test_cases")
        if action == "jira":
            return Command(update=update, goto="jira_interrupt")
        return Command(update=update)  # action == "done" — just clear interrupt

    raise ValueError(f"Unsupported interrupt form: {form}")


# ── GET /sessions/{id} ────────────────────────────────────────────────────────

@router.get("/{session_id}")
async def get_session(
    session_id: str,
    request: Request,
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    await require_session_owner(session_id, current_user, db)
    graph = request.app.state.graph
    snapshot = await graph.aget_state({"configurable": {"thread_id": session_id}})
    if not snapshot.values:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    state = snapshot.values
    interrupt_payload = _pending_interrupt_payload(snapshot)

    return {
        "session_id":       session_id,
        "mode":             state.get("mode", "analyze"),
        "message_count":    len(state.get("messages", [])),
        "prd_ready":        bool(state.get("prd_markdown")),
        "quality_score":    state.get("quality_score", 0),
        "grade":            state.get("grade", ""),
        "file_name":        state.get("file_name", ""),
        "interrupted":      interrupt_payload is not None,
        "interrupt":        interrupt_payload,
        "epic_key":         state.get("epic_key", ""),
        "epic_url":         state.get("epic_url", ""),
    }


# ── GET /sessions/{id}/prd ───────────────────────────────────────────────────

@router.get("/{session_id}/prd")
async def get_prd(
    session_id: str,
    request: Request,
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    await require_session_owner(session_id, current_user, db)
    graph = request.app.state.graph
    snapshot = await graph.aget_state({"configurable": {"thread_id": session_id}})
    if not snapshot.values:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    state = snapshot.values
    if not state.get("prd_markdown"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PRD not generated yet")

    return {
        "session_id":    session_id,
        "file_name":     state.get("file_name", "prd.md"),
        "quality_score": state.get("quality_score", 0),
        "grade":         state.get("grade", ""),
        "markdown":      state.get("prd_markdown", ""),
    }


# ── GET /sessions/{id}/download ──────────────────────────────────────────────

@router.get("/{session_id}/download")
async def download_prd(
    session_id: str,
    request: Request,
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """Download the generated PRD as a .md file."""
    await require_session_owner(session_id, current_user, db)
    graph    = request.app.state.graph
    snapshot = await graph.aget_state({"configurable": {"thread_id": session_id}})
    if not snapshot.values:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    state    = snapshot.values
    markdown = state.get("prd_markdown", "")
    if not markdown:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PRD not generated yet")

    file_name = state.get("file_name") or f"PRD_{session_id[:8]}.md"
    return Response(
        content=markdown.encode("utf-8"),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


# ── POST /sessions/{id}/resume ────────────────────────────────────────────────

class ResumePayload(BaseModel):
    """
    Form data submitted by the user to resume a suspended graph.

    For email_form:  {"name": "...", "email": "..."}
    For jira_form:   {"decision": "approve", "assignee_email": "...", "notes": "..."}
    """
    data: dict


async def _resume_stream(
    request: Request,
    user_id: int,
    session_id: str,
    form_data: dict,
) -> AsyncIterator[str]:
    from langgraph.types import Command

    graph  = request.app.state.graph
    config = {"configurable": {"thread_id": session_id, "user_id": str(user_id)}}

    try:
        snapshot = await graph.aget_state(config)
        interrupt_payload = _pending_interrupt_payload(snapshot)
        if not interrupt_payload:
            raise ValueError("Session is not currently waiting for input")

        async for chunk in graph.astream(
            _build_resume_command(interrupt_payload, form_data),
            config=config,
            stream_mode="custom",
        ):
            if isinstance(chunk, dict):
                yield _sse(chunk)

        # After streaming ends, check if the graph suspended again (next interrupt)
        snapshot = await graph.aget_state(config)
        next_interrupt = _pending_interrupt_payload(snapshot)
        if next_interrupt:
            yield _sse({"type": "interrupt", **next_interrupt})

    except Exception as exc:
        logger.exception("Resume error session=%s: %s", session_id, exc)
        yield _sse({"type": "error", "message": str(exc)})

    finally:
        yield _sse({"type": "turn_end", "session_id": session_id})


@router.post(
    "/{session_id}/resume",
    summary="Resume after HITL interrupt (SSE stream)",
)
async def resume_session(
    session_id: str,
    body: ResumePayload,
    request: Request,
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """
    Resume a suspended graph execution with the user's form data.
    Returns an SSE stream — same event contract as POST /api/v1/chat.

    After email form: pass {"name": "...", "email": "..."}
    After JIRA form:  pass {"decision": "approve", "assignee_email": "...", "notes": "..."}
    """
    await require_session_owner(session_id, current_user, db)
    # Verify session exists and is actually interrupted
    graph    = request.app.state.graph
    snapshot = await graph.aget_state({"configurable": {"thread_id": session_id}})
    if not snapshot.values:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if not _pending_interrupt_payload(snapshot):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is not currently waiting for input",
        )

    return StreamingResponse(
        _resume_stream(request, current_user.id, session_id, body.data),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )
