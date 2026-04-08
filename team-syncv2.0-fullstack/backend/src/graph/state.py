"""
PRDState — the single source of truth passed between every graph node.

Messages are stored in Anthropic format (plain dicts) so we call the SDK
without any conversion layer. The `append_messages` reducer accumulates
history across turns; LangGraph merges returned messages on each invocation.
"""
from typing import Any, Annotated, Literal, Optional, TypedDict


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
    context_summary: str

    # Set by the validate node.
    prd_markdown: str
    quality_score: int
    grade: str
    file_name: str

    # Set by the email HITL gate.
    recipient_email: str
    recipient_name: str

    # Set by the JIRA HITL gate.
    jira_decision: str
    jira_assignee_email: str
    jira_notes: str
    jira_project_key: str

    # Set by generate_prd_outline node.
    prd_outline: str
    outline_feedback: str
    pending_interrupt: Optional[dict[str, Any]]

    # Uploaded documents/images attached for requirements context.
    uploaded_documents: Annotated[list[dict], _append]

    # Kept for backwards compatibility (not used in new flow).
    jira_tickets_markdown: str

    # Set by generate_test_cases node — Happy Path + Edge Case TCs.
    test_cases_markdown: str

    # Set by validate_test_cases node.
    test_cases_file_name: str

    # Tracks which post-PRD actions have been completed: ["email", "test_cases", "jira"]
    actions_taken: Annotated[list[str], _append]

    # Set by create_jira node.
    epic_key: str
    epic_url: str
    task_keys: Annotated[list[str], _append]
