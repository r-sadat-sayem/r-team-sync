"""
Session and PRD endpoints.

GET  /api/v1/sessions/{id}        — current session state
GET  /api/v1/sessions/{id}/prd    — fetch generated PRD markdown
POST /api/v1/sessions/{id}/resume — resume after HITL interrupt (SSE stream)
"""
import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.middleware.auth import require_api_key

router = APIRouter(prefix="/api/v1/sessions", tags=["Sessions"])
logger = logging.getLogger(__name__)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# ── GET /sessions/{id} ────────────────────────────────────────────────────────

@router.get("/{session_id}", dependencies=[Depends(require_api_key)])
async def get_session(session_id: str, request: Request) -> dict:
    graph = request.app.state.graph
    snapshot = await graph.aget_state({"configurable": {"thread_id": session_id}})
    if not snapshot.values:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    state = snapshot.values
    # Check if execution is currently suspended waiting for a form
    interrupt_payload = None
    if snapshot.tasks:
        for task in snapshot.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                interrupt_payload = task.interrupts[0].value
                break

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

@router.get("/{session_id}/prd", dependencies=[Depends(require_api_key)])
async def get_prd(session_id: str, request: Request) -> dict:
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
    session_id: str,
    form_data: dict,
) -> AsyncIterator[str]:
    from langgraph.types import Command

    graph  = request.app.state.graph
    config = {"configurable": {"thread_id": session_id}}

    try:
        async for chunk in graph.astream(
            Command(resume=form_data),
            config=config,
            stream_mode="custom",
        ):
            if isinstance(chunk, dict):
                yield _sse(chunk)

        # After streaming ends, check if the graph suspended again (next interrupt)
        snapshot = await graph.aget_state(config)
        if snapshot.tasks:
            for task in snapshot.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    yield _sse({"type": "interrupt", **task.interrupts[0].value})
                    break

    except Exception as exc:
        logger.exception("Resume error session=%s: %s", session_id, exc)
        yield _sse({"type": "error", "message": str(exc)})

    finally:
        yield _sse({"type": "turn_end", "session_id": session_id})


@router.post(
    "/{session_id}/resume",
    summary="Resume after HITL interrupt (SSE stream)",
    dependencies=[Depends(require_api_key)],
)
async def resume_session(
    session_id: str,
    body: ResumePayload,
    request: Request,
) -> StreamingResponse:
    """
    Resume a suspended graph execution with the user's form data.
    Returns an SSE stream — same event contract as POST /api/v1/chat.

    After email form: pass {"name": "...", "email": "..."}
    After JIRA form:  pass {"decision": "approve", "assignee_email": "...", "notes": "..."}
    """
    # Verify session exists and is actually interrupted
    graph    = request.app.state.graph
    snapshot = await graph.aget_state({"configurable": {"thread_id": session_id}})
    if not snapshot.values:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if not snapshot.tasks or not any(
        hasattr(t, "interrupts") and t.interrupts for t in snapshot.tasks
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is not currently waiting for input",
        )

    return StreamingResponse(
        _resume_stream(request, session_id, body.data),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )
