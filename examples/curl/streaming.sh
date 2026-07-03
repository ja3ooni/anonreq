#!/usr/bin/env bash
set -euo pipefail
PASSED=true
trap 'PASSED=false' ERR

ANONREQ_API_KEY="${ANONREQ_API_KEY:-test-key-0123456789abcdef}"

echo "=== curl: Streaming ==="
RESPONSE=$(curl -s -N \
  -H "Authorization: Bearer $ANONREQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"Hi"}],"stream":true}' \
  http://localhost:8000/v1/chat/completions 2>&1)

if echo "$RESPONSE" | grep -q "data: \[DONE\]"; then
  echo "PASS: Streaming completed with [DONE] event"
  echo "$RESPONSE"
else
  echo "FAIL: Missing [DONE] event"
  echo "$RESPONSE"
  PASSED=false
fi

[ "$PASSED" = true ] && exit 0 || exit 1
