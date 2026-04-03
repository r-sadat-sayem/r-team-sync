# INTEGRATIONS.md

External services, APIs, and webhooks used in this codebase.

---

## n8n Workflow Platform

**Role:** Core backend runtime — all business logic executes inside n8n workflows.

- Self-hosted at `http://localhost:5678` (dev default)
- Workflows triggered via Chat Trigger webhooks (HTTP POST)
- Wait nodes suspend execution pending form submissions (`$execution.resumeFormUrl`)
- Credential store holds all service credentials (referenced by ID in JSON)

**Webhook endpoints consumed by frontend** (configured via `frontend/.env`):
| Variable | Purpose |
|---|---|
| `VITE_CHAT_WEBHOOK_ID` | Chat Trigger — main conversational entry point |
| `VITE_EMAIL_WEBHOOK_ID` | `d9d4af96-c7a3-4dcf-8d59-708ffd5f1a7f` — email delivery trigger |
| `VITE_JIRA_WEBHOOK_ID` | JIRA approval form webhook |

Base URL: `VITE_N8N_BASE_URL` (default `http://localhost:5678`)

---

## Ollama (LLM — Generation 2)

**Role:** Local LLM inference for the active workflow (`team_sync_dev_v2.1_with_JIRA.json`).

- Node type: `lmChatOllama`
- Credential ID: `Ro4RyNcsDpqjzjd0`
- **Primary model:** `gpt-oss:20b-cloud`
- **Fallback model:** `mistral:latest`
- Memory buffer: `contextWindowLength: 20`, keyed by `sessionId`

---

## Google Gemini (LLM — Generation 1)

**Role:** LLM for legacy multi-workflow system (`main.json`, `task_agent.json`, `prd_creator_agent.json`).

- Node type: `lmChatGoogleGemini`
- Credential ID: `Your_Gemini_Credentials_ID` (placeholder — must be set per instance)

---

## JIRA Cloud (Atlassian)

**Role:** Ticket creation from generated PRDs.

- Credential ID: `LIpsYPvVhobVTK8i`
- Hardcoded project ID: `10033` ("Team Sync Automation")
- Subtasks auto-assigned to user ID: `712020:819804e5-2d30-4b3d-9388-7f8dfb416842` ("Basic Coding Agent")
- Integration status: **partially implemented** — EPIC creation works; subtask splitting nodes are stubs

---

## Gmail / SMTP

**Role:** Delivering generated PRD documents to recipients via email.

- Credential ID: `euztR3CaCKVVRcH9`
- Triggered after PRD quality validation passes (`action=done`)
- Email content: base64-encoded markdown PRD attached/inline
- Recipient collected via n8n Wait node form (`Ask for Recipient Email`)

---

## localStorage (Browser Persistence)

**Role:** Client-side state persistence between page loads.

| Key | Contents |
|---|---|
| `current_session_id` | Active n8n session ID |
| `chat_messages` | Full message history array |
| `prd_history` | Up to 50 generated PRD documents |
| `jira_tickets` | JIRA ticket objects |

Managed exclusively through `src/services/api.ts` (`TeamSyncAPI` singleton).

---

## Planned Integrations (Not Yet Implemented)

Per `BACKEND_PLAN.md`:
- **PostgreSQL** — persistent storage for the planned Node.js/Express backend rewrite
- **OpenAI / Claude API** — alternative LLM providers considered in backend plan
- **shadcn/ui** — component library referenced in `FRONTEND_DESIGN.md` but not yet installed
