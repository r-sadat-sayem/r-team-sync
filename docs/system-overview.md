# System Overview

## Repository Role

This repository currently combines four different system layers:

1. **Active automation backend**: `team_sync_dev_v2.1_with_JIRA.json`
2. **Standalone demo surface**: `demo.html`
3. **Containerized review endpoint**: `Dockerfile.demo`, `docker-compose.demo.yml`, `docker/`
4. **In-progress React product UI**: `frontend/`

There is also a **planned** Node/Express/Postgres rewrite documented in `BACKEND_PLAN.md`.

## Component Status

| Component | Status | Purpose |
|---|---|---|
| `team_sync_dev_v2.1_with_JIRA.json` | Active | End-to-end PRD automation workflow: chat, PRD generation, scoring, email, Jira approval, Jira creation |
| `demo.html` | Active, demo-facing | Review landing page that embeds or links to the live chat endpoint |
| Docker demo container | Active | Serves the demo page and proxies `/webhook/*` to local n8n for same-origin public review |
| `frontend/` | In progress | React UI that mirrors the flow and stores state locally for demo convenience |
| `backend/` | Partial/planned | Package metadata and structure exist, but the implementation is not complete in this branch |
| `BACKEND_PLAN.md` | Planned | Future-state rewrite design, not the live runtime |

## High-Level Architecture

### Active path

User -> demo page or React app -> n8n webhook -> Ollama-backed agent -> PRD generation/validation -> email wait/resume -> Jira approval wait/resume -> Jira ticket creation

### Supporting path

Public reviewer -> Docker demo container on port `4040` -> same-origin `/webhook/*` proxy -> local n8n on `host.docker.internal:5678`

## Responsibility by Subsystem

### n8n workflow

- Owns the live business logic
- Maintains conversation state through session IDs
- Switches between analyze and generate modes
- Scores PRD quality
- Generates email delivery artifacts
- Gates Jira creation behind human approval
- Creates the Epic -> Task -> Subtask hierarchy

### Standalone demo page

- Presents the system for external review
- Shows starter prompts and links to supporting docs
- Embeds the chat endpoint when possible
- Falls back to direct-link launch when iframe embedding fails
- Reads runtime config from `config.js`

### Docker demo container

- Serves `demo.html` and related docs
- Generates `config.js` at startup from environment variables
- Proxies `/webhook/*` to local n8n
- Makes the demo page and chat endpoint available from one public origin

### React frontend

- Provides a structured UI for chat, PRD viewing, email entry, Jira approval, and dashboard history
- Talks directly to n8n webhooks for chat, email, and Jira approval
- Stores chat history, PRD history, session IDs, and mock Jira tickets in `localStorage`
- Does not replace the n8n backend; it is a client for it

## What Is Real vs Simulated

### Real in the active workflow

- Conversational intake
- PRD generation
- PRD quality scoring
- Email wait/resume flow
- Jira approval wait/resume flow
- Jira ticket creation

### Simulated or local-only in the React app

- PRD history persistence in `localStorage`
- Jira ticket display after approval
- Some dashboard activity metrics derived from local browser state

## Configuration Surfaces

### n8n-side

- Active imported workflow
- Ollama model availability
- Gmail credentials
- Jira credentials
- Reachable webhook endpoints

### Demo container

- `N8N_CHAT_URL`
- `N8N_UPSTREAM_BASE`
- `DEMO_TITLE`
- `DEMO_BADGE`

### React frontend

- `VITE_N8N_BASE_URL`
- `VITE_CHAT_WEBHOOK_ID`
- `VITE_EMAIL_WEBHOOK_ID`
- `VITE_JIRA_WEBHOOK_ID`

## Where To Go Next

- For exact runtime behavior: [Current Flow Reference](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/current-flow-reference.md)
- For node-level workflow detail: [n8n Workflow Reference](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/n8n-workflow-reference.md)
- For UI-side behavior: [Frontend Reference](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/frontend-reference.md)
- For future-state vs current limitations: [Roadmap and Known Gaps](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/roadmap-and-known-gaps.md)
