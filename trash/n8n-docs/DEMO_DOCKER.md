# Demo Docker Runbook

Canonical reference:
- [Demo Deployment](/Users/sadat.sayem/TeamSyncV2/n8nProjects/v1.1/docs/demo-deployment.md)

## Purpose

This container serves the standalone `demo.html` landing page and its review documents on port `4040`.

## Quick start

```bash
docker compose -f docker-compose.demo.yml up --build
```

Then open:

```text
http://localhost:4040
```

## Required environment variable

By default, the demo page uses a same-origin chat path and proxies it to your local n8n instance:

```bash
N8N_CHAT_URL=/webhook/unified-webhook-id/chat
N8N_UPSTREAM_BASE=http://host.docker.internal:5678
```

You can override the compose defaults:

```bash
N8N_CHAT_URL=/webhook/unified-webhook-id/chat \
N8N_UPSTREAM_BASE=http://host.docker.internal:5678 \
DEMO_TITLE="TeamSync AI" \
DEMO_BADGE="Stakeholder Review" \
docker compose -f docker-compose.demo.yml up --build
```

## Included routes

- `/`: review-ready demo landing page
- `/DEMO_GUIDE.md`: presenter guide
- `/TESTING_GUIDE.md`: test guide
- `/E2E_TEST_DATA.md`: copy/paste demo datasets
- `/healthz`: container health check endpoint

## Notes

- Runtime configuration is injected through `config.js`; you do not need to edit `demo.html` to change the chat URL.
- The demo container proxies `/webhook/*` to n8n, so a public host can serve both the landing page and the chat endpoint from the same origin.
- If iframe embedding is blocked by the upstream chat page, the demo automatically falls back to a direct-link launch path.
