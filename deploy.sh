#!/usr/bin/env bash
# deploy.sh — start TeamSync v2.0 locally (Postgres + Backend + Frontend)
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh            # local dev (venv + npm)
#   ./deploy.sh --docker   # full Docker Compose stack
set -eo pipefail   # intentionally NO -u; empty arrays are fine

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

info()    { echo -e "${CYAN}[TeamSync]${NC} $*"; }
success() { echo -e "${GREEN}[  OK   ]${NC} $*"; }
warn()    { echo -e "${YELLOW}[ WARN  ]${NC} $*"; }
error()   { echo -e "${RED}[ ERROR ]${NC} $*"; exit 1; }

# ── Docker Compose mode ───────────────────────────────────────────────────────
if [[ "${1:-}" == "--docker" ]]; then
  info "Starting full Docker Compose stack..."
  [[ ! -f "$BACKEND_DIR/.env" ]] && cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env" \
    && warn ".env created from .env.example — fill in your API keys before using."
  cd "$SCRIPT_DIR"
  docker compose up --build
  exit 0
fi

# ── Local dev mode ────────────────────────────────────────────────────────────

PIDS=()
POSTGRES_STARTED=false

cleanup() {
  echo ""
  info "Shutting down..."
  if [[ ${#PIDS[@]} -gt 0 ]]; then
    for pid in "${PIDS[@]}"; do
      kill "$pid" 2>/dev/null || true
    done
  fi
  if [[ "$POSTGRES_STARTED" == "true" ]]; then
    info "Stopping Postgres container..."
    docker stop teamsync-postgres 2>/dev/null || true
  fi
  success "All services stopped."
}
trap cleanup INT TERM EXIT

# ── 1. Preflight checks ───────────────────────────────────────────────────────
command -v docker  &>/dev/null || error "docker is not installed."
command -v python3 &>/dev/null || error "python3 is not installed."
command -v npm     &>/dev/null || error "npm is not installed."

# ── 2. .env setup ─────────────────────────────────────────────────────────────
if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  warn "Created backend/.env from .env.example — fill in RAKUTEN_AI_GATEWAY_KEY and other keys."
fi

if [[ ! -f "$FRONTEND_DIR/.env" ]] && [[ -f "$FRONTEND_DIR/.env.example" ]]; then
  cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
fi

# ── 3. Postgres ───────────────────────────────────────────────────────────────
# Check if port 5432 is already bound (any Postgres — Docker or native)
if lsof -i :5432 -sTCP:LISTEN &>/dev/null 2>&1; then
  success "Port 5432 already in use — using existing Postgres."
  POSTGRES_STARTED=false
elif docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^teamsync-postgres$"; then
  success "teamsync-postgres container already running."
  POSTGRES_STARTED=false
else
  info "Starting Postgres 15 container on :5432..."
  docker run -d \
    --name teamsync-postgres \
    --rm \
    -e POSTGRES_USER=teamsync \
    -e POSTGRES_PASSWORD=teamsync \
    -e POSTGRES_DB=teamsync \
    -p 5432:5432 \
    postgres:15-alpine \
    >/dev/null
  POSTGRES_STARTED=true

  info "Waiting for Postgres to be ready..."
  for i in {1..20}; do
    docker exec teamsync-postgres pg_isready -U teamsync &>/dev/null && break
    sleep 1
    [[ $i -eq 20 ]] && error "Postgres did not become ready in time."
  done
  success "Postgres is ready."
fi

# ── 4. Python venv ────────────────────────────────────────────────────────────
VENV="$BACKEND_DIR/.venv"
if [[ ! -d "$VENV" ]]; then
  info "Creating Python virtual environment..."
  python3 -m venv "$VENV"
fi

info "Installing / syncing backend dependencies..."
"$VENV/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"
success "Backend dependencies ready."

# ── 5. Frontend dependencies ──────────────────────────────────────────────────
if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  info "Installing frontend dependencies (first run)..."
  npm --prefix "$FRONTEND_DIR" install --silent
  success "Frontend dependencies installed."
fi

# ── 6. Start backend ──────────────────────────────────────────────────────────
info "Starting backend on http://localhost:8000 ..."
(
  cd "$BACKEND_DIR"
  "$VENV/bin/uvicorn" src.main:app --reload --port 8000 --host 0.0.0.0
) &
PIDS+=($!)
sleep 2

# ── 7. Start frontend on :5173 ───────────────────────────────────────────────
if lsof -i :5173 -sTCP:LISTEN &>/dev/null 2>&1; then
  success "Port 5173 already in use — using existing frontend."
else
  info "Starting frontend on http://localhost:5173 ..."
  (
    cd "$FRONTEND_DIR"
    npm run dev -- --port 5173 --strictPort
  ) &
  PIDS+=($!)
fi

# ── 8. Done ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  TeamSync v2.0 is running${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Frontend  →  ${CYAN}http://localhost:5173${NC}"
echo -e "  Backend   →  ${CYAN}http://localhost:8000${NC}"
echo -e "  API docs  →  ${CYAN}http://localhost:8000/docs${NC}"
echo -e "  Postgres  →  ${CYAN}localhost:5432${NC}  (db: teamsync)"
echo ""
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop everything."
echo ""

wait
