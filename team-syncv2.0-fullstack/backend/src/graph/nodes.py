from __future__ import annotations

"""
Graph nodes — each function maps (state) → partial state update dict.

SSE event shapes:
  {"type": "token",               "content": "..."}
  {"type": "status",              "message": "..."}
  {"type": "prd_complete",        "score": 87, "grade": "B", "file_name": "...md"}
  {"type": "test_cases_complete", "file_name": "...md", "tc_count": 15}
"""
import base64
import logging
import re
from datetime import date, datetime

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

DEVBRIDGE_PRD_SYSTEM = """\
You are DevBridge, PRD writer. Use ONLY provided context. Write TBD if unknown. \
No JIRA templates, test cases, or stakeholder lists.

Output exactly these sections:

# Classification Summary
```
Type: X | Priority: Critical/High/Medium/Low | Complexity: Low/Medium/High | Effort: X pts
```
# Product Overview
- **Project Name**: X | **Version**: 1.0 | **Date**: {today}
- **Introduction**: [2-3 sentences]
# Goals
- Primary: X | UX: X
# User Stories / Functional Requirements
**FR1**: As [user], I want [action] so that [benefit].
[FR2-FR5+ minimum 5 FRs]
# Non-Functional Requirements
- Performance: X | Security: X | Usability: X
# Scope
**In Scope:** ... | **Out of Scope:** ...
# Success Metrics
- [metric + measurable target]
# Technical Considerations
- Platform: X | Stack: X | APIs: X
# Timeline
- Phase 1-2: X\
""".format(today=date.today().isoformat())

DEVBRIDGE_TESTCASES_SYSTEM = """\
You are DevBridge. Generate test cases ONLY from the PRD below.

# Test Cases
## Happy Path
**TC001**: [scenario] | Steps: 1. ... 2. ... | Expected: X | Priority: Critical/High/Medium
[min 10 TCs — one per FR minimum]

## Edge Cases
**TC101**: [boundary/error] | Steps: X | Expected: [handled gracefully]
[min 5 edge TCs]\
"""


# ── Shared helpers ────────────────────────────────────────────────────────────

def _make_model(max_tokens: int = 2048, temperature: float = 0.7) -> ChatAnthropic:
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
    return text


def _placeholder_guard(text: str) -> bool:
    return bool(re.search(r"\bMyApp\b|\bExample Project\b|\bSample Feature\b|\bunnamed\b", text, re.I))


def _score_prd(markdown: str) -> tuple[int, str]:
    """Score PRD-only content 0-100."""
    patterns = {
        "classification": re.compile(r"Classification Summary", re.I),
        "overview":       re.compile(r"Product Overview|Introduction", re.I),
        "goals":          re.compile(r"\bGoals\b", re.I),
        "functional":     re.compile(r"Functional Requirements|User Stories", re.I),
        "non_functional": re.compile(r"Non-Functional Requirements", re.I),
        "scope":          re.compile(r"In Scope|Out of Scope", re.I),
        "metrics":        re.compile(r"Success Metrics|KPIs?", re.I),
        "technical":      re.compile(r"Technical Considerations", re.I),
        "timeline":       re.compile(r"Timeline|Milestones", re.I),
    }
    fr_count     = len(re.findall(r"\*\*FR\d+\*\*", markdown))
    section_hits = sum(1 for p in patterns.values() if p.search(markdown))
    length       = len(markdown)

    score  = round((section_hits / len(patterns)) * 60)
    score += 20 if fr_count >= 5 else 15 if fr_count >= 3 else 5 if fr_count >= 1 else 0
    score += 20 if length > 4000 else 15 if length > 2500 else 10 if length > 1500 else 5 if length > 800 else 0
    score  = min(100, score)

    grade = "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 60 else "F"
    return score, grade


def _slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9\s_-]", "", text.lower())
    slug = re.sub(r"\s+", "_", slug).strip("_")
    return slug[:max_len] or "prd_document"


