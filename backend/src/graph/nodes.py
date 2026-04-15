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

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
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

def _make_model(max_tokens: int = 4096, temperature: float = 0.7) -> ChatAnthropic:
    """
    Build a ChatAnthropic instance pointed at the Rakuten AI Gateway.

    Auth pattern (from Rakuten docs):
      - anthropic_api_key="test"  — required by the LangChain client init but
                                    NOT sent to Rakuten; the real auth is the header below.
      - Authorization: Bearer {key} — actual Rakuten gateway credential.
    """
    return ChatAnthropic(
        model_name=settings.rakuten_anthropic_model,
        temperature=temperature,
        max_tokens=max_tokens,
        anthropic_api_url=settings.rakuten_anthropic_base_url,
        anthropic_api_key="test",
        default_headers={"Authorization": f"Bearer {settings.rakuten_ai_gateway_key}"},
        streaming=True,
    )


def _to_lc_messages(dicts: list[dict], system: str) -> list:
    """Convert our plain-dict message history to LangChain message objects."""
    msgs: list = [SystemMessage(content=system)]
    for d in dicts:
        if d["role"] == "user":
            msgs.append(HumanMessage(content=d["content"]))
        else:
            msgs.append(AIMessage(content=d["content"]))
    return msgs


def _extract_chunk_text(chunk) -> str:
    """Pull text out of a LangChain streaming chunk (handles str or list content)."""
    c = chunk.content
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "".join(
            item if isinstance(item, str)
            else item.get("text", "") if isinstance(item, dict)
            else ""
            for item in c
        )
    return ""


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


# ── Prompts for outline + test-cases nodes ────────────────────────────────────

OUTLINE_SYSTEM = """\
You are DevBridge, an expert PRD generator. Based on the requirements context below, \
produce a concise PRD outline: 8-12 bullet points covering the key sections and major \
decisions that will appear in the full document. Use clear, action-oriented language. \
Format as a markdown bullet list — no preamble, no closing remarks.\
"""

TEST_CASES_SYSTEM = """\
You are a senior QA engineer. Generate a comprehensive test suite for the provided PRD.

OUTPUT FORMAT — test cases only, no preamble:

## Happy Path

**TC001: [Core workflow description]**
- Steps: 1. ... 2. ...
- Expected: ...
- Priority: Critical

[continue to TC015 minimum — aim for TC020]

## Edge Cases

**TC101: [Edge condition]**
- Steps: ...
- Expected: [graceful handling]

[minimum 5 edge case TCs]

RULES:
- Every FR must have at least one TC.
- Use TC001-TC099 for happy path, TC101+ for edge cases.
- Steps must be numbered and specific.
- Expected results must be verifiable.\
"""


# ── Node: generate_prd_outline ───────────────────────────────────────────────

async def generate_prd_outline(state: PRDState) -> dict:
    """
    Generate a brief PRD outline that the user reviews before full PRD generation.
    Streams tokens so the user can see the outline forming in real time.
    ChatInterface detects the 'Planning PRD outline...' status to start token accumulation.
    """
    writer  = get_stream_writer()
    model   = _make_model(max_tokens=512, temperature=0.3)

    writer({"type": "status", "message": "Planning PRD outline..."})

    prompt  = (
        "Create a concise PRD outline based on these requirements:\n\n"
        + state.get("context_summary", "")
    )
    lc_msgs = _to_lc_messages(
        [{"role": "user", "content": prompt}],
        OUTLINE_SYSTEM,
    )

    full_text = ""
    async for chunk in model.astream(lc_msgs):
        text = _extract_chunk_text(chunk)
        if text:
            full_text += text
            writer({"type": "token", "content": text})

    logger.info("generate_prd_outline: length=%d", len(full_text))
    return {"prd_outline": full_text}


# ── Node: prd_outline_interrupt ───────────────────────────────────────────────

