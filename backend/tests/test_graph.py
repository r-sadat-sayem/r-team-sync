"""
Unit tests for the LangGraph PRD workflow.

These tests cover routing and pause/resume helpers without a real API key.
"""

from src.graph.edges import route_after_analyze, route_entry
from src.graph.nodes import _score_prd, _extract_context_summary, _placeholder_guard
from src.graph.graph import get_default_state
from src.routers.sessions import _build_resume_command
from src.graph.state import PRDState
from langgraph.graph import END


# ── Edge routing tests ────────────────────────────────────────────────────────

def make_state(**overrides) -> PRDState:
    base = get_default_state()
    base.update(overrides)
    return base


def test_route_entry_defaults_to_analyze():
    state = make_state(mode="analyze")
    assert route_entry(state) == "analyze"


def test_route_entry_goes_to_generate_when_mode_set_and_no_prd():
    state = make_state(mode="generate", prd_markdown="")
    assert route_entry(state) == "generate_prd_outline"


def test_route_entry_stays_on_analyze_if_prd_already_exists():
    # If PRD was already generated (e.g. user sends another message after),
    # don't re-generate.
    state = make_state(mode="generate", prd_markdown="# PRD content here")
    assert route_entry(state) == "analyze"


def test_route_after_analyze_ends_when_still_chatting():
    state = make_state(mode="analyze")
    assert route_after_analyze(state) == END


def test_route_after_analyze_goes_to_generate_when_signal_detected():
    state = make_state(mode="generate", prd_markdown="")
    assert route_after_analyze(state) == "generate_prd_outline"


def test_route_after_analyze_ends_if_prd_already_present():
    state = make_state(mode="generate", prd_markdown="# PRD")
    assert route_after_analyze(state) == END


# ── PRD quality scoring ───────────────────────────────────────────────────────

MINIMAL_PRD = """\
# Classification Summary
# Product Overview
# Goals
# User Stories / Functional Requirements
**FR1**: As a user I want something.
**FR2**: As a user I want something else.
**FR3**: As a manager I want reporting.
**FR4**: As an admin I want permissions.
**FR5**: As a user I want notifications.
# Non-Functional Requirements
# Scope
# Success Metrics
# Technical Considerations
# Timeline and Milestones
""" + "x" * 5100  # push length above 5000


def test_score_prd_good_document():
    score, grade = _score_prd(MINIMAL_PRD)
    assert score >= 80
    assert grade in ("A", "B")


def test_score_prd_empty_document():
    score, grade = _score_prd("")
    assert score == 0
    assert grade == "F"


def test_score_prd_partial_document():
    partial = "# Classification Summary\n# Product Overview\n# Goals\n"
    score, grade = _score_prd(partial)
    assert 0 < score < 80


# ── Helper functions ──────────────────────────────────────────────────────────

def test_extract_context_summary():
    text = (
        "Sure! Here is the summary:\n\nGENERATE_PRD:\n"
        "- Project: Expense Tracker\n- Type: New Product\n\n"
        "Shall I proceed with generating the complete PRD?"
    )
    ctx = _extract_context_summary(text)
    assert "Expense Tracker" in ctx
    assert "Shall I proceed" not in ctx


def test_placeholder_guard_detects_myapp():
    assert _placeholder_guard("Project: MyApp") is True


def test_placeholder_guard_passes_real_name():
    assert _placeholder_guard("Project: Expense Tracker Pro") is False


# ── Resume command helpers ───────────────────────────────────────────────────

def test_resume_command_approving_outline_goes_to_generate_prd():
    cmd = _build_resume_command({"form": "prd_outline_form"}, {"decision": "approve"})

    assert cmd.goto == "generate_prd"
    assert cmd.update["pending_interrupt"] is None
    assert cmd.update["outline_feedback"] == ""


def test_resume_command_revising_outline_returns_to_analyze():
    cmd = _build_resume_command(
        {"form": "prd_outline_form"},
        {"decision": "revise", "feedback": "Add admin approval flow."},
    )

    assert cmd.goto == "analyze"
    assert cmd.update["mode"] == "analyze"
    assert cmd.update["prd_outline"] == ""
    assert cmd.update["pending_interrupt"] is None
    assert "Add admin approval flow." in cmd.update["messages"][0]["content"]


def test_resume_command_email_form_goes_to_send_email():
    cmd = _build_resume_command(
        {"form": "email_form"},
        {"name": "Taylor", "email": "taylor@example.com"},
    )

    assert cmd.goto == "send_email"
    assert cmd.update["recipient_name"] == "Taylor"
    assert cmd.update["recipient_email"] == "taylor@example.com"
    assert cmd.update["pending_interrupt"] is None


def test_resume_command_jira_skip_only_updates_state():
    cmd = _build_resume_command(
        {"form": "jira_form"},
        {"decision": "skip", "project_key": "TS"},
    )

    assert cmd.goto == ()
    assert cmd.update["jira_decision"] == "skip"
    assert cmd.update["jira_project_key"] == "TS"
    assert cmd.update["pending_interrupt"] is None