def _inject_document_context(lc_msgs: list, docs: list[dict]) -> list:
    """Inject uploaded document text / images into the LangChain message list."""
    if not docs:
        return lc_msgs

    text_docs  = [d for d in docs if d.get("text")]
    image_docs = [d for d in docs if d.get("image_data")]

    if text_docs:
        context_block = "\n\n---\nUPLOADED DOCUMENTS (treat as additional context):\n"
        for doc in text_docs:
            context_block += f"\n[{doc['filename']}]\n{doc['text'][:3000]}\n"
        if lc_msgs and isinstance(lc_msgs[0], SystemMessage):
            lc_msgs[0] = SystemMessage(content=lc_msgs[0].content + context_block)

    if image_docs:
        image_msgs = []
        for doc in image_docs:
            image_msgs.append(HumanMessage(content=[
                {
                    "type":      "image_url",
                    "image_url": {"url": f"data:{doc['content_type']};base64,{doc['image_data']}"},
                },
                {
                    "type": "text",
                    "text": f"This image ({doc['filename']}) was uploaded as additional context.",
                },
            ]))
        insert_idx = 1 if lc_msgs and isinstance(lc_msgs[0], SystemMessage) else 0
        lc_msgs = lc_msgs[:insert_idx] + image_msgs + lc_msgs[insert_idx:]

    return lc_msgs


# ── Command helpers ───────────────────────────────────────────────────────────

_CONVERSATIONAL_COMMANDS = re.compile(
    r"^/(?P<cmd>prd|help|regenerate|summary)\b",
    re.I,
)

_CONFIRMATION_WORDS = frozenset({
    'yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'proceed', 'generate',
    'go', 'great', 'perfect', 'approve', 'confirm', 'continue', 'please',
})


def _is_confirmation(text: str) -> bool:
    """Return True if the message looks like a short yes/proceed confirmation."""
    if len(text) > 80:
        return False
    words = set(re.sub(r"[^a-z\s]", "", text.lower()).split())
    return bool(words & _CONFIRMATION_WORDS)

_HELP_TEXT = """\
**Available commands**

| Command | What it does |
|---|---|
| `/jira` | Create JIRA tickets from the current PRD |
| `/testcases` | Generate test cases from the current PRD |
| `/prd` | Show a summary of the current PRD |
| `/summary` | Summarise the requirements gathered so far |
| `/regenerate` | Discard the current PRD and start requirements gathering again |
| `/help` | Show this command list |

You can also type natural language variants, e.g. *"create jira tickets"*, \
*"generate test cases"*, *"start over"*.\
"""


async def _handle_command(cmd: str, state: PRDState, writer) -> dict | None:
    cmd = cmd.lower()

    if cmd == "help":
        writer({"type": "token", "content": _HELP_TEXT})
        return {"messages": [{"role": "assistant", "content": _HELP_TEXT}]}

    if cmd == "prd":
        prd = state.get("prd_markdown", "")
        if not prd:
            reply = "No PRD has been generated yet. Continue the conversation and I'll generate one when I have enough requirements."
        else:
            score = state.get("quality_score", 0)
            grade = state.get("grade", "")
            fname = state.get("file_name", "")
            preview = prd[:800].rstrip() + (" …" if len(prd) > 800 else "")
            reply = (
                f"**Current PRD** — `{fname}` · Grade **{grade}** · Score **{score}/100**\n\n"
                f"{preview}\n\n"
                "_Use `/jira` to create JIRA tickets or `/testcases` to generate test cases._"
            )
        writer({"type": "token", "content": reply})
        return {"messages": [{"role": "assistant", "content": reply}]}

    if cmd == "summary":
        ctx = state.get("context_summary", "")
        if not ctx:
            reply = "No requirements have been gathered yet. Tell me about the product you want to build!"
        else:
            reply = f"**Requirements summary gathered so far:**\n\n{ctx}"
        writer({"type": "token", "content": reply})
        return {"messages": [{"role": "assistant", "content": reply}]}

    if cmd == "regenerate":
        reply = (
            "Sure — let's start fresh. Tell me about the product you want to build "
            "and I'll gather requirements from the beginning."
        )
        writer({"type": "token", "content": reply})
        return {
            "mode":                 "analyze",
            "prd_markdown":         "",
            "test_cases_markdown":  "",
            "test_cases_file_name": "",
            "context_summary":      "",
            "prd_outline":          "",
            "pending_interrupt":    None,
            "quality_score":        0,
            "grade":                "",
            "file_name":            "",
            "messages": [{"role": "assistant", "content": reply}],
        }

    return None


# ── Node: analyze ─────────────────────────────────────────────────────────────

