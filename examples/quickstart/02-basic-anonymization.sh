#!/usr/bin/env bash
set -euo pipefail
PASSED=true
trap 'PASSED=false' ERR

ANONREQ_API_KEY="${ANONREQ_API_KEY:-test-key-0123456789abcdef}"
START_TIME=$(date +%s)

echo "=== Phase: Basic Anonymization ==="

RESPONSE=$(curl -s -w "\n%{http_code}" \
  -H "Authorization: Bearer $ANONREQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "user", "content": "Hi, my email is john.doe@example.com and my phone is +1-555-123-4567"}
    ]
  }' \
  http://localhost:8000/v1/chat/completions)

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" != "200" ]; then
  echo "FAIL: API returned HTTP $HTTP_CODE"
  echo "$BODY"
  PASSED=false
else
  echo "$BODY" | python3 -c "
import json, sys
data = json.load(sys.stdin)
content = data['choices'][0]['message']['content']
assert '[EMAIL_1]' in content, 'Missing [EMAIL_1] token'
assert '[PHONE_1]' in content, 'Missing [PHONE_1] token'
print('Tokenized content:', content)
" && echo "PASS: Tokens found in response"
fi

ELAPSED=$(( $(date +%s) - START_TIME ))
if [ "$PASSED" = true ]; then
  echo "=== PASS (${ELAPSED}s) — Anonymization verified ==="
  exit 0
else
  echo "=== FAIL (${ELAPSED}s) ==="
  exit 1
fi
