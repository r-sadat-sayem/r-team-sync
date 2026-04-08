# TeamSync AI — System Design
> Version 2.0 | LangGraph + Anthropic SDK + FastAPI
> Last updated: 2026-04-06

---

## 1. What this product does

TeamSync AI eliminates the manual work between "we have a product idea" and "tickets are in JIRA."

A team member describes what they want to build in a chat interface. An AI analyst (Sam) gathers requirements through conversation. When enough context is collected, a second AI persona (DevBridge) generates a complete, scored Product Requirements Document. The PRD is emailed as a markdown attachment, and — with one approval click — a full JIRA hierarchy (Epic → Stories → Subtasks) is created under the submitting user's own Atlassian identity.

The whole cycle takes 5–10 minutes instead of hours.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│                                                                              │
│   React / Vite Frontend  (http://localhost:5173)                            │
│   ┌──────────────┐  ┌─────────────────────────────────────────────────┐    │
│   │  Chat UI     │  │  PRD Viewer  │  Email Form  │  JIRA Form        │    │
│   │  (SSE reader)│  │  (markdown)  │  (interrupt) │  (interrupt)      │    │
│   └──────┬───────┘  └─────────────────────────┬───────────────────────┘    │
│          │  POST /api/v1/chat                  │  POST /api/v1/sessions/    │
│          │  (text/event-stream)                │  {id}/resume               │
└──────────┼─────────────────────────────────────┼────────────────────────────┘
           │                                     │
           ▼                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           FastAPI Backend  (:8000)                            │
│                                                                               │
│   Routers                         Middleware                                  │
│   ├── /api/v1/chat        ──────► X-API-Key auth                            │
│   ├── /api/v1/sessions/{id}                                                  │
│   │   ├── GET  (state snapshot)   Services                                   │
│   │   ├── GET  /prd               ├── email.py   Gmail SMTP                  │
│   │   └── POST /resume (SSE)      ├── jira.py    JIRA REST v3                │
│   ├── /api/v1/ai/query            └── (ai calls go through graph nodes)      │
│   └── /api/v1/jira/auth/*                                                    │
│       ├── GET  /connect                                                       │
│       ├── GET  /callback  ◄── Atlassian OAuth redirect                       │
│       ├── GET  /status                                                        │
│       └── DELETE /disconnect                                                  │
│                                                                               │
│   ┌───────────────────────────────────────────────────────────────────────┐  │
│   │                   LangGraph Workflow  (in-process)                    │  │
│   │                                                                       │  │
│   │   START                                                               │  │
│   │     │ route_entry (mode?)                                             │  │
│   │     ├─► analyze ──────────────────────────────────────────────┐      │  │
│   │     │   (Sam: requirements gathering)  route_after_analyze     │      │  │
│   │     │                │ GENERATE_PRD signal detected            │      │  │
│   │     └─► generate_prd ◄───────────────────────────────────────-┘      │  │
│   │         (DevBridge: one-shot PRD, 8192 tokens)                        │  │
│   │                │                                                       │  │
│   │             validate                                                   │  │
│   │         (score 0-100, derive filename)                                 │  │
│   │                │                                                       │  │
│   │         email_interrupt  ◄── HITL pause 1: user submits email form    │  │
│   │                │                                                       │  │
│   │           send_email                                                   │  │
│   │         (Gmail SMTP, PRD as .md attachment)                            │  │
│   │                │                                                       │  │
│   │         jira_interrupt   ◄── HITL pause 2: user approves + assignee   │  │
│   │                │ route_after_jira (approve/skip)                       │  │
│   │           create_jira                                                  │  │
│   │         (Epic → Stories → Subtasks, notification email)                │  │
│   │                │                                                       │  │
│   │              END                                                       │  │
│   │                                                                       │  │
│   │   State persisted across turns via PostgreSQL checkpointer            │  │
│   └───────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
┌─────────────────┐  ┌──────────────────┐  ┌────────────────────────────────┐
│  PostgreSQL      │  │  Rakuten AI      │  │  External Services             │
│  (:5432)         │  │  Gateway         │  │                                │
│                  │  │                  │  │  Gmail SMTP  (port 465 SSL)    │
│  • LangGraph     │  │  Anthropic SDK   │  │  JIRA REST API v3              │
│    checkpoints   │  │  (auth_token)    │  │  Atlassian OAuth               │
│    (session      │  │                  │  │  (auth.atlassian.com)          │
│    state across  │  │  Claude Haiku    │  │                                │
│    turns)        │  │  (or Sonnet)     │  │                                │
│                  │  │  • analyze mode  │  │                                │
│  • app schema    │  │  • generate mode │  │                                │
│    (PRDs,        │  │  • web search    │  │                                │
│    sessions —    │  │    (available)   │  │                                │
│    Phase 3)      │  │                  │  │                                │
└─────────────────┘  └──────────────────┘  └────────────────────────────────┘
```

---

## 3. Component Responsibilities

| Component | Owns | Does NOT own |
|---|---|---|
| **React Frontend** | UI rendering, SSE stream parsing, form display | Business logic, direct LLM calls |
| **FastAPI** | HTTP routing, auth, SSE streaming, JIRA OAuth flow | Workflow orchestration |
| **LangGraph** | Conversation state machine, HITL interrupts, PRD pipeline | HTTP, email, user auth |
| **Nodes (analyze / generate_prd)** | LLM prompt construction, streaming tokens, signal detection | State routing |
| **Nodes (email_interrupt / jira_interrupt)** | Suspend execution, describe what form to show | Rendering the form |
| **Services (email.py / jira.py)** | External API calls, asyncio.to_thread for sync libs | Graph logic |
| **PostgreSQL** | Durable session state across browser refreshes and server restarts | Any business logic |
| **Rakuten AI Gateway** | LLM inference, web search | Orchestration |

---

## 4. User Flow

```
User                    Frontend              Backend/Graph           External
─────                   ────────              ─────────────           ────────

  1. Opens app
      │
      ├──────────────► Loads chat UI
      │
  2. Types: "I want to                                                      
     build an expense
     tracker"
      │
      ├──────────────► POST /api/v1/chat ──► Graph starts
      │                SSE stream opens       route_entry → analyze
      │                                       Calls Rakuten AI (Claude)
      │
      │                {"type":"token","content":"Great!"}
      │                {"type":"token","content":" What platform..."}
      │◄──────────────  append to bubble
      │                {"type":"turn_end","session_id":"abc"}
      │
  3. User answers
     questions (2-4
     more turns, same
     flow as step 2)
      │
  4. Sam detects enough context, emits GENERATE_PRD signal
      │
      ├──────────────► POST /api/v1/chat ──► analyze detects signal
      │                                       mode = "generate"
      │                                       route_after_analyze → generate_prd
      │                                       Calls Rakuten AI (8192 tokens)
      │
      │                {"type":"status","message":"Writing PRD..."}
      │                {"type":"token","content":"# Classification..."}
      │                  ... (hundreds of token events) ...
      │                {"type":"prd_complete","score":87,"grade":"B"}
      │                {"type":"interrupt","form":"email_form","score":87}
      │◄──────────────  show PRD + email form inline
      │                {"type":"turn_end"}
      │
  5. User fills email
     form (name +
     email)
      │
      ├──────────────► POST /sessions/abc/resume ──► email_interrupt resumes
      │                {"data":{"name":"...","email":"..."}}  send_email runs
      │                                                       ──────────────────►
      │                                                                    Gmail SMTP
      │                                                                    PRD .md sent
      │                {"type":"email_sent","recipient":"..."}◄────────────
      │                {"type":"interrupt","form":"jira_form",
      │                 "jira_connected":false,
      │                 "connect_url":"/api/v1/jira/auth/connect?..."}
      │◄──────────────  show JIRA form + "Connect JIRA" button
      │                {"type":"turn_end"}
      │
  6. User clicks
     "Connect JIRA"
      │
      ├──────────────► GET /jira/auth/connect?session_id=abc
      │◄──────────────  {url: "https://auth.atlassian.com/..."}
      │
      ├─ opens OAuth tab ─────────────────────────────────────────────────────►
      │                                                                   Atlassian
      │                                                                   login page
      │                  User logs in, grants permission
      │◄─ tab redirects ──────────────────────────────────────────────────────
      │                  GET /jira/auth/callback?code=...&state=abc
      │                         exchange code for token
      │                         fetch cloud ID + user info
      │                         store in token_store[abc]
      │                  self-closing HTML tab: "Connected as Sadat on MyOrg"
      │
      ├──────────────► GET /jira/auth/status?session_id=abc
      │◄──────────────  {connected:true, user_name:"Sadat", cloud_name:"MyOrg"}
      │                 update form UI: "Connected as Sadat ✓"
      │
  7. User fills JIRA
     form: decision=
     "approve",
     assignee=team@...
      │
      ├──────────────► POST /sessions/abc/resume ──► jira_interrupt resumes
      │                {"data":{"decision":"approve",    create_jira runs
      │                 "assignee_email":"team@...",       JiraService.for_session(abc)
      │                 "notes":"Urgent"}}                 uses OAuth token
      │                                                   ────────────────────────────►
      │                                                                     JIRA API
      │                                                                     Epic created
      │                                                                     3 Stories
      │                                                                     9 Subtasks
      │                {"type":"jira_created",           ◄────────────────────────────
      │                 "epic_key":"TSA-42",
      │                 "task_keys":["TSA-43","TSA-44","TSA-45"]}
      │                {"type":"notification_sent",
      │                 "to":"team@..."}
      │◄──────────────  show JIRA links + success screen
      │                {"type":"turn_end"}
      │
  Done. PRD in inbox. JIRA board updated. 5-10 minutes total.
```

---

## 5. SSE Event Contract

Every `data:` line in the stream is a JSON object. Frontend behaviour per `type`:

| `type` | Frontend action |
|---|---|
| `token` | Append `content` to current message bubble |
| `status` | Show transient progress label (spinner) |
| `prd_complete` | Render quality badge `{score}/100 Grade {grade}`, enable download |
| `email_sent` | Show confirmation banner |
| `interrupt` | Hide typing indicator, render the appropriate inline form |
| `jira_created` | Render clickable links for `epic_key` + `task_keys` |
| `notification_sent` | Show "notification sent to {to}" |
| `turn_end` | Hide spinner, store `session_id`, re-enable input |
| `error` | Show error toast, re-enable input |

**Interrupt payload shapes** (received when `type === "interrupt"`):

```jsonc
// Email form
{
  "form": "email_form",
  "message": "Your PRD is ready!",
  "fields": ["name", "email"],
  "score": 87,
  "grade": "B"
}

// JIRA approval form
{
  "form": "jira_form",
  "message": "Approve JIRA ticket creation.",
  "fields": ["decision", "assignee_email", "notes"],
  "hint": "Type 'approve' or 'skip'",
  "jira_connected": false,
  "connect_url": "/api/v1/jira/auth/connect?session_id=abc"  // null if already connected
}
```

---

## 6. JIRA Authentication Flow

```
                    ┌─────────────┐
                    │   Frontend  │
                    └──────┬──────┘
                           │ GET /jira/auth/connect?session_id=abc
                           ▼
                    ┌─────────────┐
                    │  FastAPI    │
                    │  /connect   │  builds OAuth URL with state=abc
                    └──────┬──────┘
                           │ returns {url: "https://auth.atlassian.com/..."}
                           │
                           ▼
         ┌────── Frontend opens URL in new tab ──────┐
         │                                            │
         │           ┌──────────────────┐             │
         │           │   Atlassian      │             │
         │           │   OAuth Page     │             │
         │           │                  │             │
         │           │  User logs in    │             │
         │           │  Grants scopes:  │             │
         │           │  read:jira-work  │             │
         │           │  write:jira-work │             │
         │           │  offline_access  │             │
         │           └────────┬─────────┘             │
         │                    │ redirect to /callback  │
         │                    ▼                        │
         │           ┌──────────────────┐             │
         │           │  FastAPI         │             │
         │           │  /callback       │             │
         │           │                  │             │
         │           │  1. Exchange code │             │
         │           │     for tokens   │             │
         │           │  2. GET /oauth/  │             │
         │           │     accessible-  │             │
         │           │     resources    │             │
         │           │  3. GET /myself  │             │
         │           │  4. Store token  │             │
         │           │     keyed by abc │             │
         │           └────────┬─────────┘             │
         │                    │ returns self-closing    │
         │                    │ HTML tab               │
         └────────────────────┘                        │
                                                       │
         Parent tab receives postMessage ──────────────┘
         Polls GET /jira/auth/status?session_id=abc
         Gets {connected: true, user_name: "Sadat"}
```

Token store is currently in-process memory. Each call to `JiraService.for_session(session_id)` looks up the token and uses the Atlassian API with the user's OAuth Bearer token — JIRA board permissions enforced server-side.

---

## 7. Data Flow Through LangGraph State

```
PRDState fields and which node writes them:

  messages          ← append_messages reducer; written by analyze + generate_prd
  mode              ← written by analyze (when GENERATE_PRD: detected)
  context_summary   ← written by analyze (extracted from GENERATE_PRD: block)
  prd_markdown      ← written by generate_prd
  quality_score     ← written by validate
  grade             ← written by validate
  file_name         ← written by validate
  recipient_name    ← written by email_interrupt (from form resume)
  recipient_email   ← written by email_interrupt (from form resume)
  jira_decision     ← written by jira_interrupt  (from form resume)
  jira_assignee_email ← written by jira_interrupt
  jira_notes        ← written by jira_interrupt
  epic_key          ← written by create_jira
  epic_url          ← written by create_jira
  task_keys         ← written by create_jira (append reducer)
```

All state is persisted to PostgreSQL at each node transition via LangGraph's `AsyncPostgresSaver`. A browser refresh, server restart, or network drop does not lose conversation state.

---

## 8. Security Model

| Boundary | Control |
|---|---|
| Frontend → Backend | `X-API-Key` header on all `/api/v1/*` routes |
| Backend → Rakuten AI | `Authorization: Bearer` via `auth_token` in Anthropic SDK |
| Backend → JIRA (OAuth) | Per-session Bearer token from Atlassian OAuth, scoped to `read/write:jira-work` |
| Backend → JIRA (fallback) | `(JIRA_EMAIL, JIRA_API_TOKEN)` basic auth from `.env` |
| Backend → Gmail | App Password from `.env`, SMTP over SSL/465 |
| Backend → PostgreSQL | Internal Docker network only, never exposed on host |
| Secrets | `.env` (never committed), generated once via `make setup` |

**What is NOT protected yet (Phase 3+):**
- No user identity — any request with the right `X-API-Key` can read any session
- JIRA OAuth tokens are in-process memory — server restart requires re-auth
- No CSRF protection on the OAuth callback (state param is the session ID, not a secret nonce)

---

## 9. Future Improvements

### Near-term (Phase 3 / next sprint)

| Item | Why |
|---|---|
| **Wire React frontend** | Current backend is complete but has no UI connected. SSE contract is fully defined. |
| **Persist JIRA OAuth tokens to PostgreSQL** | In-memory tokens are lost on restart. A `jira_tokens` table with expiry + refresh logic. |
| **Add CSRF nonce to OAuth state param** | State param currently carries only `session_id`. Should be `session_id:random_nonce` verified on callback. |
| **Per-user sessions** | All sessions currently share one `X-API-Key`. Add a `users` table, JWT auth, and scope sessions per user. |
| **PRD history dashboard** | Store completed PRDs in `app.prds` PostgreSQL table. List, search, and re-open past PRDs. |

### Medium-term

| Item | Why |
|---|---|
| **Web search in PRD generation** | Rakuten gateway supports `web_search_20250305` tool. Sam could research competitor products or industry standards during requirements gathering to produce higher quality PRDs. |
| **Confluence export** | Publish PRD directly to a Confluence page via Atlassian REST API (shares auth with JIRA OAuth). |
| **Slack / Teams notifications** | Notify the team channel when a PRD is created and JIRA tickets are live, instead of only emailing the assignee. |
| **JIRA webhook sync** | Listen for JIRA ticket updates (status changes) and surface them in the chat history for that session. |
| **Retry / resume on error** | If `send_email` or `create_jira` fails, currently the graph errors out. Add retry logic with exponential backoff and a user-visible "retry" option. |

### Longer-term / architectural

| Item | Why |
|---|---|
| **RAG over past PRDs** | Index all generated PRDs in a vector store. Sam can reference similar past projects during requirements gathering, improving consistency across the team. |
| **Multi-product / multi-board routing** | Teams with multiple JIRA boards can specify which project at the JIRA approval step rather than always using the configured default. |
| **LangGraph multi-agent** | Replace the dual-mode single agent (Sam + DevBridge in one prompt) with two proper LangGraph agents sharing a supervisor. Cleaner separation, easier to tune each independently. |
| **Streaming PRD to a shared editing surface** | Instead of emailing a static file, stream the PRD into a collaborative editor (Notion, Confluence, or a custom block editor) so the team can annotate in real time. |
| **Replace `X-API-Key` with proper auth** | SSO via Atlassian OAuth (already integrated) — the same flow used for JIRA can authenticate the user into the app. Zero additional credentials for the team to manage. |
| **n8n fully retired** | The v1 n8n workflow still runs alongside v2.0. Once the React frontend is wired and team validates the full flow, retire n8n and simplify the deployment to 2 services (postgres + backend). |
