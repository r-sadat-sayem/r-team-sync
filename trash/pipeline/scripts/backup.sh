#!/usr/bin/env bash
# backup.sh — Backup PostgreSQL database and n8n workflow data
# Run: bash pipeline/scripts/backup.sh (or: make backup)
# Cron: 0 2 * * * /path/to/project/pipeline/scripts/backup.sh >> /var/log/teamsync-backup.log 2>&1
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

[ -f ".env" ] && export $(grep -v '^#' .env | xargs) 2>/dev/null || true

BACKUP_DIR="${PROJECT_ROOT}/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_USER="${DB_USER:-n8n}"
DB_NAME="${DB_NAME:-teamsync}"
N8N_API_KEY="${N8N_API_KEY:-}"
N8N_URL="http://localhost:5678"
RETAIN_DAYS="${BACKUP_RETAIN_DAYS:-30}"

mkdir -p "${BACKUP_DIR}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${GREEN}[backup ${DATE}]${NC} $*"; }
warn() { echo -e "${YELLOW}[backup ${DATE}]${NC} $*"; }

# ── PostgreSQL dump ───────────────────────────────────────────────────────────
info "Dumping PostgreSQL (${DB_NAME})..."
docker compose -f pipeline/docker/docker-compose.dev.yml --env-file .env exec -T postgres \
  pg_dump -U "${DB_USER}" "${DB_NAME}" | \
  gzip > "${BACKUP_DIR}/db_${DATE}.sql.gz"
info "  Saved: backups/db_${DATE}.sql.gz"

# ── n8n workflow export ───────────────────────────────────────────────────────
info "Exporting n8n workflows..."
mkdir -p "${BACKUP_DIR}/workflows_${DATE}"

if [ -n "${N8N_API_KEY}" ]; then
  WORKFLOW_IDS=$(curl -sf \
    -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
    "${N8N_URL}/api/v1/workflows" | \
    python3 -c "import sys,json; [print(w['id']) for w in json.load(sys.stdin)['data']]" 2>/dev/null || echo "")

  for WF_ID in $WORKFLOW_IDS; do
    curl -sf \
      -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
      "${N8N_URL}/api/v1/workflows/${WF_ID}" \
      > "${BACKUP_DIR}/workflows_${DATE}/wf_${WF_ID}.json"
  done
  info "  Workflows saved to backups/workflows_${DATE}/"
else
  warn "  N8N_API_KEY not set — skipping workflow export"
fi

# ── Clean up old backups ──────────────────────────────────────────────────────
info "Removing backups older than ${RETAIN_DAYS} days..."
find "${BACKUP_DIR}" -name "db_*.sql.gz" -mtime "+${RETAIN_DAYS}" -delete
find "${BACKUP_DIR}" -type d -name "workflows_*" -mtime "+${RETAIN_DAYS}" -exec rm -rf {} + 2>/dev/null || true

info "Backup complete: ${DATE}"
ls -lh "${BACKUP_DIR}" | tail -10
