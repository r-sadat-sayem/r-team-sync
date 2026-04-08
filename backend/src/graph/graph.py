"""
Compiled LangGraph workflow.

New flow (Phase 3 — multi-agent approval):
  analyze → generate_prd_outline → prd_outline_interrupt → END
  [resume approve] → generate_prd → validate → post_prd_interrupt → END
  [resume action=email]       → email_interrupt → END
    [resume email form]       → send_email → post_prd_interrupt → END
  [resume action=test_cases]  → generate_test_cases → validate_test_cases → post_prd_interrupt → END
  [resume action=jira]        → jira_interrupt → END
    [resume jira approve]     → create_jira → END
  [resume action=done]        → END
"""
import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.graph.edges import route_after_analyze, route_entry
from src.graph.nodes import (
    analyze,
    create_jira,
    email_interrupt,
    generate_prd,
    generate_prd_outline,
    generate_test_cases,
    jira_interrupt,
    post_prd_interrupt,
    prd_outline_interrupt,
    send_email,
    validate,
    validate_test_cases,
)
from src.graph.state import PRDState

logger = logging.getLogger(__name__)


def build_graph(checkpointer=None):
    builder = StateGraph(PRDState)

    # ── Nodes ─────────────────────────────────────────────────
    builder.add_node("analyze",               analyze)
    builder.add_node("generate_prd_outline",  generate_prd_outline)
    builder.add_node("prd_outline_interrupt", prd_outline_interrupt)
    builder.add_node("generate_prd",          generate_prd)
    builder.add_node("validate",              validate)
    builder.add_node("post_prd_interrupt",    post_prd_interrupt)
    builder.add_node("generate_test_cases",   generate_test_cases)
    builder.add_node("validate_test_cases",   validate_test_cases)
    builder.add_node("email_interrupt",       email_interrupt)
    builder.add_node("send_email",            send_email)
    builder.add_node("jira_interrupt",        jira_interrupt)
    builder.add_node("create_jira",           create_jira)

    # ── Edges ─────────────────────────────────────────────────
    builder.add_conditional_edges(
        START,
        route_entry,
        {
            "analyze":              "analyze",
            "generate_prd_outline": "generate_prd_outline",
            "generate_prd":         "generate_prd",
            "generate_test_cases":  "generate_test_cases",
            "jira_interrupt":       "jira_interrupt",
        },
    )

    builder.add_conditional_edges(
        "analyze",
        route_after_analyze,
        {"generate_prd_outline": "generate_prd_outline", END: END},
    )

    builder.add_edge("generate_prd_outline",  "prd_outline_interrupt")
    builder.add_edge("prd_outline_interrupt",  END)

    builder.add_edge("generate_prd",          "validate")
    builder.add_edge("validate",              "post_prd_interrupt")
    builder.add_edge("post_prd_interrupt",     END)

    builder.add_edge("email_interrupt",        END)
    builder.add_edge("send_email",            "post_prd_interrupt")

    builder.add_edge("generate_test_cases",   "validate_test_cases")
    builder.add_edge("validate_test_cases",   "post_prd_interrupt")

    builder.add_edge("jira_interrupt",         END)
    builder.add_edge("create_jira",            END)

    resolved_checkpointer = checkpointer if checkpointer is not None else MemorySaver()
    graph = builder.compile(checkpointer=resolved_checkpointer)

    logger.info("LangGraph PRD workflow compiled (Phase 3 — multi-agent approval)")
    return graph


def get_default_state() -> PRDState:
    """Return a clean initial state for a new session."""
    return PRDState(
        messages=[],
        mode="analyze",
        context_summary="",
        prd_outline="",
        outline_feedback="",
        pending_interrupt=None,
        uploaded_documents=[],
        prd_markdown="",
        jira_tickets_markdown="",
        test_cases_markdown="",
        test_cases_file_name="",
        actions_taken=[],
        quality_score=0,
        grade="",
        file_name="",
        recipient_email="",
        recipient_name="",
        jira_decision="",
        jira_assignee_email="",
        jira_notes="",
        jira_project_key="",
        epic_key="",
        epic_url="",
        task_keys=[],
    )
