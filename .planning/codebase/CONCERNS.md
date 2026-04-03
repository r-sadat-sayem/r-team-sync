# CONCERNS.md

Technical debt, known issues, security concerns, and fragile areas.

---

## Critical Tech Debt

### JIRA Branch — Stub Implementation
**File:** `team_sync_dev_v2.1_with_JIRA.json` — nodes: `Extract JIRA content`, `Split Epic into Tasks`, `Convert into Sub tasks`

The three intermediate JIRA nodes only set `myNewField: 1`. No PRD parsing, no Epic/Task structure extraction. Only a single JIRA ticket is created per run. The workflow's sticky note documents remaining TODOs.

**Impact:** JIRA integration is non-functional beyond EPIC creation.

### No Test Suite
No unit or integration tests exist anywhere in the codebase. `TESTING.md` describes what _should_ be tested, not what is. All business logic in n8n Code nodes and frontend services is untested.

**Impact:** Any refactor of `api.ts`, `AppContext.tsx`, or n8n `Parse Agent Response` logic has no safety net.

### Design/Implementation Mismatch
`FRONTEND_DESIGN.md` specifies shadcn/ui components, but the actual implementation uses hand-rolled `ui/Button.tsx`, `ui/Card.tsx`, `ui/Input.tsx` with clsx + tailwind-merge. These are not API-compatible.

### Planned Backend Rewrite Not Started
`BACKEND_PLAN.md` documents a Node.js/Express + PostgreSQL rewrite replacing n8n as the backend. It has not been started. The current n8n approach has hard scaling and observability limits.

---

## Known Issues

### Session IDs
`api.ts` generates session IDs client-side. If the approach uses `Math.random()` or similar, entropy may be insufficient. Sessions are not authenticated — any client can use any session ID.

### Email Delivery Not Tracked
After `Email PRD Document` node fires, no delivery confirmation is surfaced to the frontend. `emailStatus` in state is set client-side without real confirmation from the workflow.

### Mock JIRA Tickets
The frontend `JIRATicketViewer` may display locally-stored ticket data that doesn't reflect actual Jira state — there's no sync back from the JIRA API to the frontend.

### Weak Email Validation
The `Ask for Recipient Email` Wait node form has no server-side email format validation before attempting delivery.

---

## Security Concerns

### Hardcoded Credential IDs in Workflow JSON
`team_sync_dev_v2.1_with_JIRA.json` contains credential IDs (`LIpsYPvVhobVTK8i`, `euztR3CaCKVVRcH9`, `Ro4RyNcsDpqjzjd0`) directly in the JSON. These IDs are meaningless without the n8n instance's credential store, but they leak the internal credential naming scheme.

### localStorage PII Risks
Chat messages (potentially containing sensitive product requirements) and email addresses are stored in `localStorage` under `chat_messages` and `prd_history`. These persist indefinitely and are accessible to any JS running on the same origin.

### Webhook Exposure
Chat webhook IDs in `frontend/.env` are embedded in client-side JS bundles. Any user can call the n8n webhooks directly, bypassing the frontend entirely.

### No Auth Layer
There is no authentication on any webhook or frontend route. The system is open to anyone with network access to n8n.

---

## Performance Concerns

### localStorage Unbounded Growth
`chat_messages` in localStorage has no size cap. `prd_history` is capped at 50 entries (enforced in `api.ts`), but message arrays can grow large for long sessions.

### Unvirtualized Chat Messages
`ChatInterface.tsx` renders all messages in the DOM. Long sessions will degrade scroll performance.

### n8n Execution Concurrency
n8n Community edition has execution concurrency limits. High parallel usage will queue or drop requests.

---

## Fragile Areas

### `Parse Agent Response` Node — Regex-Based Routing
**File:** `team_sync_dev_v2.1_with_JIRA.json` — `Parse Agent Response` Code node

The entire workflow routing depends on:
- Regex match for `GENERATE_PRD:` signal in agent output
- Output length >2000 chars AND 4+ section header matches for `action=done`
- Placeholder guard: `/MyApp|Example Project|Sample Feature|unnamed/i`

Any LLM output format change (different phrasing, shorter sections, inline headers) breaks routing silently — the workflow continues but produces wrong output.

### Hardcoded JIRA Assignee
Subtasks are always assigned to user ID `712020:819804e5-2d30-4b3d-9388-7f8dfb416842`. No configurability. Breaks if that user is deactivated or if used in a different Jira instance.

### Hardcoded JIRA Project ID
Project ID `10033` is hardcoded. The workflow cannot create tickets in any other project without a JSON edit.

### n8n Wait Node / Form URL
The `Ask for Recipient Email` node suspends execution and provides `$execution.resumeFormUrl`. If the n8n instance restarts during this wait, the execution is lost. The frontend has no mechanism to detect or recover from this.

### LLM Model Dependency
The primary model `gpt-oss:20b-cloud` is a non-standard Ollama model name. If this model is unavailable or renamed, the fallback to `mistral:latest` is silent — output quality degrades without notification.

---

## Scaling Limits

| Limit | Threshold | Impact |
|---|---|---|
| n8n Community concurrency | ~1-2 concurrent executions | Unusable for multi-user |
| localStorage quota | ~5-10 MB per origin | Long sessions may hit quota |
| LLM context window | 20 message buffer | Early conversation context lost |
| PRD history | 50 entries (soft cap) | Oldest PRDs silently dropped |

---

## Untested Paths

- Chat error handling (network failure, n8n timeout, malformed response)
- PRD validation logic (length checks, section pattern matching)
- Email validation and delivery failure handling
- JIRA creation failure handling
- `CLEAR_CHAT` action effects on all state slices
- All n8n workflow conditional branches (`action=generate`, `action=done`, `action=continue`)
- Placeholder guard false positives/negatives

---

## Dependencies at Risk

| Dependency | Risk |
|---|---|
| `gpt-oss:20b-cloud` (Ollama model) | Non-standard model — availability uncertain |
| n8n Community Edition | No SLA; workflow JSON format may change between versions |
| React 19 | Early adoption — some ecosystem libraries may not be compatible |
| Tailwind CSS 4 | Major version — documentation and tooling still maturing |
