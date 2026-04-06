# TeamSync Testing Guide

Canonical reference:
- [Testing Reference](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/testing-reference.md)
- [Current Flow Reference](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/current-flow-reference.md)

## Scope

This repository has two test surfaces:

1. The React app in `frontend/`, which stores chat state, PRD history, and mock Jira tickets in `localStorage`.
2. The live automation flow in `team_sync_dev_v2.1_with_JIRA.json`, which runs in n8n and performs the real chat, PRD generation, email, and Jira steps.

Use both. The frontend alone does not prove Gmail or Jira integration, and the n8n workflow alone does not prove route navigation or UI handling.

## Test Environment

### Required services

- Node.js 18+
- `frontend` dependencies installed with `npm install`
- n8n running on `http://localhost:5678`
- Ollama running with `gpt-oss:20b-cloud`
- Valid Gmail OAuth2 credential in n8n
- Valid Jira Software Cloud credential in n8n

### Frontend config

Create `frontend/.env`:

```env
VITE_N8N_BASE_URL=http://localhost:5678
VITE_CHAT_WEBHOOK_ID=unified-webhook-id
VITE_EMAIL_WEBHOOK_ID=d9d4af96-c7a3-4dcf-8d59-708ffd5f1a7f
VITE_JIRA_WEBHOOK_ID=jira-approval-form-webhook
```

### Demo config

Prefer the Docker demo deployment documented in [demo deployment](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/demo-deployment.md), where the page uses:

```text
/webhook/unified-webhook-id/chat
```

and the container proxies that path to local n8n.

## Core Commands

- `cd frontend && npm run dev`: run the React UI.
- `cd frontend && npm run build`: verify the production build.
- `cd frontend && npm run lint`: catch TypeScript and React lint issues.
- `cd backend && npm run test`: reserved for backend Jest tests when backend code is present on this branch.

## Reset Before Each Test Cycle

### Frontend reset

Clear these browser storage keys:

- `current_session_id`
- `chat_messages`
- `prd_history`
- `jira_tickets`

Also clear n8n execution history for easier debugging.

### Workflow reset

- Re-import or reactivate `team_sync_dev_v2.1_with_JIRA.json` if webhook IDs changed.
- Confirm the workflow is active.
- Confirm the two Wait nodes still expose:
  - email form: `d9d4af96-c7a3-4dcf-8d59-708ffd5f1a7f`
  - Jira approval form: `jira-approval-form-webhook`

## Recommended Test Data

Use the demo scenario from [`DEMO_GUIDE.md`](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/DEMO_GUIDE.md):

> I want to build a mobile expense tracking app for small business owners. They need to photograph receipts, auto-categorize expenses, and export reports to CSV. Target: iOS and Android, launch in Q3 2025.

Expected clarifications:

- success metric: reduce manual entry time by 70%
- users: freelancers and teams up to 10
- key concern: offline mode

## End-to-End Test Cases

### 1. Chat intake

- Open `/` in the React app or load `demo.html`.
- Send the starter message.
- Verify the assistant asks focused follow-up questions, not a full PRD immediately.
- Verify refresh persistence: messages should reload from `localStorage`.
- Verify `Enter` sends and `Shift+Enter` does not.

Pass criteria:

- A session ID is created.
- User and assistant messages render in order.
- No HTTP or timeout error is shown.

### 2. PRD generation

- When Sam responds with a `GENERATE_PRD:` summary, confirm generation.
- Verify the workflow switches from analyze mode to generate mode.
- Verify the final response includes `fullOutput`, `qualityScore`, and `grade`.
- Open `/prd` and confirm:
  - PRD title is derived from `**Project Name**`
  - markdown renders correctly
  - sections appear in the table of contents
  - test case count is greater than zero

Pass criteria:

- Quality score appears in chat and PRD view.
- PRD is saved into `prd_history`.
- Download produces a `.md` file.

### 3. Email delivery

- From `/prd`, click `Email`.
- Submit a valid name and email.
- In n8n, confirm the execution paused at `Ask for Recipient Email`, resumed, then reached `Email PRD Document`.
- Verify the inbox receives the markdown attachment.

Negative checks:

- Blank name should fail client-side.
- Invalid email should fail client-side and should also fail server-side in the `Process Email Input` code node.

Pass criteria:

- Success UI appears in the React app.
- Gmail sends one message with a markdown attachment.

### 4. Jira approval and ticket creation

- From `/prd` or `/email`, open `/jira`.
- Submit `APPROVE`.
- In the React app, verify the approval form disappears and ticket cards appear.
- In n8n, confirm `Approve JIRA Creation` resumes and the workflow reaches `Create an EPIC`, `Create an Parent Task`, and `Create an Sub Task`.
- In Jira, confirm one Epic, one Task, and one Subtask were created.

Pass criteria:

- Epic summary uses the PRD project name.
- Task maps to `FR1`.
- Subtask maps to `TC001`.
- Subtask assignee is `Basic Coding Agent` if that mapping is still configured.

Note: the React screen currently shows mock tickets after approval. Jira must still be checked directly to validate the real integration.

### 5. Dashboard and history

- Open `/dashboard`.
- Verify total PRDs, average quality, and recent activity update after a successful generation.
- Open a saved PRD from history and confirm `/prd/:id` loads it correctly.

## `demo.html` Checks

- Verify the iframe loads when `N8N_CHAT_URL` is valid.
- Verify the fallback link appears if the iframe cannot load.
- Verify the page copy matches the actual workflow: chat, PRD generation, email, then Jira approval.

## Failure Tests

- Stop n8n and verify the frontend shows an error on send.
- Expire Gmail credentials and verify the workflow fails after the email form resumes.
- Reject or submit anything other than `APPROVE` in the Jira approval form and verify no tickets are created.
- Generate a very weak prompt and verify the PRD quality score drops below the normal demo range.

## Debugging Checklist

- Chat issues: confirm `unified-webhook-id` is active and `VITE_N8N_BASE_URL` points to the running n8n instance.
- Missing PRD: inspect `Validate PRD Quality` and confirm the response includes `action: "done"` and `fullOutput`.
- Email failures: inspect `Convert to Binary`, `Merge PRD & Form`, and `Process Email Input`.
- Jira failures: inspect `Extract JIRA content`, the approval Wait node, and all Jira credential mappings.
- UI persistence bugs: inspect `localStorage` contents and clear stale keys before retesting.

## Current Gaps

- No frontend unit or component test runner is configured.
- Backend source and Jest coverage are not fully present on this branch.
- The Jira view in React is partly simulated; production validation still depends on checking n8n and Jira directly.
