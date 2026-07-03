#!/usr/bin/env bash
set -euo pipefail
PASSED=true
trap 'PASSED=false' ERR

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
START_TIME=$(date +%s)

echo "=== Phase: Cleanup ==="

cd "$PROJECT_ROOT"
echo "Checking for errors in logs..."
ERROR_COUNT=$(docker compose logs anonreq 2>&1 | grep -c -i "error" || true)
if [ "$ERROR_COUNT" -gt 0 ]; then
  echo "WARNING: Found $ERROR_COUNT error(s) in logs"
  docker compose logs anonreq --tail=20
fi

echo "Stopping Docker Compose services..."
docker compose down

echo "Verifying cleanup..."
if docker compose ps 2>&1 | grep -q "Up"; then
  echo "FAIL: Some services still running"
  PASSED=false
else
  echo "PASS: All services stopped"
fi

ELAPSED=$(( $(date +%s) - START_TIME ))
if [ "$PASSED" = true ]; then
  echo "=== PASS (${ELAPSED}s) — Cleanup complete, zero errors ==="
  exit 0
else
  echo "=== FAIL (${ELAPSED}s) ==="
  exit 1
fi
