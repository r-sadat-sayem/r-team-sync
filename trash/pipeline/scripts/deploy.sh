#!/usr/bin/env bash
# deploy.sh — Deploy TeamSync AI to production server via SSH
# Prerequisites: DEPLOY_HOST, DEPLOY_USER, DEPLOY_PATH, DEPLOY_SSH_KEY set in .env
# Run: bash pipeline/scripts/deploy.sh (or: make deploy)
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[deploy]${NC} $*"; }
error() { echo -e "${RED}[deploy] ERROR:${NC} $*" >&2; exit 1; }

# ── Load env ──────────────────────────────────────────────────────────────────
[ -f ".env" ] && export $(grep -v '^#' .env | xargs) 2>/dev/null || true

DEPLOY_HOST="${DEPLOY_HOST:-}"
DEPLOY_USER="${DEPLOY_USER:-deploy}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/teamsync}"
DEPLOY_SSH_KEY="${DEPLOY_SSH_KEY:-~/.ssh/id_rsa}"
TAG="${TAG:-latest}"

[ -z "$DEPLOY_HOST" ] && error "DEPLOY_HOST not set in .env"

SSH="ssh -i ${DEPLOY_SSH_KEY} -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST}"
SCP="scp -i ${DEPLOY_SSH_KEY} -o StrictHostKeyChecking=no"

# ── Build images ──────────────────────────────────────────────────────────────
info "Building production images..."
TAG="${TAG}" bash pipeline/scripts/build.sh

# ── Copy files to server ──────────────────────────────────────────────────────
info "Syncing files to ${DEPLOY_HOST}:${DEPLOY_PATH}..."
$SSH "mkdir -p ${DEPLOY_PATH}"

# Copy only what the server needs (not source code, not .git)
rsync -az --delete \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='__pycache__' \
  --exclude='.env' \
  --exclude='backups' \
  -e "ssh -i ${DEPLOY_SSH_KEY} -o StrictHostKeyChecking=no" \
  pipeline/docker/docker-compose.yml \
  pipeline/nginx/nginx.conf \
  "${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/"

# Copy .env.prod if it exists (never copy .env directly)
if [ -f ".env.prod" ]; then
  $SCP .env.prod "${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/.env"
  info "Copied .env.prod → remote .env"
fi

# ── Save and transfer Docker images ──────────────────────────────────────────
info "Transferring Docker images..."
for svc in backend frontend demo; do
  docker save "teamsync-${svc}:${TAG}" | gzip | \
    $SSH "docker load"
  info "  Loaded teamsync-${svc}:${TAG} on remote"
done

# ── Deploy on server ──────────────────────────────────────────────────────────
info "Starting production stack on ${DEPLOY_HOST}..."
$SSH "cd ${DEPLOY_PATH} && \
  docker compose -f docker-compose.yml --env-file .env pull --ignore-pull-failures 2>/dev/null; \
  docker compose -f docker-compose.yml --env-file .env up -d --remove-orphans; \
  docker compose -f docker-compose.yml --env-file .env exec backend alembic upgrade head"

# ── Health check ──────────────────────────────────────────────────────────────
info "Running health check..."
sleep 8
if $SSH "curl -sf http://localhost:8000/health > /dev/null"; then
  info "Backend health check passed."
else
  warn "Backend health check failed — check logs with: make logs-backend"
fi

info "Deployment complete! Server: https://${DEPLOY_HOST}"
