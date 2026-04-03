"""
Graph nodes — each function maps (state) → partial state update dict.

Streaming: nodes call get_stream_writer() and emit typed events so the
SSE route can forward them to the browser in real time.

SSE event shapes:
  {"type": "token",        "content": "..."}          — streaming character chunk
  {"type": "status",       "message": "..."}           — progress label
  {"type": "prd_complete", "score": 87, "grade": "B",
                           "file_name": "...md"}       — PRD validated
"""
import logging
import re
from datetime import date

from anthropic import AsyncAnthropic
from langgraph.config import get_stream_writer

from src.config import settings
from src.graph.state import PRDState

logger = logging.getLogger(__name__)

# ── Prompts ───────────────────────────────────────────────────────────────────

SAM_SYSTEM = """\
You are Sam, an Expert AI Product Analyst. Your role is to gather specific, \
actionable product requirements through natural conversation.

RULES:
- Ask a maximum of 3 focused questions per turn.
- Never assume. If something is unclear, ask.
- Do not use placeholder names like "MyApp" or "Example Project".
- Once you have enough to write a full PRD, emit the signal below and stop.

WHEN READY — respond with EXACTLY this block, nothing after it:

GENERATE_PRD:
- Project: [exact project name]
- Type: [Feature | Enhancement | New Product]
- Platform: [Web | iOS | Android | API | All]
- Key Features: [3-5 bullet points]
- Target Users: [specific description]
- Timeline: [deadline or "TBD"]
- Success Metric: [one measurable goal]

Shall I proceed with generating the complete PRD?\
"""

DEVBRIDGE_SYSTEM = """\
You are DevBridge, an elite AI PRD Generator. You receive a structured context \
summary and must output a complete, professional Product Requirements Document in \
one response. Use only the information in the context. Write TBD for anything missing.

OUTPUT FORMAT — use exactly these section headers:

# Classification Summary
```
Type:               [from context]
Priority:           [Critical | High | Medium | Low]
Complexity:         [Low | Medium | High]
Estimated Effort:   [X story points]
```

# Product Overview
- **Project Name**: ...
- **Version**: 1.0
- **Date**: {today}
- **Introduction**: [2-3 sentence summary]

# Goals
- Primary Goal: ...
- User Experience Goal: ...

# User Stories / Functional Requirements
**FR1**: As a [user], I want [action] so that [benefit].
**FR2**: ...
(minimum 5 FRs)

# Non-Functional Requirements
- Performance: ...
- Security: ...
- Usability: ...

# Scope
**In Scope:**
- ...

**Out of Scope:**
- ...

# Success Metrics
- [metric with target number]

# Design and UX Considerations
- Layout: ...
- Key user flows: ...

# Technical Considerations
- Platform: ...
- Stack: ...
- Key dependencies / APIs: ...

# Timeline and Milestones
- Week 1-2: ...

# Stakeholders
- Project Owner: ...

# Jira Ticket Templates

**Epic:**
```
Issue Type: Epic
Summary: [project objective]
Description: [2-3 sentences]
Acceptance Criteria: [3 conditions]
```

**Story 1 (FR1):**
```
Summary: [title]
Acceptance Criteria: [3 specific, testable conditions]
```

# Test Cases

## Happy Path

**TC001: [Core workflow test]**
- Steps: 1. ... 2. ...
- Expected: ...
- Priority: Critical

[continue to TC015 minimum — aim for 20]

## Edge Cases

**TC101: [Boundary or error condition]**
- Steps: ...
- Expected: [error handled gracefully]

[minimum 5 edge case TCs]

RULES:
- Minimum 15 test cases total.
- Every FR must have at least one TC.
- No markdown code fences around the whole document.\
""".format(today=date.today().isoformat())


# ── Shared helpers ────────────────────────────────────────────────────────────

def _make_client() -> AsyncAnthropic:
    return AsyncAnthropic(
        base_url=settings.rakuten_anthropic_base_url,
        auth_token=settings.rakuten_ai_gateway_key,
    )


def _extract_context_summary(text: str) -> str:
    """Pull the structured block that follows the GENERATE_PRD: signal."""
    match = re.search(r"GENERATE_PRD:\s*([\s\S]*?)(?:Shall I proceed|$)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text  # fallback: use the whole message as context


def _placeholder_guard(text: str) -> bool:
    """Return True if the context looks like a placeholder / not real."""
    return bool(re.search(r"\bMyApp\b|\bExample Project\b|\bSample Feature\b|\bunnamed\b", text, re.I))


def _score_prd(markdown: str) -> tuple[int, str]:
    """Score 0-100. Mirrors the logic from the n8n Validate PRD Quality node."""
    patterns = {
        "classification": re.compile(r"Classification Summary", re.I),
        "overview":       re.compile(r"Product Overview|Introduction", re.I),
        "goals":          re.compile(r"\bGoals\b", re.I),
        "functional":     re.compile(r"Functional Requirements|User Stories", re.I),
        "non_functional": re.compile(r"Non-Functional Requirements", re.I),
        "scope":          re.compile(r"In Scope|Out of Scope", re.I),
        "metrics":        re.compile(r"Success Metrics|KPIs?", re.I),
        "test_cases":     re.compile(r"Test Cases?|TC\d+", re.I),
    }
    section_hits = sum(1 for p in patterns.values() if p.search(markdown))
    tc_count     = len(re.findall(r"TC\d{2,}", markdown))
    length       = len(markdown)

    score  = round((section_hits / len(patterns)) * 50)
    score += 30 if tc_count >= 15 else 25 if tc_count >= 10 else 15 if tc_count >= 5 else 0
    score += 20 if length > 5000 else 10 if length > 3000 else 5 if length > 2000 else 0
    score  = min(100, score)

    grade = "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 60 else "F"
    return score, grade


def _slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9\s_-]", "", text.lower())
    slug = re.sub(r"\s+", "_", slug).strip("_")
    return slug[:max_len] or "prd_document"


