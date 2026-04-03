# TeamSync AI — Full-Stack Implementation Plan
> Production-grade rewrite: Next.js + FastAPI + n8n + PostgreSQL
> Status: Planning | Date: 2026-04-03

---

## Architecture Decision Summary

| Layer | Choice | Reason |
|---|---|---|
| Frontend | **Next.js 14** (App Router) | Production-grade React, SSR/SSG, built-in routing, easy Vercel/Docker deploy. Existing React components migrate with minimal changes. |
| Backend | **FastAPI** (Python 3.12) | Async, auto-generates OpenAPI docs, type-safe with Pydantic, replaces Node.js scaffold. Best Python option for production APIs. |
| Workflow engine | **n8n** (self-hosted Docker) | Kept as-is, fixed. Called by Python backend via webhook. Can call backend endpoints. |
| AI / LLM | **Ollama** (local) + **Rakuten AI Gateway** (future) | Ollama for local dev, Rakuten gateway plugged into n8n HTTP node or FastAPI client when docs are provided. |
| Database | **PostgreSQL 15** | Shared between n8n and FastAPI backend. |
| Reverse proxy | **Nginx** | Routes: `/api` → FastAPI, `/webhook` + `/n8n` → n8n, `/` → Next.js. |

### Full System Diagram
```
Internet / LAN
      │
  [Nginx :80/:443]
      ├─ /            → Next.js frontend   (:3000)
      ├─ /api/*       → FastAPI backend    (:8000)
      ├─ /webhook/*   → n8n webhooks       (:5678)
      └─ /n8n/*       → n8n UI (admin)     (:5678)

  [FastAPI :8000]
      ├─ POST /api/v1/chat          → proxy to n8n chat webhook
      ├─ GET  /api/v1/prd/{id}      → fetch PRD from DB
      ├─ GET  /api/v1/sessions      → session history
      ├─ POST /api/v1/jira/approve  → trigger n8n JIRA resume
      └─ POST /api/v1/ai/query      → Rakuten AI gateway (Phase 5)

  [n8n :5678]
      ├─ Chat Trigger webhook       → PRD workflow
      └─ Calls FastAPI              → store PRD, notify, etc.

  [PostgreSQL :5432]
      ├─ n8n database
      └─ backend database (sessions, prds, tickets)
```

---

## Phase Breakdown

### Phase 1 — Workflow Fixes (n8n) [IMMEDIATE]
> No new infra. Fix bugs in the existing workflow before anything else.

**Tasks:**
1. **Fix JIRA approval gate** — add IF node after `Approve JIRA Creation` Wait. Check `Decision === "APPROVE"` (case-insensitive). Route "no/skip/cancel" to a graceful exit NoOp.
2. **Fix JIRA loop connections** — `Loop Over Tasks` → `Create Parent Task` → back to `Loop Over Tasks` (done output → next phase). Same pattern for `Loop Over Subtasks`.
3. **Add workflow-level error handler** — create a new workflow called `TeamSync Error Handler`. In main workflow Settings → Error Workflow, point to it. Error handler should log + send Slack/email alert.
4. **Make Ollama model configurable** — replace hardcoded `gpt-oss:20b-cloud` with an expression that reads from an n8n credential or environment variable so teammates can point to their Ollama model.
5. **Update welcome message URL** — replace TinyURL with internal docs link.

**Deliverables:** Updated `team_sync_dev_v2.1_with_JIRA.json`, `team_sync_error_handler.json`

---

### Phase 2 — Python FastAPI Backend
> Replaces the empty Node.js scaffold in `backend/`. Keep `backend/` directory.

**Directory structure:**
```
backend/
├── src/
│   ├── main.py               # FastAPI app entry point
│   ├── config.py             # Settings (pydantic-settings, reads .env)
│   ├── database.py           # SQLAlchemy engine + session
│   ├── models/
│   │   ├── prd.py            # PRD ORM model
│   │   ├── session.py        # Chat session ORM model
│   │   └── ticket.py         # JIRA ticket ORM model
│   ├── schemas/
│   │   ├── prd.py            # Pydantic request/response schemas
│   │   ├── chat.py
│   │   └── ticket.py
│   ├── routers/
│   │   ├── chat.py           # POST /api/v1/chat
│   │   ├── prd.py            # CRUD /api/v1/prd
│   │   ├── sessions.py       # /api/v1/sessions
│   │   ├── jira.py           # /api/v1/jira
│   │   ├── ai.py             # /api/v1/ai (Rakuten gateway — Phase 5)
│   │   └── health.py         # GET /health, GET /api/v1/status
│   ├── services/
│   │   ├── n8n_client.py     # HTTP client to call n8n webhooks
│   │   ├── prd_service.py    # PRD business logic
│   │   └── ai_service.py     # AI gateway abstraction (Rakuten Phase 5)
│   ├── middleware/
│   │   ├── auth.py           # API key validation
│   │   └── rate_limit.py     # Per-key rate limiting (slowapi)
│   └── core/
│       ├── security.py       # API key hashing, token utils
│       └── exceptions.py     # Custom exception handlers
├── alembic/                  # DB migrations
│   └── versions/
├── tests/
│   ├── test_chat.py
│   ├── test_prd.py
│   └── conftest.py
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
└── alembic.ini
```