async def analyze(state: PRDState) -> dict:
    """Sam asks requirements questions."""
    writer = get_stream_writer()

    last_content = ""
    for msg in reversed(state.get("messages", [])):
        if msg.get("role") == "user":
            last_content = msg.get("content", "").strip()
            break
    m = _CONVERSATIONAL_COMMANDS.match(last_content)
    if m:
        result = await _handle_command(m.group("cmd"), state, writer)
        if result is not None:
            return result

    # If we already gathered requirements and the user just confirmed → start outline
    if state.get("context_summary") and not state.get("prd_markdown"):
        if _is_confirmation(last_content):
            logger.info("analyze: user confirmed PRD generation → mode=generate")
            return {"mode": "generate"}

    model   = _make_model(max_tokens=1024, temperature=0.7)
    lc_msgs = _to_lc_messages(state["messages"], SAM_SYSTEM)
    lc_msgs = _inject_document_context(lc_msgs, state.get("uploaded_documents", []))

    full_text = ""
    async for chunk in model.astream(lc_msgs):
        text = _extract_chunk_text(chunk)
        if text:
            full_text += text
            writer({"type": "token", "content": text})

    logger.debug("analyze: response length=%d", len(full_text))

    update: dict = {"messages": [{"role": "assistant", "content": full_text}]}

    if "GENERATE_PRD:" in full_text:
        ctx = _extract_context_summary(full_text)
        if _placeholder_guard(ctx):
            logger.warning("analyze: placeholder detected in context summary")
        else:
            logger.info("analyze: GENERATE_PRD signal detected — waiting for user confirmation")
            update["mode"]            = "awaiting_prd_confirm"
            update["context_summary"] = ctx

    return update


# ── Node: generate_prd_outline ────────────────────────────────────────────────

async def generate_prd_outline(state: PRDState) -> dict:
    """DevBridge generates a concise PRD outline for user review."""
    writer = get_stream_writer()
    model  = _make_model(max_tokens=1024, temperature=0.3)

    writer({"type": "status", "message": "Planning PRD outline…"})

    prompt = (
        "Based on the requirements below, produce a concise PRD outline using EXACTLY this format:\n\n"
        "**Project:** [name]\n"
        "**Goals:** [1-2 sentence summary]\n\n"
        "**Key Features:**\n"
        "- [feature 1]\n"
        "- [feature 2]\n"
        "(5-10 bullets)\n\n"
        "**Target Users:** [description]\n\n"
        "**Out of Scope:**\n"
        "- [item]\n\n"
        "**Assumptions:**\n"
        "- [item]\n\n"
        "Requirements:\n\n"
        + state.get("context_summary", "")
    )
    lc_msgs = _to_lc_messages([{"role": "user", "content": prompt}], DEVBRIDGE_PRD_SYSTEM)

    full_text = ""
    async for chunk in model.astream(lc_msgs):
        text = _extract_chunk_text(chunk)
        if text:
            full_text += text
            writer({"type": "token", "content": text})

    logger.info("generate_prd_outline: generated %d chars", len(full_text))
    return {"prd_outline": full_text}


# ── Node: prd_outline_interrupt ───────────────────────────────────────────────

async def prd_outline_interrupt(state: PRDState, config: RunnableConfig) -> dict:
    return {
        "pending_interrupt": {
            "form":    "prd_outline_form",
            "message": "Here's my plan for the PRD — approve to generate or request changes.",
            "outline": state.get("prd_outline", ""),
        }
    }


# ── Node: generate_prd ────────────────────────────────────────────────────────

async def generate_prd(state: PRDState) -> dict:
    """DevBridge generates the full PRD markdown. Output capped at 6500 tokens."""
    writer = get_stream_writer()
    model  = _make_model(max_tokens=6500, temperature=0.3)

    writer({"type": "status", "message": "Writing PRD document..."})

    outline = state.get("prd_outline", "")
    prompt  = (
        "Generate a comprehensive PRD using this requirements context:\n\n"
        + state.get("context_summary", "")
        + ("\n\nApproved PRD outline to follow:\n" + outline if outline else "")
    )
    lc_msgs = _to_lc_messages([{"role": "user", "content": prompt}], DEVBRIDGE_PRD_SYSTEM)

    full_text  = ""
    last_chunk = None
    async for chunk in model.astream(lc_msgs):
        last_chunk = chunk
        text = _extract_chunk_text(chunk)
        if text:
            full_text += text
            writer({"type": "token", "content": text})

    if last_chunk is not None:
        stop_reason = getattr(last_chunk, "response_metadata", {}).get("stop_reason")
        logger.info("generate_prd: stop_reason=%s chars=%d", stop_reason, len(full_text))
        if stop_reason == "max_tokens":
            logger.warning("generate_prd: OUTPUT TRUNCATED — hit 6500 token limit.")

    proj_match = re.search(r"\*\*Project Name\*\*[:\s]+([^\n\r]+)", full_text, re.I)
    proj_name  = proj_match.group(1).strip() if proj_match else "the project"

    return {
        "prd_markdown": full_text,
        "messages": [{
            "role":    "assistant",
            "content": f"I've generated the PRD for {proj_name}. It has been validated and is ready for review.",
        }],
    }


