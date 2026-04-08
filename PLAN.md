# TeamSync v2.0 — LangGraph + Anthropic SDK
> Full rewrite plan. Replace n8n with Python-native workflow.
> Date: 2026-04-03

---

## Why rewrite

The current n8n workflow is a 3-state machine (analyze → generate → done) with two
human pauses. The logic isn't complex — the JSON format made it look complex. Every
change requires editing JSON-escaped JavaScript strings with no IDE support, no tests,
and unreadable git diffs.

LangGraph replaces n8n for the conversation workflow. The integrations (Gmail, JIRA)
become direct Python API calls. The result is one deployable service instead of two.

**What gets dropped:** n8n, the demo container, Ollama, the 22-file pipeline directory.
**What stays:** React frontend (it works), PostgreSQL, Rakuten AI Gateway.

---

## Architecture

```
Browser (React frontend)
        │  HTTP
        ▼
FastAPI  (:8000)
  POST /api/v1/chat              ← send message, run graph
  POST /api/v1/sessions/{id}/resume  ← resume after email/JIRA form
  GET  /api/v1/sessions/{id}/prd     ← fetch completed PRD
  GET  /health
        │
        ▼
LangGraph (in-process, same FastAPI app)
  State persisted in PostgreSQL via LangGraph checkpointer
        │
        ├── Anthropic SDK → Rakuten AI Gateway  (Claude Sonnet 4)
        ├── Gmail API                            (email delivery)
        └── JIRA REST API                        (ticket creation)

PostgreSQL (:5432)
  - LangGraph checkpoint table  (conversation state across turns)
  - app.sessions                (session metadata)
  - app.prds                    (generated PRD records)
```

No queue. No worker processes. No Redis. No separate n8n service.
LangGraph runs inside FastAPI as a library call.

---

## LangGraph design

### State

```python
class PRDState(TypedDict):
    session_id:      str
    messages:        list[BaseMessage]   # full conversation history
    mode:            str                 # "analyze" | "generate" | "done"
    context_summary: str                 # extracted when Sam is ready
    prd_markdown:    str                 # generated PRD
    quality_score:   int                 # 0-100
    grade:           str                 # A-F
    file_name:       str
    # set by HITL email interrupt
    recipient_email: str
    recipient_name:  str
    # set by HITL JIRA interrupt
    jira_decision:   str                 # "approve" | "skip"
```

### Nodes and edges

```
[START]
   │
   ▼
analyze          Sam asks questions using Claude (Rakuten gateway).
   │             System prompt: requirements gathering mode.
   ▼
route_action     Conditional edge. Inspects last message:
   │             - GENERATE_PRD: signal detected → generate_prd
   │             - PRD complete (>2000 chars, 4+ sections) → validate
   │             - Otherwise → back to analyze (loop)
   │
   ├── [analyze]          (loop back for next user turn)
   │
   ├── generate_prd       DevBridge prompt. One-shot full PRD generation.
   │       │
   │       ▼
   │   route_action       Same check — when PRD complete → validate
   │
   └── validate           Score PRD 0-100. Attach grade + summary.
           │
           ▼
       email_interrupt     HITL pause. Suspend execution, return resume URL
           │               to client in response. Client shows email form.
           │               Resumes via POST /sessions/{id}/resume.
           ▼
       send_email          Gmail API. Attach PRD as markdown file.
           │
           ▼
       jira_interrupt      HITL pause. Same pattern — show approval form.
           │               Resumes with decision: "approve" | "skip".
           ▼
       create_jira         If approved: Epic → Tasks → Subtasks via JIRA REST.
           │               If skipped: pass through.
           ▼
         [END]
```

### HITL — how it works

LangGraph has a built-in `interrupt()` function (v0.2+). When a node calls it,
execution suspends. The checkpointer saves full state to PostgreSQL.
The API returns the interrupt payload (resume URL) to the frontend.
When the user submits the form, the frontend POSTs to `/sessions/{id}/resume`.
FastAPI loads the checkpoint and continues the graph from the suspended node.

```python
# email_interrupt node
def email_gate(state: PRDState) -> dict:
    form_data = interrupt({          # suspends here, saves state
        "type": "email_form",
        "message": "Fill in your details to receive the PRD by email."
    })
    return {
        "recipient_email": form_data["email"],
        "recipient_name":  form_data["name"],
    }
```

This replaces n8n's Wait node. No task queue needed — state lives in PostgreSQL.

---

## File structure

