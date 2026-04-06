# Roadmap and Known Gaps

## Current-State Gaps

### Workflow scope limits

- Jira creation currently covers only the first Epic/title path, the first functional requirement, and the first test case
- low PRD quality does not automatically trigger a retry loop
- execution success still depends on external Gmail and Jira auth being healthy

### Frontend limits

- React state is browser-local rather than backed by a database or service
- dashboard metrics are derived from browser-local artifacts
- Jira display after approval is not a fully server-sourced reflection of created tickets

### Repository limits

- backend package metadata exists, but the implementation is not complete in this branch
- there is no unified root-level application runtime that replaces n8n today
- documentation historically accumulated in separate files and required consolidation

## Planned Direction

The intended future direction is documented in `BACKEND_PLAN.md`:

- Express API layer
- PostgreSQL persistence
- AI service abstraction
- email and Jira services
- dedicated session, PRD, email, and Jira data models

This is a design target, not the current runtime.

## Recommended Next Documentation/Engineering Steps

- keep `docs/` as the source of truth
- update focused docs when behavior changes in n8n or the demo container
- decide whether the React app or a future backend rewrite becomes the primary product surface
- move any environment-sensitive operational notes to a private operator appendix if needed later

## Decision Boundary

Use this rule when reading the repo:

- if it lives in the n8n workflow or the demo deployment, it likely affects the live system now
- if it lives in `frontend/`, it likely affects the client experience but not the backend source of truth
- if it lives in `BACKEND_PLAN.md`, it is future-state design only
