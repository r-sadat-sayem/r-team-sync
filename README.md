# TeamSync AI v2.0

An AI-powered Product Requirements Document (PRD) automation tool. Describe a product idea in a chat interface, get a scored PRD, email it, and create a full JIRA ticket hierarchy — all without leaving the conversation.

**Time from idea to JIRA board: 5–10 minutes.**

---

## Table of Contents

- [What It Does](#what-it-does)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
  - [Docker (recommended)](#docker-recommended)
  - [Local Development](#local-development)
- [Configuration](#configuration)
  - [Backend Environment Variables](#backend-environment-variables)
  - [Frontend Environment Variables](#frontend-environment-variables)
- [Features](#features)
  - [Conversational Requirements Gathering](#conversational-requirements-gathering)
  - [PRD Generation and Scoring](#prd-generation-and-scoring)
  - [Gmail Integration](#gmail-integration)
  - [JIRA Integration](#jira-integration)
  - [Multi-Tab Sessions](#multi-tab-sessions)
  - [History and Dashboard](#history-and-dashboard)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
  - [Auth](#auth)
  - [Chat](#chat)
  - [Sessions](#sessions)
  - [JIRA](#jira)
  - [Gmail](#gmail)
- [LangGraph Workflow](#langgraph-workflow)
  - [Nodes](#nodes)
  - [HITL Interrupts](#hitl-interrupts)
  - [SSE Event Contract](#sse-event-contract)
- [Database Schema](#database-schema)
- [Frontend Routes](#frontend-routes)
- [Development Notes](#development-notes)

---

## What It Does

1. **Chat with Sam** — an AI analyst who asks targeted questions to gather your product requirements.
2. **Approve the outline** — Sam generates a structured outline before writing the full PRD, so you can catch direction issues early.
3. **Receive a scored PRD** — DevBridge (AI generator) writes a complete PRD, scored 0–100 with a letter grade.
4. **Email it** — send the PRD as a `.md` attachment to any recipient via connected Gmail.
5. **Create JIRA tickets** — one click creates an Epic → Stories → Subtasks hierarchy under your Atlassian identity.

---

## Architecture

```
Browser (React / Vite)
        │  POST /api/v1/chat  (SSE stream)
        │  POST /api/v1/sessions/{id}/resume  (SSE stream)
        ▼
FastAPI  (:8000)
  ├── Routers: auth, chat, sessions, jira_auth, email_auth, ai
  ├── Middleware: cookie-based session auth
  └── LangGraph (in-process)
        │  State persisted via PostgreSQL checkpointer
        ├── Anthropic (Claude) via Rakuten AI Gateway
        ├── Gmail API  (OAuth 2.0 + SMTP fallback)
        └── JIRA REST API v3  (OAuth 2.0 + PAT)

PostgreSQL (:5432)
  ├── LangGraph checkpoint tables  (full conversation state per thread)
  └── App schema: users, auth_sessions, app_sessions, oauth_connections
```

No queue, no worker processes, no Redis. LangGraph runs inside FastAPI as a library call. State survives server restarts.

---

## Quick Start

### Docker (recommended)

```bash
git clone <repo>
cd team-syncv2.0-fullstack

# Copy and fill in environment variables
cp backend/.env.example backend/.env

# Start all three services (postgres + backend + frontend)
docker compose up --build -d
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |

### Local Development

**Prerequisites:** Python 3.12, Node.js 20, PostgreSQL 15

**Backend:**

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # fill in values

# Run with hot reload
uvicorn src.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
cp .env.example .env.local  # optional overrides

npm run dev     # http://localhost:5173
npm run build   # TypeScript check + production bundle
npm run lint    # ESLint
```

The Vite dev server proxies `/api/*` to `http://localhost:8000` by default. Set `VITE_API_PROXY_TARGET` in `frontend/.env.local` to override.

---

## Configuration

### Backend Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in the required values.

#### Required

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL async connection string |
| `RAKUTEN_AI_GATEWAY_KEY` | Bearer token for Rakuten AI Gateway (Claude access) |
| `RAKUTEN_ANTHROPIC_BASE_URL` | Gateway endpoint (default: Rakuten public endpoint) |
| `RAKUTEN_ANTHROPIC_MODEL` | Model name (e.g. `claude-3-7-sonnet-20250219`) |

#### App & Auth

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `true` | Enable verbose backend logging |
| `LOG_LEVEL` | `debug` | Log level (`debug` / `info` / `warning`) |
| `FRONTEND_URL` | `http://localhost:5173` | Allowed CORS origin for OAuth redirects |
| `AUTH_COOKIE_NAME` | `teamsync_session` | Session cookie name |
| `AUTH_COOKIE_SECURE` | `false` | Set `true` in production (HTTPS only) |
| `AUTH_COOKIE_SAMESITE` | `lax` | SameSite policy |
| `AUTH_SESSION_DAYS` | `14` | Session lifetime in days |

#### Google Login OAuth (app sign-in)

Create a Google OAuth Web Client at [console.cloud.google.com](https://console.cloud.google.com).  
Callback URI: `http://localhost:8000/api/v1/auth/google/callback`  
Scopes: `openid email profile`

| Variable | Description |
|----------|-------------|
| `GOOGLE_LOGIN_CLIENT_ID` | OAuth client ID |
| `GOOGLE_LOGIN_CLIENT_SECRET` | OAuth client secret |

#### Gmail OAuth (PRD email sending)

Separate Google OAuth app with Gmail API enabled.  
Callback URI: `http://localhost:8000/api/v1/email/auth/callback`  
Scopes: `gmail.send userinfo.email`

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLIENT_ID` | OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret |

#### Gmail SMTP Fallback (if OAuth not configured)

| Variable | Description |
|----------|-------------|
| `GMAIL_SENDER` | Gmail address to send from |
| `GMAIL_APP_PASSWORD` | Google App Password (not your account password) |

#### JIRA OAuth (user-level, preferred)

Create an OAuth 2.0 app at [developer.atlassian.com/console/myapps](https://developer.atlassian.com/console/myapps).  
Callback URI: `http://localhost:8000/api/v1/jira/auth/callback`  
Scopes: `read:jira-work write:jira-work offline_access`

| Variable | Description |
|----------|-------------|
| `ATLASSIAN_CLIENT_ID` | Atlassian app client ID |
| `ATLASSIAN_CLIENT_SECRET` | Atlassian app client secret |

#### JIRA API Token Fallback (service account)

Used when no user has connected via OAuth, or for self-hosted JIRA.

| Variable | Default | Description |
|----------|---------|-------------|
| `JIRA_BASE_URL` | — | JIRA instance base URL (e.g. `https://your-org.atlassian.net`) |
| `JIRA_EMAIL` | — | Service account email |
| `JIRA_API_TOKEN` | — | JIRA API token |
| `JIRA_PROJECT_KEY` | `TSA` | Default project key for ticket creation |
| `JIRA_EPIC_TYPE` | `Epic` | Epic issue type name in your JIRA project |
| `JIRA_STORY_TYPE` | `Story` | Story issue type name |
| `JIRA_SUBTASK_TYPE` | `Subtask` | Subtask issue type name |

### Frontend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | _(empty)_ | Backend origin override. Leave empty to use the Vite dev proxy |
| `VITE_API_PROXY_TARGET` | `http://localhost:8000` | Proxy target for `/api/*` requests in development |
| `VITE_HTTP_LOG` | `true` | Set `false` to silence browser console HTTP logging |

---

## Features

### Conversational Requirements Gathering

Sam, the AI analyst, conducts a structured requirements dialogue. It asks targeted questions, accepts file uploads (PDF, images, text, JSON, XML up to 10 MB), and supports commands:

| Command | Action |
|---------|--------|
| `/prd` | Trigger PRD generation immediately |
| `/summary` | Show requirements summary so far |
| `/regenerate` | Regenerate the last response |
| `/help` | Show available commands |
| `/jira` | Jump to JIRA creation (if PRD exists) |
| `/testcases` | Generate test cases (if PRD exists) |

When Sam has gathered enough context, it emits a `GENERATE_PRD:` signal which triggers the outline stage automatically.

### PRD Generation and Scoring

The PRD outline is presented for approval before full generation. Users can approve it or provide feedback for revision.

DevBridge generates a complete PRD covering:
- Classification (type, priority, complexity, effort)
- Product Overview + Introduction
- Goals
- Functional Requirements (≥5 FRs)
- Non-Functional Requirements
- Scope (in/out)
- Success Metrics
- Design & UX Considerations
- Technical Considerations
- Timeline & Milestones
- JIRA Ticket Templates
- Test Cases (≥15 total: happy path + edge cases)

**Scoring (0–100):**

| Component | Max Points |
|-----------|-----------|
| Section coverage (8 sections) | 50 pts |
| Test case count (≥15 = 30 pts) | 30 pts |
| Document length (>5000 chars = 20 pts) | 20 pts |

**Grades:** A (≥90) · B (≥80) · C (≥70) · D (≥60) · F (<60)

### Gmail Integration

- Connect Gmail via OAuth 2.0 popup (no page navigation required)
- Send PRD as a `.md` file attachment inline from the chat
- Falls back to SMTP app password if OAuth is not configured
- Token auto-refreshed before each send

### JIRA Integration

**Two authentication modes:**

| Mode | Use Case |
|------|----------|
| OAuth 2.0 | JIRA Cloud — user logs in via Atlassian popup |
| PAT | Self-hosted / Data Center JIRA |

**Ticket hierarchy created from the PRD:**

```
Epic  [PRD] {Project Name}
├── Story: FR1: {requirement title}
│   ├── Subtask: TC001: {test case}
│   └── Subtask: TC002: {test case}
├── Story: FR2: {requirement title}
│   └── Subtask: TC003: {test case}
└── ...
```

- Auto-confirm with 5-second countdown if already connected
- Optional assignee email — resolves Atlassian account ID, assigns all tickets
- Notification email sent to assignee with all ticket links
- Real-time progress ("Creating story 2 of 5…") via SSE
- Retry logic: up to 3 attempts on network/timeout errors per ticket

**Projects page:**
- Browse all JIRA projects and boards
- Open any board directly in JIRA
- Create tickets from any PRD markdown outside the chat flow

### Multi-Tab Sessions

- Open unlimited concurrent chat sessions in separate tabs
- Each tab has its own LangGraph thread and session state
- Tabs persist across browser refreshes (localStorage + PostgreSQL)
- Tab labels auto-generated from first user message

### History and Dashboard

**History page:**
- Browse all generated PRDs with quality score and grade
- Search by title or filename
- Delete individual entries or clear all
- Resume any past session by clicking its history card

**Dashboard:**
- Total PRDs generated
- Average quality score
- JIRA tickets created count
- Recent activity timeline

---

## Project Structure

```
team-syncv2.0-fullstack/
├── backend/
│   ├── src/
│   │   ├── graph/
│   │   │   ├── state.py          PRDState TypedDict (all workflow fields)
│   │   │   ├── nodes.py          All node functions (Sam, DevBridge, HITL, JIRA, email)
│   │   │   ├── edges.py          Routing functions (route_entry, route_after_analyze)
│   │   │   └── graph.py          Compiled StateGraph + PostgreSQL checkpointer
│   │   ├── routers/
│   │   │   ├── auth.py           /api/v1/auth — signup, login, logout, Google OAuth
│   │   │   ├── chat.py           /api/v1/chat — SSE chat stream + file upload
│   │   │   ├── sessions.py       /api/v1/sessions/{id} — state, PRD, download, resume
│   │   │   ├── jira_auth.py      /api/v1/jira/auth — OAuth, PAT, projects, boards, create
│   │   │   ├── email_auth.py     /api/v1/email/auth — Gmail OAuth connect/status
│   │   │   └── ai.py             /api/v1/ai — direct AI query, provider list
│   │   ├── services/
│   │   │   ├── jira.py           JiraService — REST v3 client (OAuth + PAT + fallback)
│   │   │   ├── email.py          Gmail API + SMTP send, token refresh
│   │   │   └── oauth_connections.py  DB helpers for OAuth token storage
│   │   ├── middleware/
│   │   │   └── auth.py           require_current_user, require_session_owner
│   │   ├── config.py             Pydantic settings (reads .env)
│   │   ├── db.py                 SQLAlchemy async engine + session factory
│   │   ├── models.py             ORM models (User, AuthSession, AppSession, OAuthConnection)
│   │   ├── security.py           Password hashing, token generation
│   │   └── main.py               FastAPI app, router registration, lifespan
│   ├── tests/
│   │   ├── conftest.py
│   │   └── test_graph.py
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── chat/             ChatPage, ChatInterface, ChatTabBar, inline HITL forms
│       │   ├── prd/              PRDViewer (full-page markdown with TOC)
│       │   ├── jira/             JIRATicketViewer, ProjectsPage (browse + create)
│       │   ├── history/          History (search, delete, resume)
│       │   ├── dashboard/        Dashboard (stats + activity)
│       │   ├── email/            EmailForm (legacy settings page)
│       │   ├── auth/             AuthPage (login / signup)
│       │   ├── layout/           Layout, Sidebar, Header
│       │   └── ui/               Button, Card, Input (primitives)
│       ├── context/
│       │   ├── AppContext.tsx     Global state: tabs, PRD history, JIRA connection
│       │   └── AuthContext.tsx    Authenticated user
│       ├── services/
│       │   └── api.ts            All HTTP calls + SSE stream readers + localStorage helpers
│       ├── types/
│       │   └── index.ts          SSEEvent, InterruptPayload, ChatTab, PRDDocument, etc.
│       └── App.tsx               React Router routes
│
├── docker-compose.yml
├── PRD.md                        Product Requirements Document
├── PLAN.md                       Technical rewrite plan (v1 → v2)
├── SYSTEM_DESIGN.md              Architecture diagrams and data flow
└── AGENTS.md                     AI agent / coding assistant instructions
```

---

## API Reference

Base URL: `http://localhost:8000/api/v1`

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/signup` | Register with email + password |
| `POST` | `/auth/login` | Login with email + password |
| `POST` | `/auth/logout` | Invalidate all sessions |
| `GET` | `/auth/me` | Get current user info |
| `GET` | `/auth/google/login` | Start Google OAuth login |
| `GET` | `/auth/google/callback` | Google OAuth callback |

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/chat` | Send message → SSE stream of events |
| `POST` | `/chat/upload` | Upload files to attach to session context |

**Chat request body:**
```json
{ "message": "I want to build an expense tracker", "session_id": "optional-uuid" }
```

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/sessions/{id}` | Get session state snapshot |
| `GET` | `/sessions/{id}/prd` | Get generated PRD markdown |
| `GET` | `/sessions/{id}/download` | Download PRD as `.md` file |
| `POST` | `/sessions/{id}/resume` | Resume after HITL interrupt → SSE stream |

**Resume request body:**
```json
{
  "data": {
    "decision": "approve",
    "assignee_email": "team@company.com",
    "notes": "Urgent — Q2 feature",
    "project_key": "TSA"
  }
}
```

### JIRA

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/jira/auth/connect?session_id=` | Get Atlassian OAuth URL (session-scoped) |
| `GET` | `/jira/auth/callback` | OAuth callback from Atlassian |
| `GET` | `/jira/auth/status?session_id=` | Check JIRA connection for session |
| `DELETE` | `/jira/auth/disconnect?session_id=` | Clear session JIRA tokens |
| `GET` | `/jira/auth/me/status` | Check user-level JIRA connection |
| `GET` | `/jira/auth/me/connect` | Get Atlassian OAuth URL (user-scoped) |
| `POST` | `/jira/auth/me/pat` | Save PAT credentials |
| `DELETE` | `/jira/auth/me/disconnect` | Clear all user JIRA credentials |
| `GET` | `/jira/auth/projects?q=` | List/search JIRA projects |
| `GET` | `/jira/auth/boards?project_key=` | List JIRA Agile boards |
| `POST` | `/jira/auth/create` | Create tickets from PRD markdown directly |

### Gmail

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/email/auth/connect?session_id=` | Get Gmail OAuth URL |
| `GET` | `/email/auth/callback` | Gmail OAuth callback |
| `GET` | `/email/auth/status?session_id=` | Check Gmail connection |
| `DELETE` | `/email/auth/disconnect?session_id=` | Clear Gmail tokens |

---

## LangGraph Workflow

### Nodes

| Node | Role | Description |
|------|------|-------------|
| `analyze` | Sam | Requirements gathering. Streams tokens. Detects `GENERATE_PRD:` signal to transition. |
| `generate_prd_outline` | DevBridge | Generates a concise outline for user approval before full PRD. |
| `prd_outline_interrupt` | HITL | Suspends graph. Frontend shows approve/revise form. |
| `generate_prd` | DevBridge | Generates complete PRD markdown (up to 8192 tokens). |
| `validate` | Scoring | Scores PRD 0–100, assigns grade, derives filename. Emits `prd_complete`. |
| `post_prd_interrupt` | HITL | Presents action menu: email / test cases / jira / done. |
| `email_interrupt` | HITL | Checks Gmail status, collects recipient details. |
| `send_email` | Action | Sends PRD via Gmail API or SMTP. Emits `email_sent`. |
| `generate_test_cases` | DevBridge | Generates happy-path and edge-case test cases. |
| `validate_test_cases` | Scoring | Counts TCs, generates filename. Emits `test_cases_complete`. |
| `jira_interrupt` | HITL | Checks JIRA auth, fetches projects, collects approval. |
| `create_jira` | Action | Creates Epic → Stories → Subtasks. Emits `jira_progress` + `jira_created`. |

### HITL Interrupts

LangGraph's `interrupt()` suspends execution and saves full state to PostgreSQL. The frontend receives an `interrupt` SSE event with a `form` field describing which inline form to show. The user submits the form, the frontend POSTs to `/sessions/{id}/resume`, and execution continues from the suspended node.

| Form | Triggered By | Collected Data |
|------|-------------|----------------|
| `prd_outline_form` | After outline generated | `decision` (approve/revise), `feedback` |
| `post_prd_actions` | After PRD validated | `action` (email/test_cases/jira/done) |
| `email_form` | Email action chosen | `name`, `email` |
| `jira_form` | JIRA action chosen, not connected | `decision`, `assignee_email`, `notes`, `project_key` |
| `jira_auto_confirm` | JIRA action chosen, already connected | Same fields with 5-second auto-submit countdown |

### SSE Event Contract

Both `/chat` and `/sessions/{id}/resume` return `text/event-stream`. Each `data:` line is a JSON object:

```
{"type": "token",        "content": "# Classification..."}
{"type": "status",       "message": "Generating PRD outline…"}
{"type": "prd_complete", "score": 87, "grade": "B", "file_name": "expense_tracker_prd.md"}
{"type": "interrupt",    "form": "jira_form", "jira_connected": false, ...}
{"type": "jira_progress","message": "Creating story 2 of 5…", "current": 2, "total": 5}
{"type": "jira_created", "epic_key": "TSA-42", "epic_url": "...", "task_keys": [...]}
{"type": "email_sent",   "recipient": "pm@company.com"}
{"type": "turn_end",     "session_id": "uuid"}
{"type": "error",        "message": "..."}
```

**Browser console logging:** All API requests and SSE events are logged to the browser console using grouped `console.log` with color-coded method/status labels. Disable with `VITE_HTTP_LOG=false`.

---

## Database Schema

```
users
  id            int PK
  email         str unique
  password_hash str
  display_name  str
  created_at    datetime

auth_sessions
  id            int PK
  user_id       int FK → users (cascade)
  token_hash    str unique       -- SHA-256 of session token
  expires_at    datetime
  last_seen_at  datetime

app_sessions
  session_id    str PK           -- = LangGraph thread_id
  user_id       int FK → users (cascade)
  title         str
  created_at    datetime

oauth_connections
  id            int PK
  user_id       int FK → users (cascade)
  provider      str              -- "gmail" | "jira" | "jira_pat"
  access_token  text
  refresh_token text
  account_email str
  cloud_id      str
  cloud_name    str
  cloud_url     str
  UNIQUE (user_id, provider)
```

LangGraph stores its own checkpoint tables (`checkpoints`, `writes`) in the same database.

---

## Frontend Routes

| Path | Component | Description |
|------|-----------|-------------|
| `/login` | AuthPage | Email/password login + Google OAuth |
| `/signup` | AuthPage | Create new account |
| `/` | ChatPage | Main chat interface with tab bar |
| `/dashboard` | Dashboard | Usage stats and recent activity |
| `/history` | History | Browse, search, and restore past PRDs |
| `/prd` | PRDViewer | View current session's PRD |
| `/prd/:id` | PRDViewer | View PRD by session ID |
| `/jira` | JIRATicketViewer | JIRA connection settings (OAuth / PAT) |
| `/projects` | ProjectsPage | Browse JIRA projects and boards |
| `/projects/:key` | ProjectsPage | View boards for a specific project |
| `/email` | EmailForm | Gmail connection settings (legacy) |
| `/browse` | → `/projects` | Redirect |

All routes except `/login` and `/signup` require authentication (redirects to `/login`).

---

## Development Notes

**Backend debug logging:**  
Set `DEBUG=true` and `LOG_LEVEL=debug` in `backend/.env`. All `src.*`, `langgraph.*`, `langchain.*`, `httpx.*`, and `uvicorn.*` loggers are set to DEBUG level.

**Frontend browser logging:**  
HTTP logs are on by default in all environments. Each request logs a collapsible group with method, URL, request body, response status, timing, and response body. SSE events (excluding token stream) are logged individually. Disable: `VITE_HTTP_LOG=false`.

**LangGraph checkpointer:**  
In development without PostgreSQL, the graph uses an in-memory `MemorySaver` (state lost on restart). With `DATABASE_URL` pointing to PostgreSQL, `AsyncPostgresSaver` is used and state is durable.

**JIRA issue type names:**  
Different JIRA projects use different issue type names (e.g. "Task" vs "Story", "Sub-task" vs "Subtask"). Set `JIRA_EPIC_TYPE`, `JIRA_STORY_TYPE`, `JIRA_SUBTASK_TYPE` in `.env` to match your project configuration.

**Running tests:**

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/
```