def prd_outline_interrupt(state: PRDState) -> dict:
    """
    Present the generated outline for user review.
    Sets pending_interrupt in state (state-field pattern) so _pending_interrupt_payload
    can detect it. The graph then proceeds to END; the frontend renders InlinePRDOutlineForm.
    """
    return {
        "pending_interrupt": {
            "form":    "prd_outline_form",
            "message": "Here's the PRD outline. Approve to generate the full document, or request changes.",
            "outline": state.get("prd_outline", ""),
            "fields":  ["decision", "feedback"],
        }
    }


# ── Node: post_prd_interrupt ──────────────────────────────────────────────────

def post_prd_interrupt(state: PRDState) -> dict:
    """
    Present the post-PRD action menu (Email / Test Cases / JIRA / Done).
    Uses state-field pattern so _pending_interrupt_payload detects it.
    The frontend renders InlineActionMenu with actions_taken to mark completed items.
    """
    return {
        "pending_interrupt": {
            "form":         "post_prd_actions",
            "message":      "What would you like to do with your PRD?",
            "fields":       ["action"],
            "score":        state.get("quality_score", 0),
            "grade":        state.get("grade", ""),
            "file_name":    state.get("file_name", ""),
            "actions_taken": list(state.get("actions_taken", [])),
        }
    }


# ── Node: generate_test_cases ─────────────────────────────────────────────────

async def generate_test_cases(state: PRDState) -> dict:
    """
    Generate comprehensive Happy Path + Edge Case test cases from the PRD.
    ChatInterface detects 'Generating test cases...' status to start TC token accumulation.
    """
    writer  = get_stream_writer()
    model   = _make_model(max_tokens=4096, temperature=0.2)

    writer({"type": "status", "message": "Generating test cases..."})

    prd     = state.get("prd_markdown", "")
    prompt  = "Generate a full test suite for this PRD:\n\n" + prd[:6000]
    lc_msgs = _to_lc_messages(
        [{"role": "user", "content": prompt}],
        TEST_CASES_SYSTEM,
    )

    full_text = ""
    async for chunk in model.astream(lc_msgs):
        text = _extract_chunk_text(chunk)
        if text:
            full_text += text
            writer({"type": "token", "content": text})

    logger.info("generate_test_cases: length=%d", len(full_text))
    return {"test_cases_markdown": full_text}


# ── Node: validate_test_cases ─────────────────────────────────────────────────

def validate_test_cases(state: PRDState) -> dict:
    """
    Count test cases, derive a file name, and emit the test_cases_complete SSE event.
    Synchronous — no LLM call needed.
    """
    writer   = get_stream_writer()
    markdown = state.get("test_cases_markdown", "")
    tc_count = len(re.findall(r"\bTC\d{2,}\b", markdown))

    ctx       = state.get("context_summary", "")
    proj      = re.search(r"Project:\s*([^\n\r-]+)", ctx)
    raw_name  = proj.group(1).strip() if proj else "test_cases"
    file_name = f"{_slugify(raw_name)}_tests_{date.today().isoformat()}.md"

    logger.info("validate_test_cases: tc_count=%d file=%s", tc_count, file_name)
    writer({"type": "test_cases_complete", "file_name": file_name, "tc_count": tc_count})

    return {"test_cases_file_name": file_name, "actions_taken": ["test_cases"]}


# ── Node: analyze ─────────────────────────────────────────────────────────────

