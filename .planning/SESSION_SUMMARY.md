# TeamSync — Session Summary
> Last updated: 2026-04-06 | Git: 2 commits on `main`

---

## What was decided (architecture)

| Decision | Chosen | Reason |
|---|---|---|
| Workflow engine | ~~n8n~~ → **LangGraph** | n8n logic lived in JSON-escaped JS strings. LangGraph is testable Python. |
| Backend language | **FastAPI (Python)** | Replaces empty Node.js scaffold. Async, auto-docs, type-safe. |
| AI provider | **Rakuten AI Gateway** (Anthropic SDK) | Team has internet access, Rakuten gateway available. Ollama dropped. |
| Claude model | `claude-haiku-4-5-20251001` | User confirmed in `.env`. Earlier attempt at `claude-sonnet-4-20250514` and `claude-3-7-sonnet-20250219` — both had issues on gateway. Haiku works. |
| HITL pattern | **LangGraph `interrupt()` + SSE resume** | n8n Wait node equivalent, no task queue needed. State persists in PostgreSQL. |
| Email | **Gmail SMTP + App Password** | Simpler than copying OAuth tokens out of n8n. |
| Frontend | **Keep existing React/Vite** | Already 60% built. Migration to Next.js deferred — not worth the churn yet. |

---

## Repository layout

```
/
├── team-syncv2.0-fullstack/        ← ACTIVE: LangGraph full-stack app
│   ├── PLAN.md                     ← Phase 1/2/3 plan with SSE decision
│   ├── docker-compose.yml          ← postgres + backend (frontend commented out)
│   └── backend/
│       ├── .env.example            ← all required vars documented
│       ├── Dockerfile              ← multi-stage: dev (hot-reload) + prod
│       ├── requirements.txt
│       ├── requirements-dev.txt
│       ├── src/
│       │   ├── config.py           ← pydantic-settings, all env vars
│       │   ├── main.py             ← FastAPI app, lifespan boots graph
│       │   ├── graph/
│       │   │   ├── state.py        ← PRDState TypedDict (single source of truth)
│       │   │   ├── nodes.py        ← all 7 node functions
│       │   │   ├── edges.py        ← routing functions (3 total)
│       │   │   └── graph.py        ← compiled graph + checkpointer setup
│       │   ├── routers/
│       │   │   ├── chat.py         ← POST /api/v1/chat (SSE)
│       │   │   ├── sessions.py     ← GET /sessions/{id}, GET /sessions/{id}/prd
│       │   │   │                      POST /sessions/{id}/resume (SSE)
│       │   │   └── ai.py           ← POST /api/v1/ai/query (direct AI call)
│       │   ├── services/
│       │   │   ├── email.py        ← Gmail SMTP, asyncio.to_thread
│       │   │   └── jira.py         ← JIRA REST v3, assignee by email lookup
│       │   └── middleware/
│       │       └── auth.py         ← X-API-Key header validation
│       └── tests/
│           ├── conftest.py         ← in-memory graph fixture
│           └── test_graph.py       ← 14 tests (routing, scoring, mocked LLM)
│
├── team_sync_dev_v2.1_with_JIRA.json  ← FIXED n8n workflow (v2.2)
├── demo.html                          ← UPDATED: inline config panel
├── pipeline/                          ← Makefile, scripts, docker, nginx, CI/CD
├── .planning/
│   ├── IMPLEMENTATION_PLAN.md         ← 5-phase plan (Next.js + FastAPI)
│   └── SESSION_SUMMARY.md             ← this file
└── .gitignore
```

---

## Changes per file

### `team-syncv2.0-fullstack/` — created from scratch

#### `src/graph/state.py`
- `PRDState` TypedDict with 15 fields
- Custom `_append` reducer for messages (Anthropic dict format, no LangChain wrappers)
- Added Phase 2 fields: `jira_assignee_email`, `jira_notes`, `epic_key`, `epic_url`, `task_keys`

#### `src/graph/nodes.py`
- `analyze` — Sam requirements gathering via streaming Anthropic SDK. Detects `GENERATE_PRD:` signal, sets `mode="generate"`.
- `generate_prd` — DevBridge one-shot PRD generation (8192 tokens). Uses `context_summary` from state.
- `validate` — Scores PRD 0-100 (same algorithm as n8n `Validate PRD Quality` node). Derives filename from PRD content.
- `email_interrupt` — Calls `langgraph.types.interrupt()`. Suspends. Resumes with `{name, email}`.
- `send_email` — Calls `email.send_prd_email()` via `asyncio.to_thread`.
- `jira_interrupt` — Calls `interrupt()`. Suspends. Resumes with `{decision, assignee_email, notes}`.
- `create_jira` — Calls `jira.create_from_prd()`. Emits `jira_created` event. Then sends notification email to assignee.

