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
import json
import logging
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.graph.graph import get_default_state
from src.middleware.auth import require_api_key

router = APIRouter(prefix="/api/v1", tags=["Chat"])
logger = logging.getLogger(__name__)


# ── Request schema ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=16_000)
    session_id: str | None = Field(
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


async def _stream_graph(
    request: Request,
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

    thread_config = {"configurable": {"thread_id": session_id}}

    # Load current state from checkpointer (or use defaults for new sessions)
    current = await graph.aget_state(thread_config)
    if current.values:
        input_payload = {
            "messages": [{"role": "user", "content": message}]
        }
    else:
        # New session — initialise full state
        initial = get_default_state()
        initial["messages"] = [{"role": "user", "content": message}]
        input_payload = initial

    try:
        async for chunk in graph.astream(
            input_payload,
            config=thread_config,
            stream_mode="custom",
        ):
            if isinstance(chunk, dict):
                yield _sse(chunk)

        # After stream ends check if graph suspended at an interrupt node
        snapshot = await graph.aget_state(thread_config)
        if snapshot.tasks:
            for task in snapshot.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    # Forward the interrupt payload so the frontend knows which form to show
                    yield _sse({"type": "interrupt", **task.interrupts[0].value})
                    break

    except Exception as exc:
        logger.exception("Graph error session=%s: %s", session_id, exc)
        yield _sse({"type": "error", "message": "Something went wrong. Please try again."})

    finally:
        yield _sse({"type": "turn_end", "session_id": session_id})


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post(
    "/chat",
    summary="Send a chat message (SSE streaming)",
    response_description="Server-Sent Events stream of typed events",
    dependencies=[Depends(require_api_key)],
)
async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
    """
    Send a user message and receive a streaming response.

    Returns an SSE stream. Each event is a JSON object with a `type` field.
    See module docstring for the full event contract.

    The `session_id` in the response `turn_end` event must be stored by the
    client and sent in subsequent requests to continue the same conversation.
    """
    session_id = body.session_id or str(uuid.uuid4())

    return StreamingResponse(
        _stream_graph(request, session_id, body.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering for SSE
            "Connection":        "keep-alive",
        },
    )
