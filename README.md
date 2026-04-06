# TeamSync PRD Automation System

TeamSync is an AI-assisted PRD automation project built around an active n8n workflow, a standalone public demo page, and an in-progress React frontend.

## Current State

- **Active backend logic:** `team_sync_dev_v2.1_with_JIRA.json`
- **Standalone public/demo UI:** `demo.html`, served directly or through the Docker demo container
- **In-progress product UI:** `frontend/`
- **Planned rewrite:** `BACKEND_PLAN.md`

The repository is currently documentation-heavy because the live behavior is split across n8n automation and UI prototypes.

## Start Here

- [Documentation Hub](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/README.md)
- [System Overview](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/system-overview.md)
- [Current Flow Reference](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/current-flow-reference.md)
- [Demo Deployment](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/demo-deployment.md)
- [Testing Reference](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/testing-reference.md)

## Quick Commands

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Demo container:

```bash
docker compose -f docker-compose.demo.yml up --build
```

## Notes

- Use sanitized placeholders for secrets, tokens, account IDs, and environment-specific identifiers in documentation and screenshots.
- The docs under `docs/` are the current source of truth. Older focused docs remain available for presentation, testing, and runbook use.
