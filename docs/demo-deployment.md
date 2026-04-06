# Demo Deployment

## Purpose

The demo deployment exposes a polished public review page and serves the live chat flow from the same public origin.

## Files Involved

- `demo.html`
- `Dockerfile.demo`
- `docker-compose.demo.yml`
- `docker/entrypoint.sh`
- `docker/demo-nginx.conf`
- `DEMO_DOCKER.md`

## Deployment Model

The demo container does two jobs:

1. Serves the static landing page and supporting docs on port `4040`
2. Proxies `/webhook/*` to the local n8n instance

This allows one public host to serve both:

- `/` -> review page
- `/webhook/unified-webhook-id/chat` -> n8n chat endpoint through nginx proxying

## Runtime Configuration

### Main environment variables

- `N8N_CHAT_URL`
- `N8N_UPSTREAM_BASE`
- `DEMO_TITLE`
- `DEMO_BADGE`

### Current recommended defaults

```bash
N8N_CHAT_URL=/webhook/unified-webhook-id/chat
N8N_UPSTREAM_BASE=http://host.docker.internal:5678
DEMO_TITLE="TeamSync AI"
DEMO_BADGE="Public Review Build"
```

`config.js` is generated at container startup, so the page can be repointed without editing `demo.html`.

## Same-Origin Chat Routing

The current container startup script writes an nginx config that proxies:

```text
/webhook/* -> http://host.docker.internal:5678
```

That makes these assumptions explicit:

- Docker can reach the host through `host.docker.internal`
- n8n is listening on port `5678`
- the `unified-webhook-id` chat webhook is active in n8n

## Local Launch

```bash
docker compose -f docker-compose.demo.yml up -d --build
```

Primary local endpoint:

```text
http://localhost:4040
```

Health endpoint:

```text
http://localhost:4040/healthz
```

## Public Exposure

If you expose the demo container through a public tunnel or reverse proxy, the preferred model is:

- public root path -> demo container `/`
- public `/webhook/*` path -> same demo container, then proxied to local n8n

This avoids splitting the demo page and the chat endpoint across different hosts.

## Fallback Behavior

- The page first tries to embed chat in an iframe
- If embedding fails, it exposes the direct chat link instead
- This is expected when the upstream chat page uses iframe-restrictive headers

## Verification Checklist

- container is running and bound to `4040:4040`
- `/healthz` returns `ok`
- generated `config.js` contains the expected chat path
- nginx config inside the container proxies `/webhook/*`
- the public root URL loads the page
- the public chat path reaches the active n8n webhook

## Common Failure Modes

- `host.docker.internal` not available in the Docker runtime
- n8n not running on `5678`
- webhook ID mismatch
- tunnel points at the wrong container or wrong port
- iframe embedding blocked, requiring direct-link fallback
