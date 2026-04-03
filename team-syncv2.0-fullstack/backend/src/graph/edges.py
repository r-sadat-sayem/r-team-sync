"""
Routing functions (conditional edges).

route_entry     — called at START. Directs new invocations based on current mode.
route_after_analyze — called after the analyze node returns.
"""
from typing import Literal

from langgraph.graph import END

from src.graph.state import PRDState


def route_entry(state: PRDState) -> Literal["analyze", "generate_prd"]:
    """
    Entry point routing.

    If mode is already "generate" (set by a previous turn's analyze node)
    and we haven't produced a PRD yet, jump straight to generation.
    Otherwise run the analyze node as normal.

    This handles the case where the user sends one more message after Sam
    emits GENERATE_PRD: — the new message is appended to history, and then
    generate_prd runs immediately without re-running Sam.
    """
    if state.get("mode") == "generate" and not state.get("prd_markdown"):
        return "generate_prd"
    return "analyze"


def route_after_jira(state: PRDState) -> Literal["create_jira", "__end__"]:
    """
    After jira_interrupt: if the user typed 'approve', create tickets.
    Anything else (skip, empty, etc.) ends the workflow cleanly.
    """
    return "create_jira" if state.get("jira_decision", "").lower() == "approve" else END


def route_after_analyze(state: PRDState) -> Literal["generate_prd", "__end__"]:
    """
    After analyze runs, check whether it detected the GENERATE_PRD signal.

    - mode == "generate"  → Sam is done gathering; continue to PRD generation
                            in the SAME turn (no round-trip to the browser).
    - Otherwise           → Sam is still chatting; end this turn and wait
                            for the next user message.
    """
    if state.get("mode") == "generate" and not state.get("prd_markdown"):
        return "generate_prd"
    return END
