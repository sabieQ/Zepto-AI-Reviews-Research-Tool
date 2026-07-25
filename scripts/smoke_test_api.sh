#!/usr/bin/env bash
# Phase 6: run full E2E smoke (falls back to health-only if python missing)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_URL="${API_BASE_URL:-http://localhost:8000}"
export API_BASE_URL="$BASE_URL"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Python not found; health-only check"
  curl -sS "$BASE_URL/api/v1/health"
  exit 0
fi

"$PY" "$ROOT/scripts/smoke_e2e.py"
