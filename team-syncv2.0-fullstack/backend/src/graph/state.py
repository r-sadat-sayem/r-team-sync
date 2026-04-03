"""
PRDState — the single source of truth passed between every graph node.

Messages are stored in Anthropic format (plain dicts) so we call the SDK
without any conversion layer. The `append_messages` reducer accumulates
history across turns; LangGraph merges returned messages on each invocation.
"""
from typing import Annotated, Literal, TypedDict


def _append(left: list, right: list) -> list:
    """Simple append reducer — each node returns only the new messages it adds."""
    return left + right


class PRDState(TypedDict):
    # Conversation history in Anthropic format: [{"role": "user"|"assistant", "content": "..."}]
    messages: Annotated[list[dict], _append]

    # Workflow mode. Drives routing at the START and after analyze.
    #   analyze   — Sam is gathering requirements
    #   generate  — PRD generation is in progress (set when GENERATE_PRD: detected)
    mode: Literal["analyze", "generate"]

    # Extracted when Sam emits the GENERATE_PRD: signal.
    # Passed as context to the DevBridge generate node.
    context_summary: str

    # Set by the validate node.
    prd_markdown: str
    quality_score: int
    grade: str
    file_name: str

    # Set by the email HITL gate (Phase 2).
    recipient_email: str
    recipient_name: str

    # Set by the JIRA HITL gate (Phase 2).
    jira_decision: str   # "approve" | "skip"
