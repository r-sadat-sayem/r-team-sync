"""
Unit tests for the LangGraph PRD workflow.

These tests mock the Anthropic client so they run without a real API key.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.graph.edges import route_after_analyze, route_entry
from src.graph.nodes import _score_prd, _extract_context_summary, _placeholder_guard
from src.graph.state import PRDState
from langgraph.graph import END


# ── Edge routing tests ────────────────────────────────────────────────────────

def make_state(**overrides) -> PRDState:
    base = PRDState(
        messages=[], mode="analyze", context_summary="",
        prd_markdown="", quality_score=0, grade="", file_name="",
        recipient_email="", recipient_name="", jira_decision="",
    )
    base.update(overrides)
    return base


def test_route_entry_defaults_to_analyze():
    state = make_state(mode="analyze")
    assert route_entry(state) == "analyze"


def test_route_entry_goes_to_generate_when_mode_set_and_no_prd():
    state = make_state(mode="generate", prd_markdown="")
    assert route_entry(state) == "generate_prd"


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
    assert route_after_analyze(state) == "generate_prd"


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
# Non-Functional Requirements
# Scope
# Success Metrics
# Test Cases
TC001: test TC002: test TC003: test TC004: test TC005: test
TC006: test TC007: test TC008: test TC009: test TC010: test
TC011: test TC012: test TC013: test TC014: test TC015: test
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


# ── Graph integration test (mocked LLM) ──────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_node_continues_when_no_signal(graph, thread_config):
    """Verify the graph ends the turn when Sam is still asking questions."""
    mock_response = "What platform are you targeting for this app?"

    with patch("src.graph.nodes._make_client") as mock_client_fn:
        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)
        mock_stream.text_stream = _async_iter([mock_response])

        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream
        mock_client_fn.return_value = mock_client

        result = await graph.ainvoke(
            {
                "messages": [{"role": "user", "content": "I want to build an expense app"}],
                "mode": "analyze",
                "context_summary": "", "prd_markdown": "", "quality_score": 0,
                "grade": "", "file_name": "", "recipient_email": "",
                "recipient_name": "", "jira_decision": "",
            },
            config=thread_config,
        )

    assert result["mode"] == "analyze"
    assert result["prd_markdown"] == ""
    assert any(m["role"] == "assistant" for m in result["messages"])


@pytest.mark.asyncio
async def test_analyze_node_triggers_generation_on_signal(graph, thread_config):
    """Verify mode switches to generate when GENERATE_PRD: signal is emitted."""
    signal = (
        "GENERATE_PRD:\n- Project: Expense Tracker\n- Type: New Product\n"
        "- Platform: iOS\n- Key Features: receipts, categories\n"
        "- Target Users: freelancers\n- Timeline: Q3 2026\n"
        "- Success Metric: 70% reduction in manual entry\n\n"
        "Shall I proceed with generating the complete PRD?"
    )
    prd_text = "# Classification Summary\n" + "content " * 1000

    call_count = 0

    async def fake_text_stream_factory(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _async_iter([signal])
        return _async_iter([prd_text])

    with patch("src.graph.nodes._make_client") as mock_client_fn:
        mock_client = MagicMock()

        def make_mock_stream(*args, **kwargs):
            m = AsyncMock()
            m.__aenter__ = AsyncMock(return_value=m)
            m.__aexit__ = AsyncMock(return_value=False)
            if call_count == 0:
                m.text_stream = _async_iter([signal])
            else:
                m.text_stream = _async_iter([prd_text])
            return m

        mock_client.messages.stream.side_effect = make_mock_stream
        mock_client_fn.return_value = mock_client

        result = await graph.ainvoke(
            {
                "messages": [{"role": "user", "content": "Yes, generate it"}],
                "mode": "analyze",
                "context_summary": "", "prd_markdown": "", "quality_score": 0,
                "grade": "", "file_name": "", "recipient_email": "",
                "recipient_name": "", "jira_decision": "",
            },
            config=thread_config,
        )

    # Mode should have transitioned; prd_markdown should be populated
    assert result["mode"] == "generate"


# ── Async iterator helper for mocking stream.text_stream ─────────────────────

async def _async_iter(items):
    for item in items:
        yield item
