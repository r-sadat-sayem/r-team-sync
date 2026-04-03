#!/usr/bin/env bash
# export-workflows.sh — Export all active n8n workflows to ./n8n/workflows/
# Run: bash pipeline/scripts/export-workflows.sh (or: make export-workflows)
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

[ -f ".env" ] && export $(grep -v '^#' .env | xargs) 2>/dev/null || true

N8N_URL="${N8N_URL:-http://localhost:5678}"
N8N_API_KEY="${N8N_API_KEY:-}"
OUT_DIR="${PROJECT_ROOT}/n8n/workflows"

if [ -z "${N8N_API_KEY}" ]; then
  echo "ERROR: N8N_API_KEY not set. Add it to .env and re-run."
  exit 1
fi

mkdir -p "${OUT_DIR}"
echo "[export] Fetching workflow list from ${N8N_URL}..."

WORKFLOWS=$(curl -sf \
  -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
  "${N8N_URL}/api/v1/workflows")

echo "${WORKFLOWS}" | python3 - <<'PYEOF'
import sys, json, subprocess, os

data = json.loads(sys.stdin.read() if not sys.stdin.isatty() else open('/dev/stdin').read())
# This won't work inline — handled by the shell loop below
PYEOF

# Extract IDs and names with Python
mapfile -t WF_PAIRS < <(echo "${WORKFLOWS}" | python3 -c "
import sys, json, re
data = json.load(sys.stdin)
for wf in data.get('data', []):
    name = re.sub(r'[^a-zA-Z0-9_-]', '_', wf.get('name','workflow')).lower()
    print(f\"{wf['id']}:{name}\")
")

for PAIR in "${WF_PAIRS[@]}"; do
  WF_ID="${PAIR%%:*}"
  WF_NAME="${PAIR##*:}"
  FILE="${OUT_DIR}/${WF_NAME}_${WF_ID}.json"

  curl -sf \
    -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
    "${N8N_URL}/api/v1/workflows/${WF_ID}" \
    | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))" \
    > "${FILE}"

  echo "[export] Saved: n8n/workflows/${WF_NAME}_${WF_ID}.json"
done

echo "[export] Done. ${#WF_PAIRS[@]} workflow(s) exported to n8n/workflows/"
