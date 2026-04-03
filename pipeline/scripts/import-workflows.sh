#!/usr/bin/env bash
# import-workflows.sh — Import n8n workflow JSON files from ./n8n/workflows/
# Run: bash pipeline/scripts/import-workflows.sh (or: make import-workflows)
# Note: This uses n8n's CLI import inside the container (safest approach for credentials).
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

[ -f ".env" ] && export $(grep -v '^#' .env | xargs) 2>/dev/null || true

WF_DIR="${PROJECT_ROOT}/n8n/workflows"
CONTAINER="${N8N_CONTAINER:-teamsync-n8n-1}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[import]${NC} $*"; }
warn()  { echo -e "${YELLOW}[import]${NC} $*"; }

# Fall back to root workflow file if n8n/workflows/ is empty
if [ -z "$(ls -A "${WF_DIR}" 2>/dev/null)" ]; then
  warn "n8n/workflows/ is empty. Looking for root-level workflow JSON files..."
  WF_FILES=$(find "${PROJECT_ROOT}" -maxdepth 1 -name "*.json" | head -20)
  if [ -z "${WF_FILES}" ]; then
    warn "No workflow JSON files found. Nothing to import."
    exit 0
  fi
  # Copy root JSONs to the workflows dir
  for f in $WF_FILES; do
    cp "$f" "${WF_DIR}/"
    info "Staged: $(basename $f)"
  done
fi

# ── Check container is running ────────────────────────────────────────────────
if ! docker ps --format '{{.Names}}' | grep -q "${CONTAINER}"; then
  warn "n8n container '${CONTAINER}' not running. Start with 'make dev' first."
  exit 1
fi

info "Importing workflows from n8n/workflows/ into ${CONTAINER}..."

for WF_FILE in "${WF_DIR}"/*.json; do
  BASENAME=$(basename "${WF_FILE}")
  info "  Importing: ${BASENAME}"
  docker cp "${WF_FILE}" "${CONTAINER}:/tmp/${BASENAME}"
  docker exec "${CONTAINER}" n8n import:workflow --input="/tmp/${BASENAME}" && \
    info "  OK: ${BASENAME}" || \
    warn "  FAILED: ${BASENAME} — check n8n logs"
done

info "Import complete. Activate workflows in the n8n UI at http://localhost:5678"
warn "REMINDER: Re-configure credentials in n8n after import:"
warn "  - Ollama account (URL + model)"
warn "  - Gmail OAuth"
warn "  - JIRA Software Cloud"