# ── Node: analyze ─────────────────────────────────────────────────────────────

async def analyze(state: PRDState) -> dict:
    """
    Sam asks requirements questions.
    Returns updated messages + transitions mode to "generate" when ready.
    """
    writer  = get_stream_writer()
    client  = _make_client()

    full_text = ""
    async with client.messages.stream(
        model=settings.rakuten_anthropic_model,
        max_tokens=1024,
        system=SAM_SYSTEM,
        messages=state["messages"],
    ) as stream:
        async for chunk in stream.text_stream:
            full_text += chunk
            writer({"type": "token", "content": chunk})

    logger.debug("analyze: response length=%d", len(full_text))

    update: dict = {
        "messages": [{"role": "assistant", "content": full_text}]
    }

    if "GENERATE_PRD:" in full_text:
        ctx = _extract_context_summary(full_text)
        if _placeholder_guard(ctx):
            logger.warning("analyze: placeholder detected in context summary")
        else:
            logger.info("analyze: GENERATE_PRD signal detected")
            writer({"type": "status", "message": "Requirements gathered. Generating PRD..."})
            update["mode"]            = "generate"
            update["context_summary"] = ctx

    return update


# ── Node: generate_prd ────────────────────────────────────────────────────────

async def generate_prd(state: PRDState) -> dict:
    """
    DevBridge generates the full PRD markdown in one shot.
    Uses context_summary stored in state — no user message needed.
    """
    writer  = get_stream_writer()
    client  = _make_client()

    writer({"type": "status", "message": "Writing PRD document..."})

    prompt = (
        "Generate a comprehensive PRD using this requirements context:\n\n"
        + state.get("context_summary", "")
    )

    full_text = ""
    async with client.messages.stream(
        model=settings.rakuten_anthropic_model,
        max_tokens=8192,
        system=DEVBRIDGE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for chunk in stream.text_stream:
            full_text += chunk
            writer({"type": "token", "content": chunk})

    logger.info("generate_prd: generated %d chars", len(full_text))

    return {
        "prd_markdown": full_text,
        "messages":     [{"role": "assistant", "content": full_text}],
    }


# ── Node: validate ────────────────────────────────────────────────────────────

def validate(state: PRDState) -> dict:
    """
    Score the PRD 0-100, attach grade and file name.
    Synchronous — no LLM call needed.
    """
    writer = get_stream_writer()

    markdown = state.get("prd_markdown", "")
    score, grade = _score_prd(markdown)

    # Derive file name from context summary
    ctx      = state.get("context_summary", "")
    proj     = re.search(r"Project:\s*([^\n\r-]+)", ctx)
    raw_name = proj.group(1).strip() if proj else "prd_document"
    file_name = f"{_slugify(raw_name)}_{date.today().isoformat()}.md"

    logger.info("validate: score=%d grade=%s file=%s", score, grade, file_name)

    writer({
        "type":       "prd_complete",
        "score":      score,
        "grade":      grade,
        "file_name":  file_name,
    })

    return {
        "quality_score": score,
        "grade":         grade,
        "file_name":     file_name,
    }


# ── Phase 2 node stubs ────────────────────────────────────────────────────────
# These are imported by graph.py so the graph compiles; they will be filled in
# Phase 2. For now they immediately pass through.

def email_interrupt(state: PRDState) -> dict:          # noqa: ARG001
    """Phase 2: suspend execution and wait for the user to submit email form."""
    raise NotImplementedError("email_interrupt is implemented in Phase 2")


def send_email(state: PRDState) -> dict:               # noqa: ARG001
    """Phase 2: send PRD as email attachment via Gmail API."""
    raise NotImplementedError("send_email is implemented in Phase 2")


def jira_interrupt(state: PRDState) -> dict:           # noqa: ARG001
    """Phase 2: suspend execution and wait for JIRA approval form."""
    raise NotImplementedError("jira_interrupt is implemented in Phase 2")


def create_jira(state: PRDState) -> dict:              # noqa: ARG001
    """Phase 2: create Epic + Tasks + Subtasks via JIRA REST API."""
    raise NotImplementedError("create_jira is implemented in Phase 2")
