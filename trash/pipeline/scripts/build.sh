#!/usr/bin/env bash
# build.sh — Build all Docker images and optionally push to registry
# Run: bash pipeline/scripts/build.sh (or: make build)
# Options:
#   PUSH=1 bash pipeline/scripts/build.sh   — also push to registry
#   TAG=v1.2.3 bash pipeline/scripts/build.sh — tag images with version
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${GREEN}[build]${NC} $*"; }
warn() { echo -e "${YELLOW}[build]${NC} $*"; }

TAG="${TAG:-latest}"
PUSH="${PUSH:-0}"
REGISTRY="${REGISTRY:-}"  # e.g. ghcr.io/your-org/teamsync

info "Building images (tag: ${TAG})..."

# ── Backend ───────────────────────────────────────────────────────────────────
info "Building backend (FastAPI)..."
docker build \
  --file backend/Dockerfile \
  --tag "teamsync-backend:${TAG}" \
  --tag "teamsync-backend:latest" \
  --target production \
  backend/
info "  teamsync-backend:${TAG} built"

# ── Frontend ──────────────────────────────────────────────────────────────────
info "Building frontend (Next.js)..."
docker build \
  --file frontend/Dockerfile \
  --tag "teamsync-frontend:${TAG}" \
  --tag "teamsync-frontend:latest" \
  --target production \
  frontend/
info "  teamsync-frontend:${TAG} built"

# ── Demo page ─────────────────────────────────────────────────────────────────
info "Building demo page (nginx)..."
docker build \
  --file Dockerfile.demo \
  --tag "teamsync-demo:${TAG}" \
  --tag "teamsync-demo:latest" \
  .
info "  teamsync-demo:${TAG} built"

# ── Push to registry (optional) ───────────────────────────────────────────────
if [ "${PUSH}" = "1" ]; then
  if [ -z "${REGISTRY}" ]; then
    warn "REGISTRY not set — skipping push. Set REGISTRY=ghcr.io/your-org/teamsync"
  else
    info "Pushing to ${REGISTRY}..."
    for svc in backend frontend demo; do
      docker tag "teamsync-${svc}:${TAG}" "${REGISTRY}-${svc}:${TAG}"
      docker push "${REGISTRY}-${svc}:${TAG}"
      info "  Pushed ${REGISTRY}-${svc}:${TAG}"
    done
  fi
fi

info "All images built successfully."
docker images | grep teamsync
