"""
Routing functions (conditional edges).

route_entry       — called at START. Directs invocations based on mode or direct commands.
route_after_analyze — called after analyze node returns.

Supported direct commands (when a PRD already exists):
  /jira | create jira   → jira_interrupt
  /testcases | generate test cases → generate_test_cases
"""
import logging
import re
from typing import Literal

from langgraph.graph import END

from src.graph.state import PRDState

logger = logging.getLogger(__name__)

_DIRECT_COMMANDS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^/jira\b|^create\s+jira\b|^generate\s+jira\b", re.I),                         "jira_interrupt"),
    (re.compile(r"^/testcases?\b|^generate\s+test\s+cases?\b|^create\s+test\s+cases?\b", re.I), "generate_test_cases"),
]


def _last_user_message(state: PRDState) -> str:
    """Return the text of the most recent user message, or ''."""
    for msg in reversed(state.get("messages", [])):
        if msg.get("role") == "user":
            return msg.get("content", "").strip()
    return ""


def route_entry(
    state: PRDState,
) -> Literal["analyze", "generate_prd_outline", "generate_prd",
             "generate_test_cases", "jira_interrupt"]:
    """
    Entry point routing for new user messages.

    Priority order:
    1. Direct commands (/jira, /testcases) when a PRD already exists.
    2. mode == "generate" with no PRD yet → outline / full generation flow.
    3. Default → Sam (analyze).
    """
    last_msg = _last_user_message(state)
    if last_msg and state.get("prd_markdown"):
        for pattern, target in _DIRECT_COMMANDS:
            if pattern.match(last_msg):
                logger.debug("route_entry: command detected → %s (msg=%r)", target, last_msg[:60])
                return target  # type: ignore[return-value]

    if state.get("mode") == "generate" and not state.get("prd_markdown"):
        if state.get("prd_outline"):
            logger.debug("route_entry: outline approved → generate_prd")
            return "generate_prd"
        logger.debug("route_entry: mode=generate, no outline → generate_prd_outline")
        return "generate_prd_outline"

    logger.debug(
        "route_entry: → analyze (mode=%s prd_exists=%s msg=%r)",
        state.get("mode"), bool(state.get("prd_markdown")), last_msg[:60],
    )
    return "analyze"


def route_after_jira(state: PRDState) -> Literal["create_jira", "__end__"]:
    """After jira_interrupt: if approved, create tickets."""
    return "create_jira" if state.get("jira_decision", "").lower() == "approve" else END


def route_after_analyze(state: PRDState) -> Literal["generate_prd_outline", "__end__"]:
    """After analyze: if GENERATE_PRD was signalled, proceed to outline."""
    if state.get("mode") == "generate" and not state.get("prd_markdown"):
        return "generate_prd_outline"
    return END


def route_after_outline(state: PRDState) -> Literal["generate_prd", "analyze"]:
    """After prd_outline_interrupt resumes: approved → generate_prd, else → analyze."""
    return "generate_prd" if state.get("mode") == "generate" else "analyze"
