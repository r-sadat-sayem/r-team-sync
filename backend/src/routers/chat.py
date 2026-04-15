from __future__ import annotations

"""
POST /api/v1/chat

Accepts a user message, runs the LangGraph workflow, and streams
events back to the browser as Server-Sent Events (SSE).

SSE event stream contract (one JSON object per `data:` line):

  {"type": "token",        "content": "..."}
      Streaming token from the LLM. Append to the current message bubble.

  {"type": "status",       "message": "..."}
      Progress label (e.g. "Generating PRD..."). Show as a status indicator.

  {"type": "prd_complete", "score": 87, "grade": "B", "file_name": "...md"}
      PRD has been validated. Show score badge and download button.

  {"type": "interrupt",    "form": "email"|"jira", "resume_url": "..."}
      (Phase 2) Execution suspended — show the appropriate inline form.

  {"type": "turn_end",     "session_id": "..."}
      This turn is finished. Hide the typing indicator.

  {"type": "error",        "message": "..."}
      Something went wrong. Show an error toast.
"""
import base64
import json
import logging
import uuid
from typing import AsyncIterator, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db_session
from src.graph.graph import get_default_state
from src.middleware.auth import require_current_user
from src.models import AppSession, User

router = APIRouter(prefix="/api/v1", tags=["Chat"])
logger = logging.getLogger(__name__)


# ── Request schema ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=16_000)
    session_id: Optional[str] = Field(
        default=None,
        description="Omit to start a new session. Include to continue an existing one.",
    )

    model_config = {"json_schema_extra": {
        "example": {
            "message": "I want to build a mobile expense tracker for small businesses.",
            "session_id": None,
        }
    }}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sse(payload: dict) -> str:
    """Format a dict as a single SSE data line."""
    return f"data: {json.dumps(payload)}\n\n"


def _pending_interrupt_payload(snapshot) -> Optional[dict]:
    """
    Read the current frontend interrupt payload from the graph snapshot.

    Handles two suspend patterns used in this codebase:

    1. State-field pattern (prd_outline_interrupt, post_prd_interrupt):
       The node sets state["pending_interrupt"] = {...} and goes to END.
       The payload lives in snapshot.values["pending_interrupt"].

    2. Native LangGraph interrupt (email_interrupt, jira_interrupt):
       The node calls `interrupt(payload)` which truly suspends execution.
       The payload lives in snapshot.tasks[i].interrupts[j].value.
    """
    # 1. State-field based interrupt
    values = getattr(snapshot, "values", None) or {}
    payload = values.get("pending_interrupt")
    if isinstance(payload, dict) and payload.get("form"):
        return payload

    # 2. Native LangGraph interrupt
    for task in getattr(snapshot, "tasks", []):
        for intr in getattr(task, "interrupts", []):
            val = getattr(intr, "value", None)
            if isinstance(val, dict) and val.get("form"):
                return val

    return None


