# ARCHITECTURE.md

System design, patterns, data flow, and key abstractions.

---

## Pattern

**Hybrid architecture**: n8n workflow automation as backend + React SPA as frontend.

- All business logic lives in n8n JSON workflow files (no custom server code)
- Frontend communicates exclusively via n8n webhook HTTP calls
- No traditional REST API or database — n8n is the runtime
- A planned Node.js/Express + PostgreSQL rewrite is documented in `BACKEND_PLAN.md` but not implemented

---

## System Layers

```
┌──────────────────────────────────────────────┐
│  React Frontend (frontend/src/)              │
│  - React Router: 6 routes                   │
│  - AppContext (useReducer): global state     │
│  - TeamSyncAPI singleton: all I/O            │
│  - localStorage: session persistence         │
└────────────────┬─────────────────────────────┘
                 │  HTTP POST (webhooks)
                 │  JSON: { chatInput, sessionId, mode }
                 ▼
┌──────────────────────────────────────────────┐
│  n8n Workflow Runtime (localhost:5678)       │
│  Generation 2: team_sync_dev_v2.1_with_JIRA  │
│  - Chat Trigger → Prepare Input              │
│  - Dual-mode agent (analyze / generate)      │
│  - Memory buffer (sessionId-keyed, len=20)   │
│  - Wait node: suspends for email form        │
└──────┬──────────────────┬────────────────────┘
       │                  │
       ▼                  ▼
 Ollama LLM          External Services
 (gpt-oss:20b)       (JIRA, Gmail)
```

---

## Dual-Mode Agent (Core Logic)

The active workflow uses a single agent that switches behavior based on a `mode` field:

**mode=analyze** → "Sam" (AI Product Analyst)
- Asks requirements questions conversationally
- When ready, emits `GENERATE_PRD: <context summary>` signal
- `Parse Agent Response` node detects this → sets `action=generate`

**mode=generate** → "DevBridge PRD Generator"
- Receives `contextSummary` from analyze phase
- Produces full markdown PRD in one pass
- `Parse Agent Response` detects PRD (length >2000, 4+ section headers) → sets `action=done`

**Routing** (`Action Router` Switch node):
- `action=continue` → NoOp, response returned to user
- `action=generate` → loops back into workflow with `mode=generate`
- `action=done` → PRD validation → email delivery → JIRA branch

---

## Frontend Data Flow

```
User input
  → ChatInterface component
  → api.sendMessage(text, sessionId)    [TeamSyncAPI]
  → POST /webhook/{CHAT_WEBHOOK_ID}
  → AgentResponse { output, action, sessionId, mode, ... }
  → dispatch ADD_MESSAGE                [AppContext]
  → localStorage save                   [api.saveMessages]
  → re-render ChatInterface

If action=done:
  → dispatch ADD_PRD_TO_HISTORY
  → navigate to /prd/:id
```

---

## State Management

`AppContext.tsx` — single global store, React Context + useReducer.

**State shape:**
```typescript
{
  sessionId: string | null
  currentMode: 'analyze' | 'generate'
  messages: Message[]
  isTyping: boolean
  currentPRD: PRDDocument | null
  prdHistory: PRDDocument[]
  emailStatus: 'idle' | 'sending' | 'sent' | 'error'
  jiraTickets: JIRATicket[]
  jiraApprovalStatus: 'pending' | 'approved' | 'rejected'
}
```

Side effects in reducer: `ADD_MESSAGE` calls `api.saveMessages()`, `ADD_PRD_TO_HISTORY` calls `api.savePRD()`, `SET_JIRA_TICKETS` calls `api.saveJIRATickets()`, `CLEAR_CHAT` calls `api.clearSession()`.

Hydrated from localStorage on mount via `useEffect` in `AppProvider`.

---

## Service Layer (`services/api.ts`)

`TeamSyncAPI` class, exported as singleton `api`. Responsible for:
1. All n8n webhook HTTP calls (`sendMessage`, `triggerEmail`, `triggerJIRA`)
2. All localStorage reads/writes (`getSessionId`, `saveMessages`, `savePRD`, etc.)
3. Session ID generation (UUID v4, persisted under `current_session_id`)

Components never touch `fetch` or `localStorage` directly.

---

## n8n Workflow Generations

| Generation | Files | LLM | Status |
|---|---|---|---|
| Gen 1 | `main.json`, `task_agent.json`, `prd_creator_agent.json` | Google Gemini | Legacy |
| Gen 2 | `team_sync_dev_v2.1_with_JIRA.json` | Ollama (gpt-oss:20b) | Active |

Gen 1 uses `executeWorkflow` to chain subworkflows. Gen 2 is self-contained.

---

## Entry Points

- **Frontend dev:** `frontend/src/main.tsx` → `App.tsx` (Router + AppProvider)
- **n8n workflows:** imported via n8n UI; Chat Trigger is the HTTP entry point
- **Standalone alternative:** `demo.html` (root) — uses `@n8n/chat` widget, no build step needed