# ── Node: generate_test_cases ─────────────────────────────────────────────────

async def generate_test_cases(state: PRDState) -> dict:
    """DevBridge generates test cases as a separate document."""
    writer = get_stream_writer()
    model  = _make_model(max_tokens=4096, temperature=0.3)

    writer({"type": "status", "message": "Generating test cases…"})

    prompt = (
        "Generate test cases for the following PRD context and functional requirements:\n\n"
        + state.get("context_summary", "")
        + "\n\nFunctional Requirements from PRD:\n"
        + state.get("prd_markdown", "")
    )
    lc_msgs = _to_lc_messages([{"role": "user", "content": prompt}], DEVBRIDGE_TESTCASES_SYSTEM)

    full_text = ""
    async for chunk in model.astream(lc_msgs):
        text = _extract_chunk_text(chunk)
        if text:
            full_text += text
            writer({"type": "token", "content": text})

    logger.info("generate_test_cases: generated %d chars", len(full_text))
    return {"test_cases_markdown": full_text}


# ── Node: validate ────────────────────────────────────────────────────────────

def validate(state: PRDState) -> dict:
    """Score the PRD 0-100, attach grade and file name."""
    writer = get_stream_writer()

    markdown = state.get("prd_markdown", "")
    score, grade = _score_prd(markdown)

    ctx      = state.get("context_summary", "")
    proj     = re.search(r"Project:\s*([^\n\r-]+)", ctx)
    raw_name = proj.group(1).strip() if proj else "prd_document"
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"PRD_{_slugify(raw_name)}_{ts}.md"

    logger.info("validate: score=%d grade=%s file=%s", score, grade, file_name)

    writer({"type": "prd_complete", "score": score, "grade": grade, "file_name": file_name})

    return {"quality_score": score, "grade": grade, "file_name": file_name}


# ── Node: validate_test_cases ─────────────────────────────────────────────────

def validate_test_cases(state: PRDState) -> dict:
    """Name and count the test case document, emit test_cases_complete SSE event."""
    writer = get_stream_writer()

    md       = state.get("test_cases_markdown", "")
    tc_count = len(re.findall(r"\*\*TC\d+\*\*", md))

    ctx      = state.get("context_summary", "")
    proj     = re.search(r"Project:\s*([^\n\r-]+)", ctx)
    raw      = proj.group(1).strip() if proj else "test_cases"
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"TC_{_slugify(raw)}_{ts}.md"

    logger.info("validate_test_cases: tc_count=%d file=%s", tc_count, file_name)
    writer({"type": "test_cases_complete", "file_name": file_name, "tc_count": tc_count})

    return {"test_cases_file_name": file_name, "actions_taken": ["test_cases"]}


# ── Node: post_prd_interrupt ──────────────────────────────────────────────────

async def post_prd_interrupt(state: PRDState, config: RunnableConfig) -> dict:
    """Show the post-PRD action menu: email, test cases, JIRA, or done."""
    actions_taken = list(set(state.get("actions_taken", [])))
    return {
        "pending_interrupt": {
            "form":          "post_prd_actions",
            "message":       "PRD ready! What would you like to do next?",
            "score":         state.get("quality_score", 0),
            "grade":         state.get("grade", ""),
            "actions_taken": actions_taken,
        }
    }


# ── Node: email_interrupt ─────────────────────────────────────────────────────

async def email_interrupt(state: PRDState, config: RunnableConfig) -> dict:
    from src.db import SessionLocal
    from src.services.email import get_gmail_connection

    session_id = config["configurable"].get("thread_id", "")
    user_id    = int(config["configurable"].get("user_id", "0"))
    async with SessionLocal() as db:
        token = await get_gmail_connection(db, user_id)
    connected   = token is not None
    connect_url = f"/api/v1/email/auth/connect?session_id={session_id}"

    return {
        "pending_interrupt": {
            "form":            "email_form",
            "message":         "Your PRD is ready! Connect Gmail or enter details below.",
            "fields":          ["name", "email"],
            "score":           state.get("quality_score", 0),
            "grade":           state.get("grade", ""),
            "gmail_connected": connected,
            "gmail_user":      token.account_email if connected else None,
            "connect_url":     None if connected else connect_url,
        }
    }