```
team-syncv2.0-fullstack/
│
├── PLAN.md                        ← this file
│
├── backend/
│   ├── src/
│   │   ├── graph/
│   │   │   ├── state.py           PRDState TypedDict
│   │   │   ├── nodes.py           all node functions (analyze, generate, validate, ...)
│   │   │   ├── edges.py           route_action conditional logic
│   │   │   └── graph.py           compiled StateGraph, checkpointer setup
│   │   ├── routers/
│   │   │   ├── chat.py            POST /api/v1/chat
│   │   │   └── sessions.py        GET /api/v1/sessions/{id}/prd
│   │   │                          POST /api/v1/sessions/{id}/resume
│   │   ├── services/
│   │   │   ├── ai.py              AsyncAnthropic client (Rakuten gateway)
│   │   │   ├── email.py           Gmail API via google-auth
│   │   │   └── jira.py            JIRA REST API via httpx
│   │   ├── config.py              pydantic-settings, reads .env
│   │   └── main.py                FastAPI app, router registration
│   ├── tests/
│   │   ├── test_graph.py          test analyze → generate → validate flow
│   │   ├── test_jira.py
│   │   └── conftest.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/                      keep existing React/Vite as-is
│   └── ...                        only change: point API calls to FastAPI
│
└── docker-compose.yml             postgres + backend + frontend (3 services only)
```

---

## Phases

### Phase 1 — Core graph, no integrations
> Goal: chat → PRD generated and returned to the frontend. Nothing else.

- `PRDState`, all nodes, `route_action` edge
- `POST /api/v1/chat` streams LangGraph execution, returns response per turn
- PostgreSQL checkpointer so conversation persists across browser refreshes
- Anthropic SDK via Rakuten gateway for both analyze and generate nodes
- PRD quality scoring in `validate` node (same logic as current n8n node)
- Frontend: update API client to call FastAPI instead of n8n webhook

**Done when:** you can go from "I want to build X" → scored PRD in the browser.

### Phase 2 — HITL gates + integrations
> Goal: email delivery and JIRA creation work end-to-end.

- `email_interrupt` and `jira_interrupt` nodes using LangGraph `interrupt()`
- `POST /api/v1/sessions/{id}/resume` resumes the suspended graph
- Gmail API client (`src/services/email.py`) — sends PRD as attachment
- JIRA REST client (`src/services/jira.py`) — creates Epic + Tasks + Subtasks
  using the same extraction logic from the current n8n `Extract JIRA content` node
- Frontend: show email form and JIRA approval form inline (no redirect)

**Done when:** full flow works end-to-end: chat → PRD → email → JIRA.

### Phase 3 — Polish
> Goal: the tool feels finished for the team.

- PRD history page (list past sessions, reopen any PRD)
- Session persistence — browser can close and reopen mid-conversation
- Error messages that make sense to users (not stack traces)
- `docker compose up` and a 1-page setup guide. That's it.

---

## Key dependencies

```
langgraph>=0.2.0                   state machine + HITL + checkpointer
langgraph-checkpoint-postgres       PostgreSQL state persistence
anthropic>=0.40.0                  Claude via Rakuten gateway
google-auth-oauthlib               Gmail API auth
google-api-python-client           Gmail API
httpx                              JIRA REST calls
fastapi + uvicorn                  API server
sqlalchemy + asyncpg               DB for session/PRD records
pydantic-settings                  config
```

---

## What this is NOT building

- No staging CI/CD pipelines
- No container registry push scripts
- No multi-stage Dockerfiles until Phase 3
- No rate limiting (internal tool, small team)
- No JWT auth (API key is enough for now)
- No Next.js migration (React/Vite frontend works fine)
- No Ollama (team uses Rakuten, local fallback not worth the complexity)

---

## One open question before starting

The `interrupt()` pattern requires the frontend to know when execution is suspended
vs. still running vs. finished. Three approaches for the chat API:

**A — Polling:** `POST /chat` starts execution, returns a `session_id`.
Frontend polls `GET /sessions/{id}/status` until status = `interrupted | done`.

**B — SSE streaming:** `POST /chat` opens a Server-Sent Events stream.
LangGraph streams intermediate messages. When interrupted, stream sends an
`interrupt` event with the form type.

**C — WebSocket:** Bidirectional. More complex, same outcome as SSE for this case.

**Recommendation: B (SSE).** The frontend already handles streaming chat from n8n.
FastAPI supports SSE natively. Cleanest user experience — no polling loop.

Pick one and confirm before Phase 1 starts.
