# TeamSync AI — System Architecture

## Overview

TeamSync AI is a production-grade PRD automation system. A user describes a product idea in chat; the system gathers requirements conversationally, generates a scored PRD, emails it as a markdown artifact, creates JIRA tickets, and optionally routes through an AI gateway.

---

## Layer Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                        CLIENTS                               │
│  Browser (Next.js frontend)  │  Demo page  │  Direct webhook │
└──────────┬───────────────────┴──────┬───────┴────────────────┘
           │ HTTPS                    │ HTTPS
┌──────────▼──────────────────────────▼──────────────────────-─┐
│                   NGINX REVERSE PROXY                         │
│  /          → frontend:3000   (Next.js)                      │
│  /api/*     → backend:8000    (FastAPI)                      │
│  /webhook/* → n8n:5678        (Chat trigger & form resumes)  │
│  /n8n/*     → n8n:5678        (Admin UI — restrict in prod)  │
│  /demo/*    → demo:4040       (Landing page for sharing)     │
└──────────┬────────────────────┬─────────────────────────────-┘
           │                    │
┌──────────▼──────┐  ┌──────────▼──────────────────────────────┐
│  Next.js        │  │  FastAPI Backend (Python)                │
│  Frontend       │  │                                          │
│  (:3000)        │  │  POST /api/v1/chat → proxy to n8n        │
│                 │  │  GET  /api/v1/prd  → DB query            │
│  Calls /api/*   │  │  POST /api/v1/prd  → store PRD (n8n→)   │
│  BFF route      │  │  POST /api/v1/jira → resume n8n wait     │
│  handlers       │  │  POST /api/v1/ai   → AI gateway (Ph 5)  │
└─────────────────┘  └────────┬────────────────────────────────┘
                               │ httpx async calls
              ┌────────────────▼────────────────────────────────┐
              │          n8n Workflow Engine (:5678)             │
              │                                                  │
              │  [Chat Trigger] → [Sam analyst] → [PRD gen]     │
              │  → [Quality score] → [Email] → [JIRA creation]  │
              │                                                  │
              │  Calls back to FastAPI: POST /api/v1/prd        │
              └────────────────┬────────────────────────────────┘
                               │
              ┌────────────────▼────────────────────────────────┐
              │              AI Layer                            │
              │                                                  │
              │  Ollama (:11434) — local dev                     │
              │    Primary model: gpt-oss:20b-cloud              │
              │    Fallback:      mistral:latest                 │
              │                                                  │
              │  Rakuten AI Gateway — Phase 5                    │
              │    Plugged into FastAPI ai_service.py            │
              │    OR n8n HTTP node (configurable)               │
              └────────────────────────────────────────────────-┘
                               │
              ┌────────────────▼────────────────────────────────┐
              │         PostgreSQL (:5432)                       │
              │                                                  │
              │  n8n schema:  execution data, credentials        │
              │  app schema:  sessions, prds, tickets, api_keys  │
              └─────────────────────────────────────────────────┘
```

---

## Data Flow — PRD Generation

```
1. User types in chat (Next.js)
2. Next.js /api/chat BFF → FastAPI POST /api/v1/chat
3. FastAPI → POST http://n8n:5678/webhook/unified-webhook-id/chat
4. n8n Chat Trigger → Prepare Input → Build System Prompt
5. n8n Technical Analyst Agent (Ollama LLM) asks questions
6. [Multiple turns 2-5 repeat until requirements are gathered]
7. Agent emits GENERATE_PRD: signal
8. n8n Parse Agent Response detects signal → action=generate
9. n8n Trigger PRD Generation → loops workflow with mode=generate
10. n8n DevBridge Agent generates full PRD markdown
11. n8n Parse Response detects complete PRD → action=done
12. n8n Validate PRD Quality (scores 0-100)
13. n8n Convert to Binary (base64 markdown) + embeds resume URL
14. n8n calls FastAPI POST /api/v1/prd (stores PRD in DB)  ← NEW
15. User submits email form (Wait node resume)
16. n8n Email PRD Document (Gmail)
17. [Parallel] n8n Extract JIRA content
18. User approves JIRA form → IF Decision=APPROVE
19. n8n Create EPIC → Loop Tasks → Create Task → Loop Subtasks → Create Subtask
```

---

## Component Responsibilities

| Component | Owns | Does NOT own |
|-----------|------|-------------|
| **Next.js** | UI rendering, routing, BFF API routes | Business logic, LLM calls |
| **FastAPI** | API auth, session/PRD storage, AI gateway abstraction | Workflow execution |
| **n8n** | Workflow orchestration, LLM conversation, email, JIRA | User auth, long-term storage |
| **PostgreSQL** | Persistent state | Business logic |
| **Nginx** | TLS, routing, WebSocket upgrade | Application logic |
| **Ollama** | LLM inference | Orchestration |

---

## Rakuten AI Gateway Integration (Phase 5)

When Rakuten AI docs are provided, integration will happen at two points:

**Option A — n8n HTTP node** (simplest):
```
[Build System Prompt] → [Rakuten AI HTTP Request node] → [Parse Response]
```
Config: Credentials stored in n8n Credentials Manager as HTTP Header Auth.

**Option B — FastAPI ai_service.py** (more flexible, recommended):
```python
# src/services/ai_service.py
class AIService:
    async def query(self, prompt: str) -> str:
        if settings.AI_PROVIDER == "rakuten":
            return await self._rakuten_query(prompt)
        elif settings.AI_PROVIDER == "ollama":
            return await self._ollama_query(prompt)
```
FastAPI then exposes `POST /api/v1/ai/query`. n8n calls this endpoint instead of Ollama directly.

---

## Security Boundaries

- n8n admin UI never exposed publicly (nginx restricts `/n8n/` by IP in prod)
- FastAPI requires `X-API-Key` header on all `/api/v1/*` routes
- PostgreSQL not exposed outside Docker network
- Secrets in `.env` (never committed), rotated on team member departure
- JIRA and Gmail credentials stored in n8n Credentials Manager (encrypted at rest with `N8N_ENCRYPTION_KEY`)