async def analyze(state: PRDState) -> dict:
    """
    Sam asks requirements questions.
    Returns updated messages + transitions mode to "generate" when ready.
    """
    writer   = get_stream_writer()
    model    = _make_model(max_tokens=1024, temperature=0.7)
    lc_msgs  = _to_lc_messages(state["messages"], SAM_SYSTEM)

    full_text = ""
    async for chunk in model.astream(lc_msgs):
        text = _extract_chunk_text(chunk)
        if text:
            full_text += text
            writer({"type": "token", "content": text})

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
    model   = _make_model(max_tokens=8192, temperature=0.3)

    writer({"type": "status", "message": "Writing PRD document..."})

    prompt  = (
        "Generate a comprehensive PRD using this requirements context:\n\n"
        + state.get("context_summary", "")
    )
    lc_msgs = _to_lc_messages(
        [{"role": "user", "content": prompt}],
        DEVBRIDGE_SYSTEM,
    )

    full_text = ""
    last_chunk = None
    async for chunk in model.astream(lc_msgs):
        last_chunk = chunk
        text = _extract_chunk_text(chunk)
        if text:
            full_text += text
            writer({"type": "token", "content": text})

    # Check if the response was cut off due to max_tokens
    if last_chunk is not None:
        stop_reason = getattr(last_chunk, "response_metadata", {}).get("stop_reason")
        logger.info("generate_prd: stop_reason=%s chars=%d", stop_reason, len(full_text))
        if stop_reason == "max_tokens":
            logger.warning("generate_prd: OUTPUT TRUNCATED — hit max_tokens limit (%d tokens). Consider increasing max_tokens or splitting generation.", 8192)

    # Use a short reference message so the full PRD markdown is not re-sent to the
    # LLM on every subsequent turn. The full content lives in state["prd_markdown"].
    proj_match = re.search(r"\*\*Project Name\*\*[:\s]+([^\n\r]+)", full_text, re.I)
    proj_name  = proj_match.group(1).strip() if proj_match else "the project"

    return {
        "prd_markdown": full_text,
        "messages": [{
            "role":    "assistant",
            "content": f"I've generated the PRD for {proj_name}. It has been validated and is ready for review.",
        }],
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


# ── Node: email_interrupt ─────────────────────────────────────────────────────

async def email_interrupt(state: PRDState, config: RunnableConfig) -> dict:
    """
    Suspend execution and wait for the user to submit their email details.
    Includes Gmail connection status so the frontend can show "Connect Gmail"
    if the user hasn't authenticated yet.
    """
    from langgraph.types import interrupt
    from src.db import SessionLocal
    from src.services.email import get_gmail_connection

    session_id  = config["configurable"].get("thread_id", "")
    user_id     = int(config["configurable"].get("user_id", "0"))
    async with SessionLocal() as db:
        token = await get_gmail_connection(db, user_id)
    connected   = token is not None
    connect_url = f"/api/v1/email/auth/connect?session_id={session_id}"

    form_data = interrupt({
        "form":              "email_form",
        "message":           "Your PRD is ready! Connect Gmail or enter details below.",
        "fields":            ["name", "email"],
        "score":             state.get("quality_score", 0),
        "grade":             state.get("grade", ""),
        "gmail_connected":   connected,
        "gmail_user":        token.account_email if connected else None,
        "connect_url":       None if connected else connect_url,
    })
    return {
        "recipient_name":  form_data.get("name", "").strip(),
        "recipient_email": form_data.get("email", "").strip(),
    }


# ── Node: send_email ──────────────────────────────────────────────────────────

async def send_email(state: PRDState, config: RunnableConfig) -> dict:
    """Send the PRD via Gmail API (OAuth) or SMTP fallback."""
    from src.services.email import send_prd_email
    from src.db import SessionLocal
    from src.services.email import get_gmail_connection

    writer     = get_stream_writer()

    # Skip guard: frontend sends email='__skip__' when user clicks Skip in confirm step
    recipient_email = state.get("recipient_email", "")
    if not recipient_email or recipient_email == "__skip__":
        return {}

    user_id    = int(config["configurable"].get("user_id", "0"))
    async with SessionLocal() as db:
        token = await get_gmail_connection(db, user_id)

    writer({"type": "status", "message": f"Sending PRD to {recipient_email}…"})

    await send_prd_email(
        recipient_name=state["recipient_name"],
        recipient_email=recipient_email,
        prd_markdown=state["prd_markdown"],
        file_name=state["file_name"],
        quality_score=state["quality_score"],
        grade=state["grade"],
        access_token=token.access_token if token else None,
        sender_email=token.account_email if token else None,
    )

    writer({"type": "email_sent", "recipient": recipient_email})
    return {"actions_taken": ["email"]}


# ── Node: jira_interrupt ──────────────────────────────────────────────────────

async def jira_interrupt(state: PRDState, config: RunnableConfig) -> dict:
    """
    Suspend execution and wait for the reviewer to approve JIRA ticket creation.

    The interrupt payload includes JIRA connection status so the frontend can
    show a 'Connect JIRA' button if the user hasn't authenticated yet.
    """
    from langgraph.types import interrupt
    from src.db import SessionLocal
    from src.services.oauth_connections import get_oauth_connection

    session_id  = config["configurable"].get("thread_id", "")
    user_id     = int(config["configurable"].get("user_id", "0"))
    async with SessionLocal() as db:
        token = await get_oauth_connection(db, user_id, "jira")
    connected   = token is not None
    connect_url = f"/api/v1/jira/auth/connect?session_id={session_id}"

    form_data = interrupt({
        "form":            "jira_form",
        "message":         "Review the PRD and approve JIRA ticket creation.",
        "fields":          ["decision", "assignee_email", "notes"],
        "hint":            "Type 'approve' to create tickets or 'skip' to finish without JIRA.",
        "jira_connected":  connected,
        "jira_user":       token.account_name if connected else None,
        "jira_cloud":      token.cloud_name if connected else None,
        "connect_url":     None if connected else connect_url,
    })
    return {
        "jira_decision":       form_data.get("decision", "skip").lower().strip(),
        "jira_assignee_email": form_data.get("assignee_email", "").strip(),
        "jira_notes":          form_data.get("notes", "").strip(),
    }


# ── Node: create_jira ─────────────────────────────────────────────────────────

async def create_jira(state: PRDState, config: RunnableConfig) -> dict:
    """
    Create Epic → Stories → Subtasks in JIRA, then send a notification email
    to the assignee with direct ticket links.

    Uses the user's OAuth token if they connected via /api/v1/jira/auth/connect.
    Falls back to the service-account API key from .env if not connected.
    """
    from src.services.jira import JiraService
    from src.services.email import send_jira_notification
    from src.db import SessionLocal
    from src.services.email import get_gmail_connection
    writer = get_stream_writer()

    user_id = int(config["configurable"].get("user_id", "0"))
    writer({"type": "status", "message": "Creating JIRA tickets…"})

    async with SessionLocal() as db:
        svc = await JiraService.for_user(db, user_id)
        email_token = await get_gmail_connection(db, user_id)
    result = await svc.create_from_prd(
        prd_markdown=state["prd_markdown"],
        feature_name=state.get("file_name", "PRD Feature").replace("_", " "),
        assignee_email=state.get("jira_assignee_email", ""),
    )

    writer({
        "type":      "jira_created",
        "epic_key":  result["epic_key"],
        "epic_url":  result["epic_url"],
        "task_keys": result["task_keys"],
    })

    # Send notification email to assignee
    if state.get("jira_assignee_email"):
        writer({"type": "status", "message": "Sending JIRA notification email…"})
        await send_jira_notification(
            assignee_email=state["jira_assignee_email"],
            assignee_name=result.get("assignee_name", ""),
            epic_key=result["epic_key"],
            epic_url=result["epic_url"],
            task_keys=result["task_keys"],
            project_key=state.get("jira_project_key", ""),
            prd_title=result["epic_key"],
            notes=state.get("jira_notes", ""),
            access_token=email_token.access_token if email_token else None,
            sender_email=email_token.account_email if email_token else None,
        )
        writer({"type": "notification_sent", "to": state["jira_assignee_email"]})

    return {
        "epic_key":      result["epic_key"],
        "epic_url":      result["epic_url"],
        "task_keys":     result["task_keys"],
        "actions_taken": ["jira"],
    }
