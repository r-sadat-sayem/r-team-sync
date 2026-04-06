# Frontend Reference

## Status

`frontend/` is an in-progress React/Vite client for the TeamSync flow. It is not the source of truth for backend logic; it is a consumer of n8n webhooks plus local browser state.

## Stack

- React 19
- TypeScript
- Vite 8
- React Router 7
- Tailwind CSS 4
- `react-markdown` with `remark-gfm`

## Routes

- `/`: chat interface
- `/dashboard`: browser-local activity view
- `/prd`: current PRD view
- `/prd/:id`: PRD history detail
- `/email`: recipient form UI
- `/jira`: Jira approval and display UI

## Main Responsibilities

### Chat UI

- Sends `chatInput`, `sessionId`, and `mode` to the chat webhook
- Renders user and assistant messages
- Switches local mode based on `response.action`
- Builds a browser-local `PRDDocument` when the backend returns `action: "done"` and `fullOutput`

### PRD UI

- Renders markdown from `fullOutput`
- Builds a table of contents from markdown headings
- Supports copy and file download
- Links into email and Jira pages

### Email UI

- Collects recipient name and email
- Calls the email webhook
- Shows client-side validation errors
- Tracks send status in app state

### Jira UI

- Collects approval or rejection
- Calls the Jira approval webhook
- Displays Jira tickets from local browser state

Important:
- the workflow is real
- the ticket display in the React app is still partly simulated after approval

### Dashboard UI

- Summarizes PRD count, average quality, and recent activity
- Reads from local browser state rather than a backend database

## State Model

Global state is managed in `context/AppContext.tsx` with React Context and `useReducer`.

Tracked fields:
- `sessionId`
- `currentMode`
- `messages`
- `isTyping`
- `currentPRD`
- `prdHistory`
- `emailStatus`
- `jiraTickets`
- `jiraApprovalStatus`

## Local Storage Model

The frontend persists:

- `current_session_id`
- `chat_messages`
- `prd_history`
- `jira_tickets`

Behavior notes:
- history is capped to the most recent 50 PRDs
- clearing chat removes the session ID and messages, but not PRD history or stored Jira tickets

## Webhook Integration

The frontend talks directly to n8n:

- chat: `POST {VITE_N8N_BASE_URL}/webhook/{VITE_CHAT_WEBHOOK_ID}`
- email: `POST {VITE_N8N_BASE_URL}/webhook/{VITE_EMAIL_WEBHOOK_ID}`
- Jira approval: `POST {VITE_N8N_BASE_URL}/webhook/{VITE_JIRA_WEBHOOK_ID}`

Default local assumptions:
- base URL `http://localhost:5678`
- webhook IDs should be supplied through `frontend/.env`

## Differences From `demo.html`

### `demo.html`

- public-review landing page
- can be containerized and proxied
- focuses on the live chat entrypoint and review experience

### React frontend

- app-like experience for routes, history, and browser-local navigation
- more complete UI structure
- still not the primary demo distribution surface

## Current Gaps

- no configured frontend unit test runner
- no shared server persistence layer
- browser-local history can drift from real external system state
- Jira UI does not yet hydrate created tickets back from a backend source of record