**Key dependencies:**
```
fastapi==0.115.x
uvicorn[standard]==0.32.x
sqlalchemy==2.0.x
alembic==1.13.x
pydantic-settings==2.x
asyncpg==0.29.x          # async postgres driver
httpx==0.27.x            # async HTTP for n8n calls
slowapi==0.1.x           # rate limiting
python-jose[cryptography] # JWT
passlib[bcrypt]           # password hashing
```

**API endpoints:**
```
GET  /health                          # liveness probe
GET  /api/v1/status                   # readiness + component health

POST /api/v1/chat                     # proxy message to n8n, return response
GET  /api/v1/sessions                 # list sessions for current user
GET  /api/v1/sessions/{id}            # session detail + chat history

POST /api/v1/prd                      # n8n calls this to store a completed PRD
GET  /api/v1/prd                      # list PRDs (paginated)
GET  /api/v1/prd/{id}                 # get PRD by ID
DELETE /api/v1/prd/{id}              # soft-delete

POST /api/v1/jira/approve             # trigger JIRA creation (resume n8n wait node)
GET  /api/v1/jira/tickets             # list created JIRA tickets

POST /api/v1/ai/query                 # Rakuten AI gateway (Phase 5, stub now)
```

**Auth model:** API key per user/team, passed as `X-API-Key` header. Keys stored hashed in DB.

---

### Phase 3 — Frontend (Next.js 14)
> Replaces/evolves the existing React/Vite app in `frontend/`. Existing components can be moved into `app/` with minimal changes since both use React.

**Directory structure:**
```
frontend/
├── app/
│   ├── layout.tsx              # Root layout (font, theme, nav)
│   ├── page.tsx                # Redirect to /chat
│   ├── chat/
│   │   └── page.tsx            # Chat interface
│   ├── dashboard/
│   │   └── page.tsx            # Session history + stats
│   ├── prd/
│   │   ├── page.tsx            # PRD list
│   │   └── [id]/page.tsx       # PRD viewer (markdown rendered)
│   └── api/                    # Next.js route handlers (BFF layer)
│       ├── chat/route.ts       # Calls FastAPI /api/v1/chat
│       └── prd/route.ts        # Calls FastAPI /api/v1/prd
├── components/
│   ├── chat/                   # Migrated from current frontend
│   ├── prd/
│   ├── dashboard/
│   └── ui/                     # Shared components
├── lib/
│   ├── api.ts                  # API client (calls /api/* BFF routes)
│   └── types.ts                # Shared TypeScript interfaces
├── Dockerfile
├── next.config.ts
└── package.json
```

**Framework rationale over React/Vite:**
- Handles routing natively (no react-router dependency)
- SSR for PRD viewer (good for sharing PRD links)
- Built-in API routes act as BFF — frontend never exposes backend URL to the browser
- Single `next build` → Docker image, or deploy to Vercel with zero config

---

### Phase 4 — Pipeline Directory
> Shell scripts, Docker compose files, CI/CD, Nginx config. See `pipeline/` directory.

**What it covers:**
- `Makefile` — single entry point for all dev/build/deploy commands
- `pipeline/scripts/` — setup, dev start, build, deploy, backup, workflow import/export
- `pipeline/docker/` — docker-compose for dev, prod, demo
- `pipeline/nginx/` — nginx config (dev + prod with SSL)
- `pipeline/ci-cd/` — GitHub Actions: CI, staging deploy, prod deploy
- `pipeline/docs/` — architecture, setup, API docs

---

### Phase 5 — Rakuten AI Gateway Integration
> **Blocked**: Requires user to provide API documentation.

**Expected integration points** (to be confirmed after docs review):
1. **In n8n**: Replace or augment Ollama with an HTTP Request node pointing to the Rakuten AI API endpoint. Credentials stored in n8n Credentials Manager.
2. **In Python backend**: `ai_service.py` (`/api/v1/ai/query`) acts as a unified AI client — routes requests to either Ollama (local) or Rakuten gateway based on config.
3. **Model routing logic**: Config flag `AI_PROVIDER=rakuten|ollama|openai` in `.env`. Backend picks provider at startup.

**Action needed:** Share Rakuten AI Gateway docs. I will then implement:
- n8n HTTP node configuration for the gateway
- `src/services/ai_service.py` Rakuten client class
- Auth (API key, OAuth, or certificate — TBD from docs)

---

## Execution Order

```
Week 1:
  [1] Phase 1 — Fix n8n workflow bugs
  [2] Phase 4 — Pipeline directory (shell scripts, Docker, CI/CD)

Week 2:
  [3] Phase 2 — FastAPI backend (core routes, DB models, n8n proxy)

Week 3:
  [4] Phase 3 — Next.js frontend (migrate existing components, wire to FastAPI)

When ready:
  [5] Phase 5 — Rakuten AI Gateway (after docs provided)
```

---

## Questions to Answer Before Phase 5

1. Rakuten AI Gateway auth method (API key / OAuth / cert)?
2. Endpoint base URL and available models?
3. Should the gateway replace Ollama or run alongside it?
4. Rate limits / quotas?

---

## Open Items

| Item | Owner | Status |
|---|---|---|
| Confirm Ollama server URL for team access | Sadat | Pending |
| Confirm shareable link approach (LAN vs internet) | Sadat | Pending |
| Provide Rakuten AI Gateway docs | Sadat | Pending |
| JIRA project ID for other team members | Sadat | Pending |
| Gmail shared account or per-user credentials | Sadat | Pending |
