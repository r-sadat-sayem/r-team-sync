#!/usr/bin/env bash
# setup.sh — One-time environment setup for TeamSync AI
# Run: bash pipeline/scripts/setup.sh (or: make setup)
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${GREEN}[setup]${NC} $*"; }
warn()    { echo -e "${YELLOW}[setup]${NC} $*"; }
error()   { echo -e "${RED}[setup] ERROR:${NC} $*" >&2; exit 1; }

# ── Prerequisites check ──────────────────────────────────────────────────────
info "Checking prerequisites..."
command -v docker  >/dev/null 2>&1 || error "Docker not installed. Install: https://docs.docker.com/get-docker/"
command -v git     >/dev/null 2>&1 || error "Git not installed."

# ── .env file ────────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  info "Copying .env.example → .env"
  cp pipeline/docker/.env.example .env
  warn "IMPORTANT: Edit .env and fill in all required values before running 'make dev'"
else
  warn ".env already exists — skipping copy. Remove it and re-run to reset."
fi

# ── Generate secrets ─────────────────────────────────────────────────────────
info "Generating secrets..."

# N8N_ENCRYPTION_KEY (32-char hex)
if grep -q "CHANGE_ME_32_CHAR_ENCRYPTION_KEY" .env 2>/dev/null; then
  N8N_KEY=$(openssl rand -hex 16)
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/CHANGE_ME_32_CHAR_ENCRYPTION_KEY/${N8N_KEY}/" .env
  else
    sed -i "s/CHANGE_ME_32_CHAR_ENCRYPTION_KEY/${N8N_KEY}/" .env
  fi
  info "  N8N_ENCRYPTION_KEY generated"
fi

# DB_PASSWORD
if grep -q "CHANGE_ME_DB_PASSWORD" .env 2>/dev/null; then
  DB_PASS=$(openssl rand -base64 18 | tr -dc 'a-zA-Z0-9' | head -c 20)
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/CHANGE_ME_DB_PASSWORD/${DB_PASS}/" .env
  else
    sed -i "s/CHANGE_ME_DB_PASSWORD/${DB_PASS}/" .env
  fi
  info "  DB_PASSWORD generated"
fi

# BACKEND_API_KEY
if grep -q "CHANGE_ME_API_KEY" .env 2>/dev/null; then
  API_KEY="ts_$(openssl rand -hex 20)"
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/CHANGE_ME_API_KEY/${API_KEY}/" .env
  else
    sed -i "s/CHANGE_ME_API_KEY/${API_KEY}/" .env
  fi
  info "  BACKEND_API_KEY generated: ${API_KEY}"
  warn "  Save this key — it is used by the frontend to call the backend."
fi

# ── Docker volumes ────────────────────────────────────────────────────────────
info "Creating Docker volumes..."
docker volume create teamsync_postgres_data 2>/dev/null && info "  Volume: teamsync_postgres_data" || warn "  Volume already exists: teamsync_postgres_data"
docker volume create teamsync_n8n_data 2>/dev/null && info "  Volume: teamsync_n8n_data" || warn "  Volume already exists: teamsync_n8n_data"

# ── n8n workflow directory ────────────────────────────────────────────────────
mkdir -p n8n/workflows
info "Created n8n/workflows/ directory for workflow JSON exports"

# ── Backup directory ──────────────────────────────────────────────────────────
mkdir -p backups
info "Created backups/ directory"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
info "Setup complete!"
echo -e "  Next steps:"
echo -e "  1. ${YELLOW}Edit .env${NC} — fill in OLLAMA_BASE_URL, JIRA_*, GMAIL_* etc."
echo -e "  2. ${YELLOW}make dev${NC}  — start the full development stack"
echo -e "  3. ${YELLOW}make import-workflows${NC} — import n8n workflow JSON"
echo ""
