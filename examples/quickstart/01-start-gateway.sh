#!/usr/bin/env bash
set -euo pipefail
PASSED=true
trap 'PASSED=false' ERR

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
START_TIME=$(date +%s)

echo "=== Phase: Starting AnonReq Gateway ==="

cd "$PROJECT_ROOT"
echo "Starting Docker Compose services..."
docker compose up -d --wait --wait-timeout 60

echo "Verifying health endpoint..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
if [ "$HTTP_CODE" != "200" ]; then
  echo "FAIL: Health check returned $HTTP_CODE (expected 200)"
  docker compose logs anonreq --tail=20
  PASSED=false
else
  echo "PASS: Gateway is healthy at http://localhost:8000"
fi

ELAPSED=$(( $(date +%s) - START_TIME ))
if [ "$PASSED" = true ]; then
  echo "=== PASS (${ELAPSED}s) — Gateway running at http://localhost:8000 ==="
  exit 0
else
  echo "=== FAIL (${ELAPSED}s) ==="
  exit 1
fi
