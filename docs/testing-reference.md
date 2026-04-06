# Testing Reference

## Scope

Testing this repository requires validating both:

1. the active n8n workflow
2. the UI surfaces that call it

Neither the React app nor the standalone demo page alone is enough to validate the whole system.

## Test Surfaces

### Live system under test

- `team_sync_dev_v2.1_with_JIRA.json`
- Ollama model serving
- Gmail integration
- Jira integration

### UI surfaces

- `demo.html` served directly or via Docker
- `frontend/` app for route-level UI validation

## Required Environment

- Node.js 18+
- installed frontend dependencies
- running n8n on the configured upstream host
- available Ollama model
- valid Gmail auth in n8n
- valid Jira auth in n8n

## Core Validation Areas

### Chat intake

Verify:
- session continuity works
- the assistant asks focused follow-up questions
- the flow does not jump directly to a PRD without enough detail

### PRD generation

Verify:
- the workflow switches from analyze to generate mode
- the final response contains `fullOutput`
- the PRD includes the required major sections
- the quality score and grade are returned

### Email delivery

Verify:
- wait-form URL is issued
- recipient submission resumes the workflow
- markdown attachment is sent

### Jira approval and creation

Verify:
- approval gate exists
- the workflow does not create tickets before approval
- one Epic, one Task, and one Subtask are created after approval

### UI behavior

Verify:
- React app stores and reloads browser-local history correctly
- `demo.html` shows the right public-review content
- iframe fallback works as intended

## Recommended Test Data

Use [E2E_TEST_DATA.md](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/E2E_TEST_DATA.md) for:
- happy path
- smoke path
- weak-input path
- email validation failure
- Jira rejection path

## Reset Guidance

### Browser reset

Clear:
- `current_session_id`
- `chat_messages`
- `prd_history`
- `jira_tickets`

### n8n reset

- clear execution history when debugging
- verify active webhook IDs
- reactivate the workflow if the imported definition changed

## Pass Criteria

A strong end-to-end pass looks like:

- stable chat
- structured PRD with visible quality score
- successful email send with markdown attachment
- Jira approval gate respected
- final Epic -> Task -> Subtask visible in Jira

## Known Test Gaps

- no formal frontend unit test suite
- backend package is not implemented enough in this branch for meaningful service-level coverage
- React Jira display is not a full source of truth for created tickets

## Related Docs

- [Legacy Testing Guide](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/TESTING_GUIDE.md)
- [Current Flow Reference](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/current-flow-reference.md)
- [Demo Deployment](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/demo-deployment.md)
