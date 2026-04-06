# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## What This Repository Is

**TeamSync AI v2.0** — a fullstack AI system that conducts conversational requirements
gathering (via LangGraph + Rakuten AI Gateway / Claude) and generates scored PRDs,
emails them, and creates JIRA tickets under the submitting user's Atlassian identity.

## Active Project

Everything lives in `team-syncv2.0-fullstack/`:

```
team-syncv2.0-fullstack/
├── backend/          Python FastAPI + LangGraph workflow engine
├── frontend/         React 19 / Vite 8 / Tailwind CSS v3
├── docker-compose.yml
├── PLAN.md           Phase plan (Phase 1-3 done, Phase 2 HITL complete)
└── SYSTEM_DESIGN.md  Architecture diagrams and data flow
```

## Commands

### Frontend — `team-syncv2.0-fullstack/frontend/`

```bash
cd team-syncv2.0-fullstack/frontend
npm install
npm run dev      # http://localhost:5173
npm run build    # TypeScript check + Vite bundle
npm run lint
```

### Backend — `team-syncv2.0-fullstack/backend/`

```bash
cd team-syncv2.0-fullstack/backend
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000   # http://localhost:8000
# Docs: http://localhost:8000/docs
```

### Full stack (Docker)

```bash
cd team-syncv2.0-fullstack
cp backend/.env.example backend/.env   # fill in RAKUTEN_AI_GATEWAY_KEY etc.
docker compose up --build -d
```

Services: frontend :5173 · backend :8000 · postgres :5432

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite 8, Tailwind CSS v3, React Router 7 |
| Backend | Python 3.12, FastAPI, LangGraph, LangChain Anthropic |
| AI | Rakuten AI Gateway → Claude (langchain-anthropic) |
| Database | PostgreSQL 15 (LangGraph checkpointer + app schema) |
| Auth | X-API-Key (backend) · Atlassian OAuth 2.0 (JIRA) |

## Key Backend Files

| File | Purpose |
|---|---|
| `backend/src/graph/nodes.py` | LangGraph nodes — Sam (analyze) + DevBridge (generate_prd) + HITL gates |
| `backend/src/graph/state.py` | `PRDState` TypedDict — all workflow state |
| `backend/src/graph/edges.py` | Routing functions |
| `backend/src/graph/graph.py` | Compiled graph + PostgreSQL checkpointer |
| `backend/src/routers/chat.py` | `POST /api/v1/chat` — SSE stream |
| `backend/src/routers/sessions.py` | `POST /sessions/{id}/resume` — HITL SSE resume |
| `backend/src/routers/jira_auth.py` | Atlassian OAuth 2.0 flow |
| `backend/src/services/email.py` | Gmail SMTP (asyncio.to_thread) |
| `backend/src/services/jira.py` | JIRA REST v3 — Epic → Stories → Subtasks |

## Key Frontend Files

| File | Purpose |
|---|---|
| `frontend/src/services/api.ts` | SSE stream generators (`streamChat`, `resumeSession`) |
| `frontend/src/components/chat/ChatInterface.tsx` | Main chat — SSE consumer, inline forms |
| `frontend/src/components/chat/InlineEmailForm.tsx` | Email HITL form (appears in chat flow) |
| `frontend/src/components/chat/InlineJiraForm.tsx` | JIRA HITL form + OAuth connect button |
| `frontend/src/context/AppContext.tsx` | Global state (interrupt, jiraResult, messages) |
| `frontend/src/types/index.ts` | SSEEvent union, InterruptPayload, JiraResult |

## Environment Variables

Copy `backend/.env.example` to `backend/.env`. Critical vars:

```
RAKUTEN_AI_GATEWAY_KEY=raik-...
RAKUTEN_ANTHROPIC_BASE_URL=https://api.ai.public.rakuten-it.com/anthropic/
RAKUTEN_ANTHROPIC_MODEL=claude-haiku-4-5-20251001   # or claude-3-7-sonnet-20250219
DATABASE_URL=postgresql+asyncpg://teamsync:teamsync@postgres:5432/teamsync
BACKEND_API_KEY=dev-change-me
ATLASSIAN_CLIENT_ID=...      # for JIRA OAuth
ATLASSIAN_CLIENT_SECRET=...
GMAIL_SENDER=...
GMAIL_APP_PASSWORD=...
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_PROJECT_KEY=TSA
```

## Trash

`trash/` contains n8n v1 artifacts moved during the 2026-04-06 restructure.
Safe to ignore. Not deleted in case reference is needed.
