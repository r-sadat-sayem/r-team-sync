"""
Compiled LangGraph workflow.

Phase 1 graph (no HITL):
  START → [route_entry] → analyze → [route_after_analyze] → generate_prd → validate → END

Phase 2 will extend this by inserting email_interrupt and jira_interrupt nodes
between validate and END, and adding the resume route.

The graph is compiled once at app startup (in main.py lifespan) with a
PostgreSQL checkpointer. Each conversation is identified by thread_id = session_id.
"""
import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.graph.edges import route_after_analyze, route_after_jira, route_entry
from src.graph.nodes import (
    analyze,
    create_jira,
    email_interrupt,
    generate_prd,
    jira_interrupt,
    send_email,
    validate,
)
from src.graph.state import PRDState

logger = logging.getLogger(__name__)


def build_graph(checkpointer=None):
    """
    Build and compile the PRD workflow graph.

    Args:
        checkpointer: LangGraph checkpointer instance.
                      Pass None to use an in-memory saver (tests only).
                      Pass AsyncPostgresSaver for production.

    Returns:
        Compiled LangGraph graph ready to invoke.
    """
    builder = StateGraph(PRDState)

    # ── Nodes ─────────────────────────────────────────────────
    builder.add_node("analyze",         analyze)
    builder.add_node("generate_prd",    generate_prd)
    builder.add_node("validate",        validate)
    builder.add_node("email_interrupt", email_interrupt)
    builder.add_node("send_email",      send_email)
    builder.add_node("jira_interrupt",  jira_interrupt)
    builder.add_node("create_jira",     create_jira)

    # ── Edges ─────────────────────────────────────────────────
    builder.add_conditional_edges(
        START,
        route_entry,
        {"analyze": "analyze", "generate_prd": "generate_prd"},
    )

    builder.add_conditional_edges(
        "analyze",
        route_after_analyze,
        {"generate_prd": "generate_prd", END: END},
    )

    builder.add_edge("generate_prd",    "validate")
    builder.add_edge("validate",        "email_interrupt")   # HITL 1: email form
    builder.add_edge("email_interrupt", "send_email")
    builder.add_edge("send_email",      "jira_interrupt")    # HITL 2: JIRA approval

    builder.add_conditional_edges(
        "jira_interrupt",
        route_after_jira,
        {"create_jira": "create_jira", END: END},
    )

    builder.add_edge("create_jira", END)

    resolved_checkpointer = checkpointer if checkpointer is not None else MemorySaver()
    graph = builder.compile(checkpointer=resolved_checkpointer)

    logger.info("LangGraph PRD workflow compiled (Phase 2)")
    return graph


def get_default_state() -> PRDState:
    """Return a clean initial state for a new session."""
    return PRDState(
        messages=[],
        mode="analyze",
        context_summary="",
        prd_markdown="",
        quality_score=0,
        grade="",
        file_name="",
        recipient_email="",
        recipient_name="",
        jira_decision="",
        jira_assignee_email="",
        jira_notes="",
        epic_key="",
        epic_url="",
        task_keys=[],
    )