#### `src/graph/edges.py`
- `route_entry` — START routing: `mode=="generate" AND no prd_markdown` → `generate_prd`, else → `analyze`
- `route_after_analyze` — Post-analyze: `mode=="generate" AND no prd_markdown` → `generate_prd`, else → END
- `route_after_jira` — Post-jira form: `decision=="approve"` → `create_jira`, else → END

#### `src/graph/graph.py`
- Full Phase 2 graph: `analyze → generate_prd → validate → email_interrupt → send_email → jira_interrupt → [route] → create_jira → END`
- PostgreSQL checkpointer (`AsyncPostgresSaver`) in prod, `MemorySaver` for tests
- `get_default_state()` initialises all 15 fields

#### `src/routers/chat.py`
- SSE stream via `graph.astream(..., stream_mode="custom")`
- After stream ends: checks `snapshot.tasks` for interrupt, forwards interrupt payload as `{"type":"interrupt", ...}` event
- Auto-generates `session_id` (UUID) if not provided

#### `src/routers/sessions.py`
- `GET /sessions/{id}` — returns state snapshot + interrupt payload if suspended
- `GET /sessions/{id}/prd` — returns PRD markdown + quality metadata
- `POST /sessions/{id}/resume` — SSE stream via `graph.astream(Command(resume=data), ...)`
- Pre-validates session exists AND is actually interrupted (returns 409 if not)

#### `src/routers/ai.py`
- `POST /api/v1/ai/query` — direct Anthropic SDK call, bypasses graph
- `GET /api/v1/ai/providers` — lists configured providers and models

#### `src/services/email.py`
- `send_prd_email()` — builds MIME multipart, attaches `.md` file, sends via SMTP_SSL
- `send_jira_notification()` — sends ticket links to assignee after JIRA creation
- `_smtp_send()` — sync function called via `asyncio.to_thread` (keeps event loop free)

#### `src/services/jira.py`
- `extract_jira_items()` — parses PRD markdown: epic title from `**Project Name**`, stories from `FR\d+`, subtasks from `TC\d+`
- `JiraService.get_account_id()` — resolves email → JIRA account ID via `/rest/api/3/user/search`
- `JiraService.create_from_prd()` — orchestrates: Epic → Stories (all FRs) → Subtasks (all TCs under first story)
- All issue types configurable: `JIRA_EPIC_TYPE`, `JIRA_STORY_TYPE`, `JIRA_SUBTASK_TYPE`

---

### `team_sync_dev_v2.1_with_JIRA.json` → v2.2

| What changed | Why |
|---|---|
| `Primary LLM` + `Fallback LLM`: `lmChatOllama` → `lmChatOpenAi` (Rakuten endpoint) | Ollama is local-only; team has internet |
| Added `Check JIRA Approval` IF node after `Approve JIRA Creation` Wait | **Bug fix**: tickets were always created regardless of what user typed |
| JIRA branch sticky note updated | Documents the fix |
| Credential references updated to `Rakuten AI Gateway` | Placeholder for n8n credential setup |

### `demo.html`

- Added inline `Configure` button in topbar
- Added config overlay panel (modal) with URL input and Save/Clear buttons
- URL resolution priority: `config.js` (Docker) → `?url=` query param → `localStorage` → auto-open panel
- Config panel auto-opens 800ms after load if nothing is configured
- No Docker or `config.js` required for local testing

### `pipeline/` — created from scratch

22 files covering: `Makefile`, `scripts/` (setup, dev, build, deploy, backup, workflow import/export), `docker/` (docker-compose dev/prod/demo, .env.example, init-db.sql), `nginx/` (prod + dev configs), `ci-cd/` (GitHub Actions CI, staging deploy, prod deploy), `docs/` (architecture, setup, API reference).

---

## SSE event contract (frontend integration spec)

Every SSE `data:` line is a JSON object with a `type` field.

