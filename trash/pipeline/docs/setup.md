# TeamSync AI — Setup Guide

## Prerequisites

| Tool | Min Version | Install |
|------|------------|---------|
| Docker | 24+ | https://docs.docker.com/get-docker/ |
| Docker Compose | v2 (bundled) | included with Docker |
| Git | any | https://git-scm.com |
| Ollama | any | https://ollama.ai (or shared server) |
| Node.js | 20+ | only needed if running frontend outside Docker |
| Python | 3.12+ | only needed if running backend outside Docker |

---

## Step 1 — Clone and Setup

```bash
git clone <repo-url> teamsync
cd teamsync

# One-time setup: generates secrets, creates Docker volumes, copies .env
make setup
```

This creates `.env` with auto-generated secrets for `N8N_ENCRYPTION_KEY`, `DB_PASSWORD`, and `BACKEND_API_KEY`.

---

## Step 2 — Configure .env

Open `.env` and fill in the values marked `CHANGE_ME` or left empty:

```bash
# Most important for local dev:
OLLAMA_BASE_URL=http://host.docker.internal:11434   # macOS/Windows default
# On Linux: OLLAMA_BASE_URL=http://172.17.0.1:11434 (or your LAN IP)

N8N_BASIC_AUTH_PASSWORD=choose-a-secure-password

# Leave these empty until you configure them in n8n:
# N8N_API_KEY=        (generate in n8n UI after first start)
```

JIRA and Gmail credentials are configured directly in the n8n UI after import — they are NOT stored in `.env`.

---

## Step 3 — Start the Stack

```bash
make dev
```

Services come up at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/docs (Swagger UI)
- **n8n**: http://localhost:5678
- **Demo page**: http://localhost:4040

---

## Step 4 — Import the n8n Workflow

```bash
make import-workflows
```

This copies `team_sync_dev_v2.1_with_JIRA.json` into the n8n container and imports it.

Then in the n8n UI:
1. Go to http://localhost:5678
2. Sign in with `N8N_BASIC_AUTH_USER` / `N8N_BASIC_AUTH_PASSWORD`
3. Open the imported workflow
4. **Re-configure credentials** (they are instance-specific):
   - **Ollama**: Set the URL from your `.env` `OLLAMA_BASE_URL`, select your model
   - **Gmail OAuth**: Follow n8n's OAuth flow
   - **JIRA**: Enter your Jira Cloud host, email, and API token
5. **Activate** the workflow (toggle at top-right)
6. Note the webhook URL shown — it will be `/webhook/unified-webhook-id/chat`

---

## Step 5 — Configure the Demo Page

Open http://localhost:4040. If the chat widget doesn't load automatically:
1. Click the **"Configure"** button (top right)
2. Enter your chat webhook URL: `http://localhost:5678/webhook/unified-webhook-id/chat`
3. Click Save — the chat will load immediately

Or update `.env` and restart:
```bash
# In .env:
N8N_CHAT_URL=/webhook/unified-webhook-id/chat
make demo
```

---

## Step 6 — Run Database Migrations

```bash
make db-migrate
```

This runs Alembic migrations to create the FastAPI backend's tables in PostgreSQL.

---

## Sharing With the Team (Internal)

### Option A — LAN (same network)
Find your machine's LAN IP:
```bash
# macOS
ipconfig getifaddr en0

# Linux
hostname -I | awk '{print $1}'
```

Share:
- `http://<YOUR_LAN_IP>:3000` — main app
- `http://<YOUR_LAN_IP>:5678/webhook/unified-webhook-id/chat` — chat webhook
- `http://<YOUR_LAN_IP>:4040` — demo page

> Make sure Docker ports are bound to `0.0.0.0` (default) not `127.0.0.1`.

### Option B — ngrok (internet access)
Install ngrok (https://ngrok.com/download), then:
```bash
# Expose the demo page
ngrok http 4040

# Or expose the main app
ngrok http 3000
```
Share the `https://xxxx.ngrok-free.app` URL. The webhook proxy in the demo container will handle routing.

### Option C — Cloudflare Tunnel (persistent URL, free)
```bash
cloudflared tunnel --url http://localhost:3000
```
Gives a persistent `https://*.trycloudflare.com` URL.

---

## Ollama Setup for the Team

If teammates run Ollama locally:
```bash
# Each team member runs this on their machine:
ollama pull gpt-oss:20b-cloud   # or whatever model you're using
ollama pull mistral:latest

# Verify Ollama is accessible:
curl http://localhost:11434/api/tags
```

If using a shared Ollama server on your LAN:
```bash
# In .env on each machine:
OLLAMA_BASE_URL=http://192.168.1.xxx:11434   # shared server IP
```

---

## Generating the n8n API Key (for export-workflows / backup)

1. n8n UI → Settings (bottom left) → API
2. Click "Create an API Key"
3. Copy the key into `.env`:
   ```bash
   N8N_API_KEY=your-generated-key
   ```

---

## Troubleshooting

| Problem | Solution |
|---------|---------|
| Chat widget shows "not configured" | Check `N8N_CHAT_URL` in `.env`, restart demo |
| n8n workflow doesn't trigger | Make sure workflow is **active** (green toggle in n8n UI) |
| Ollama errors in n8n | Verify `OLLAMA_BASE_URL` is reachable from inside Docker (use `host.docker.internal` on Mac) |
| `make db-migrate` fails | Ensure backend container is running: `make ps` |
| Port already in use | Check `docker ps` and stop conflicting containers |
| JIRA tickets not created | Check Decision field in approval form = "APPROVE" (case-insensitive after Phase 1 fix) |