async def _stream_graph(
    request: Request,
    user_id: int,
    session_id: str,
    message: str,
) -> AsyncIterator[str]:
    """
    Core generator: run the graph for one turn and yield SSE strings.

    LangGraph config:
      thread_id  — maps to session_id; the checkpointer uses this to load/save state.
      stream_mode "custom" — surfaces events written by nodes via get_stream_writer().
    """
    graph = request.app.state.graph

    thread_config = {"configurable": {"thread_id": session_id, "user_id": str(user_id)}}

    # Load current state from checkpointer (or use defaults for new sessions)
    current = await graph.aget_state(thread_config)
    if current.values and current.values.get("messages"):
        # Existing session with conversation history — just append new message
        input_payload = {
            "messages": [{"role": "user", "content": message}]
        }
    else:
        # New session (or session with only uploaded docs, no messages yet)
        initial = get_default_state()
        initial["messages"] = [{"role": "user", "content": message}]
        input_payload = initial
        # uploaded_documents already in checkpoint (if any) will be merged by _append reducer

    logger.debug("stream_graph: session=%s user=%d msg_len=%d", session_id, user_id, len(message))

    try:
        async for chunk in graph.astream(
            input_payload,
            config=thread_config,
            stream_mode="custom",
        ):
            if isinstance(chunk, dict):
                event_type = chunk.get("type", "unknown")
                if event_type == "token":
                    logger.debug("SSE token: %d chars", len(chunk.get("content", "")))
                else:
                    logger.debug("SSE event: %s", chunk)
                yield _sse(chunk)

        # After stream ends check whether the graph paused for frontend input.
        snapshot = await graph.aget_state(thread_config)
        interrupt_payload = _pending_interrupt_payload(snapshot)
        logger.debug(
            "snapshot next=%s tasks=%d pending_interrupt=%s",
            snapshot.next,
            len(snapshot.tasks),
            interrupt_payload.get("form") if interrupt_payload else None,
        )
        if interrupt_payload:
            logger.debug("SSE interrupt: form=%s", interrupt_payload.get("form"))
            yield _sse({"type": "interrupt", **interrupt_payload})

    except Exception as exc:
        logger.exception("Graph error session=%s: %s", session_id, exc)
        yield _sse({"type": "error", "message": "Something went wrong. Please try again."})

    finally:
        logger.debug("stream_graph: turn_end session=%s", session_id)
        yield _sse({"type": "turn_end", "session_id": session_id})


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post(
    "/chat",
    summary="Send a chat message (SSE streaming)",
    response_description="Server-Sent Events stream of typed events",
)
async def chat(
    body: ChatRequest,
    request: Request,
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """
    Send a user message and receive a streaming response.

    Returns an SSE stream. Each event is a JSON object with a `type` field.
    See module docstring for the full event contract.

    The `session_id` in the response `turn_end` event must be stored by the
    client and sent in subsequent requests to continue the same conversation.
    """
    session_id = body.session_id or str(uuid.uuid4())

    result = await db.execute(select(AppSession).where(AppSession.session_id == session_id))
    app_session = result.scalar_one_or_none()
    if app_session and app_session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    if not app_session:
        db.add(AppSession(session_id=session_id, user_id=current_user.id))
        await db.commit()

    return StreamingResponse(
        _stream_graph(request, current_user.id, session_id, body.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering for SSE
            "Connection":        "keep-alive",
        },
    )


# ── Upload files ──────────────────────────────────────────────────────────────

_ALLOWED_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/json",
    "text/xml",
    "application/xml",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}
_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post(
    "/chat/upload",
    summary="Upload documents or images for requirements context",
)
async def upload_files(
    request: Request,
    session_id: str = Form(...),
    files: List[UploadFile] = File(...),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Process uploaded files and attach them to the session's LangGraph state.

    Supported: PDF, TXT, MD (text extracted), PNG/JPEG/WEBP/GIF (base64 encoded).
    Returns a list of previews for the frontend to display as chips.
    """
    graph = request.app.state.graph

    processed: list[dict] = []
    for upload in files:
        content_type = (upload.content_type or "").split(";")[0].strip()
        if content_type not in _ALLOWED_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type: {content_type}. Allowed: PDF, TXT, MD, JSON, XML, PNG, JPEG, WEBP, GIF.",
            )

        raw = await upload.read()
        if len(raw) > _MAX_FILE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"{upload.filename} exceeds the 10 MB limit.",
            )

        doc: dict = {"filename": upload.filename or "unnamed", "content_type": content_type}

        if content_type == "application/pdf":
            try:
                import io
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(raw))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception as exc:
                logger.warning("PDF extraction failed for %s: %s", upload.filename, exc)
                text = ""
            doc["text"] = text
            doc["preview"] = text[:200].replace("\n", " ") if text else "(no text extracted)"

        elif content_type in ("text/plain", "text/markdown", "application/json", "text/xml", "application/xml"):
            text = raw.decode("utf-8", errors="replace")
            doc["text"] = text
            doc["preview"] = text[:200].replace("\n", " ")

        else:
            # Image — base64 encode for Claude vision
            doc["image_data"] = base64.b64encode(raw).decode()
            doc["preview"] = f"[image: {upload.filename}]"

        processed.append(doc)

    # Persist to LangGraph state so all subsequent nodes see the documents
    config = {"configurable": {"thread_id": session_id, "user_id": str(current_user.id)}}
    await graph.aupdate_state(config, {"uploaded_documents": processed})

    logger.info(
        "upload_files: session=%s user=%d files=%d",
        session_id, current_user.id, len(processed),
    )
    return {
        "documents": [
            {"filename": d["filename"], "content_type": d["content_type"], "preview": d["preview"]}
            for d in processed
        ]
    }
