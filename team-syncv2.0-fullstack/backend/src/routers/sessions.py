"""
Session and PRD endpoints.

GET  /api/v1/sessions/{session_id}        — current state of a session
GET  /api/v1/sessions/{session_id}/prd    — fetch the generated PRD markdown
POST /api/v1/sessions/{session_id}/resume — resume after a HITL interrupt (Phase 2)
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from src.middleware.auth import require_api_key

router = APIRouter(prefix="/api/v1/sessions", tags=["Sessions"])
logger = logging.getLogger(__name__)


# ── GET /sessions/{id} ────────────────────────────────────────────────────────

@router.get(
    "/{session_id}",
    summary="Get session state",
    dependencies=[Depends(require_api_key)],
)
async def get_session(session_id: str, request: Request) -> dict:
    """Return the current state snapshot for a session."""
    graph = request.app.state.graph
    config = {"configurable": {"thread_id": session_id}}

    snapshot = await graph.aget_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    state = snapshot.values
    return {
        "session_id":    session_id,
        "mode":          state.get("mode", "analyze"),
        "message_count": len(state.get("messages", [])),
        "prd_ready":     bool(state.get("prd_markdown")),
        "quality_score": state.get("quality_score", 0),
        "grade":         state.get("grade", ""),
        "file_name":     state.get("file_name", ""),
    }


# ── GET /sessions/{id}/prd ───────────────────────────────────────────────────

@router.get(
    "/{session_id}/prd",
    summary="Get generated PRD",
    dependencies=[Depends(require_api_key)],
)
async def get_prd(session_id: str, request: Request) -> dict:
    """Return the generated PRD markdown and quality metadata."""
    graph = request.app.state.graph
    config = {"configurable": {"thread_id": session_id}}

    snapshot = await graph.aget_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    state = snapshot.values
    if not state.get("prd_markdown"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PRD not generated yet for this session",
        )

    return {
        "session_id":    session_id,
        "file_name":     state.get("file_name", "prd.md"),
        "quality_score": state.get("quality_score", 0),
        "grade":         state.get("grade", ""),
        "markdown":      state.get("prd_markdown", ""),
    }


# ── POST /sessions/{id}/resume — Phase 2 stub ────────────────────────────────

class ResumePayload(BaseModel):
    form_type: str          # "email" | "jira"
    data: dict              # form field values


@router.post(
    "/{session_id}/resume",
    summary="Resume after HITL interrupt (Phase 2)",
    dependencies=[Depends(require_api_key)],
)
async def resume_session(
    session_id: str,
    body: ResumePayload,
    request: Request,               # noqa: ARG001
) -> dict:
    """
    Resume a suspended graph execution after the user submits a HITL form.
    Phase 2 implementation: inject form data and continue the graph.
    """
    # Phase 2: call graph.aupdate_state() then graph.ainvoke(None, ...)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="HITL resume is implemented in Phase 2",
    )