| `type` | When emitted | Payload |
|---|---|---|
| `token` | LLM streaming | `{content: "..."}` — append to current message bubble |
| `status` | Node transitions | `{message: "..."}` — show as progress indicator |
| `prd_complete` | After `validate` | `{score, grade, file_name}` — show quality badge |
| `email_sent` | After `send_email` | `{recipient}` — confirm delivery |
| `interrupt` | After `email_interrupt` or `jira_interrupt` | See below |
| `jira_created` | After `create_jira` | `{epic_key, epic_url, task_keys}` |
| `notification_sent` | After notification email | `{to}` |
| `turn_end` | Every turn | `{session_id}` — hide typing indicator, store session_id |
| `error` | Any exception | `{message}` — show error toast |

**Interrupt payload shapes:**

```json
// email_form interrupt
{
  "type": "interrupt",
  "form": "email_form",
  "message": "Your PRD is ready! Enter your details to receive it by email.",
  "fields": ["name", "email"],
  "score": 87,
  "grade": "B"
}

// jira_form interrupt
{
  "type": "interrupt",
  "form": "jira_form",
  "message": "Review the PRD and approve JIRA ticket creation.",
  "fields": ["decision", "assignee_email", "notes"],
  "hint": "Type 'approve' to create tickets or 'skip' to finish without JIRA."
}
```

---

## Running state

```bash
cd team-syncv2.0-fullstack
docker compose up -d          # postgres + backend
# backend hot-reloads on src/ changes

docker compose up -d          # after changing .env
docker compose up --build -d  # after changing Dockerfile or requirements.txt
```

Services:
- `http://localhost:8000/health`   — liveness
- `http://localhost:8000/docs`     — Swagger UI (all endpoints)
- `http://localhost:5432`          — PostgreSQL (internal only)

Auth: `X-API-Key: dev-change-me` on all `/api/v1/*` requests.

---

## Phase 3 — Frontend wiring (NEXT)

**Goal:** Connect the existing React/Vite frontend to the LangGraph backend. Replace direct n8n webhook calls with FastAPI calls. Render SSE events in real time.

### What needs to change in the frontend

| File | Change |
|---|---|
| `src/services/api.ts` | Replace `TeamSyncAPI` n8n webhook calls with `fetch` to `http://localhost:8000/api/v1/chat` (SSE) and `/sessions/{id}/resume` (SSE) |
| `src/types/index.ts` | Add `InterruptEvent`, `JiraCreatedEvent`, `PRDCompleteEvent` types matching SSE contract above |
| `src/context/AppContext.tsx` | Add `interruptState` to `AppState` (which form to show, null if none) |
| `src/components/chat/ChatInterface.tsx` | Replace polling/webhook response with `EventSource` or `fetch` streaming reader |
| `src/components/chat/` | Add `EmailForm.tsx` — shown when `interrupt.form === "email_form"` |
| `src/components/chat/` | Add `JiraApprovalForm.tsx` — shown when `interrupt.form === "jira_form"` |
| `src/components/prd/PRDViewer.tsx` | Show quality score badge, download button, JIRA links |
| `frontend/.env` | Add `VITE_API_URL=http://localhost:8000`, `VITE_API_KEY=dev-change-me` |

### SSE streaming pattern for the frontend

```typescript
// Replace n8n webhook fetch with this pattern
async function* streamChat(message: string, sessionId?: string) {
  const res = await fetch(`${API_URL}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop()!;
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        yield JSON.parse(line.slice(6));
      }
    }
  }
}
```

### Resume pattern

```typescript
// After user submits email form
async function* resumeSession(sessionId: string, formData: Record<string, string>) {
  const res = await fetch(`${API_URL}/api/v1/sessions/${sessionId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
    body: JSON.stringify({ data: formData }),
  });
  // same SSE reader as above
}
```

---

## Deferred / future work

| Item | Status | Notes |
|---|---|---|
| Phase 3: Frontend wiring | **Next** | See above |
| JIRA subtask loop (all stories) | Deferred | Currently subtasks only attach to first story. Loop all stories in Phase 3+ |
| Rakuten AI web search | Future | Available via `web_search_20250305` tool — add to `ai/query` endpoint when needed |
| n8n workflow → fully retire | Future | Keep running until Phase 3 frontend is validated by team |
| Error workflow (n8n) | Not done | n8n still has no global error handler; low priority since we're moving off it |
| Tests for Phase 2 nodes | Not done | `test_graph.py` covers Phase 1 only; need mocked email + JIRA tests |
| Rate limiting | Not done | `slowapi` is in requirements but not wired up. Add when team size warrants it |