# ── Node: send_email ──────────────────────────────────────────────────────────

async def send_email(state: PRDState, config: RunnableConfig) -> dict:
    """Send the PRD via Gmail API (OAuth) or SMTP fallback."""
    from src.services.email import send_prd_email
    from src.db import SessionLocal
    from src.services.email import get_gmail_connection

    writer = get_stream_writer()

    recipient_email = state.get("recipient_email", "")
    if not recipient_email or recipient_email == "__skip__":
        return {"actions_taken": ["email"]}

    user_id = int(config["configurable"].get("user_id", "0"))
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
    Persist the JIRA approval payload. If already connected: auto-confirm form.
    If not connected: full form with Connect JIRA button.
    """
    from src.db import SessionLocal
    from src.services.oauth_connections import get_oauth_connection
    from src.services.jira import JiraService

    session_id = config["configurable"].get("thread_id", "")
    user_id    = int(config["configurable"].get("user_id", "0"))
    async with SessionLocal() as db:
        token = await get_oauth_connection(db, user_id, "jira")
        project_choices: list[dict] = []
        try:
            svc = await JiraService.for_user(db, user_id)
            raw = await svc.search_projects()
            project_choices = [{"key": p["key"], "name": p["name"]} for p in raw[:50]]
        except Exception:
            pass

    connected   = token is not None
    connect_url = f"/api/v1/jira/auth/connect?session_id={session_id}"

    if connected:
        payload = {
            "form":               "jira_auto_confirm",
            "message":            f"Creating JIRA tickets as {token.account_name}…",
            "jira_connected":     True,
            "jira_user":          token.account_name,
            "jira_cloud":         token.cloud_name,
            "auto_confirm":       True,
            "countdown_seconds":  5,
            "available_projects": project_choices,
            "default_project":    settings.jira_project_key,
        }
    else:
        payload = {
            "form":               "jira_form",
            "message":            "Review the PRD and approve JIRA ticket creation.",
            "fields":             ["decision", "assignee_email", "notes"],
            "hint":               "Approve to create tickets or skip to finish without JIRA.",
            "jira_connected":     False,
            "jira_user":          None,
            "jira_cloud":         None,
            "connect_url":        connect_url,
            "available_projects": project_choices,
            "default_project":    settings.jira_project_key,
        }

    return {"pending_interrupt": payload}


# ── Node: create_jira ─────────────────────────────────────────────────────────

async def create_jira(state: PRDState, config: RunnableConfig) -> dict:
    """Create Epic → Stories → Subtasks in JIRA, then send a notification email."""
    from src.services.jira import JiraService
    from src.services.email import send_jira_notification
    from src.db import SessionLocal
    from src.services.email import get_gmail_connection
    writer = get_stream_writer()

    user_id     = int(config["configurable"].get("user_id", "0"))
    project_key = state.get("jira_project_key", "").strip()
    writer({"type": "status", "message": "Creating JIRA tickets…"})

    async with SessionLocal() as db:
        svc         = await JiraService.for_user(db, user_id)
        email_token = await get_gmail_connection(db, user_id)

    from src.services.jira import extract_jira_items
    combined_markdown = state["prd_markdown"] + "\n\n" + state.get("test_cases_markdown", "")
    items         = extract_jira_items(combined_markdown, state.get("file_name", "PRD Feature"))
    total_stories = len(items["tasks"])
    for i, task in enumerate(items["tasks"]):
        writer({
            "type":    "jira_progress",
            "message": f"Creating story {i + 1} of {total_stories}…",
            "current": i + 1,
            "total":   total_stories,
        })

    result = await svc.create_from_prd(
        prd_markdown=state["prd_markdown"],
        feature_name=state.get("file_name", "PRD Feature").replace("_", " "),
        assignee_email=state.get("jira_assignee_email", ""),
        project_key=project_key,
    )

    writer({
        "type":      "jira_created",
        "epic_key":  result["epic_key"],
        "epic_url":  result["epic_url"],
        "task_keys": result["task_keys"],
    })

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
