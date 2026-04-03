#!/usr/bin/env bash
# dev.sh — Start the full TeamSync AI development stack
# Run: bash pipeline/scripts/dev.sh (or: make dev)
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${GREEN}[dev]${NC} $*"; }
warn() { echo -e "${YELLOW}[dev]${NC} $*"; }

# ── Prerequisite checks ───────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  warn ".env not found. Run 'make setup' first."
  exit 1
fi

# ── Pull latest images (skip if no internet) ─────────────────────────────────
info "Pulling latest base images..."
docker compose -f pipeline/docker/docker-compose.dev.yml --env-file .env pull --ignore-pull-failures 2>/dev/null || true

# ── Start stack ───────────────────────────────────────────────────────────────
info "Starting dev stack..."
docker compose -f pipeline/docker/docker-compose.dev.yml --env-file .env up --build -d

# ── Wait for PostgreSQL ───────────────────────────────────────────────────────
info "Waiting for PostgreSQL to be healthy..."
for i in $(seq 1 30); do
  if docker compose -f pipeline/docker/docker-compose.dev.yml --env-file .env exec postgres \
       pg_isready -U "${DB_USER:-n8n}" -q 2>/dev/null; then
    break
  fi
  sleep 2
done

# ── Run DB migrations ─────────────────────────────────────────────────────────
info "Running database migrations..."
docker compose -f pipeline/docker/docker-compose.dev.yml --env-file .env exec backend \
  alembic upgrade head 2>/dev/null || warn "Migration skipped (backend may still be starting)"

# ── Status ────────────────────────────────────────────────────────────────────
echo ""
info "Dev stack is running!"
echo -e ""
echo -e "  ${GREEN}Frontend  ${NC}  http://localhost:3000"
echo -e "  ${GREEN}Backend   ${NC}  http://localhost:8000"
echo -e "  ${GREEN}API Docs  ${NC}  http://localhost:8000/docs"
echo -e "  ${GREEN}n8n       ${NC}  http://localhost:5678"
echo -e "  ${GREEN}Demo page ${NC}  http://localhost:4040"
echo -e ""
echo -e "  ${YELLOW}Tail logs:${NC} make logs"
echo -e "  ${YELLOW}Stop:     ${NC} make dev-down"
echo ""
