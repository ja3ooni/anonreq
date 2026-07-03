#!/usr/bin/env bash
set -euo pipefail
PASSED=true
trap 'PASSED=false' ERR

ANONREQ_API_KEY="${ANONREQ_API_KEY:-test-key-0123456789abcdef}"

echo "=== curl: GDPR Preset ==="
RESPONSE=$(curl -s -w "\n%{http_code}" \
  -H "Authorization: Bearer $ANONREQ_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-AnonReq-Compliance-Preset: gdpr" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"My tax ID is 12345678901 and phone is +49-30-123456"}]}' \
  http://localhost:8000/v1/chat/completions)

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" != "200" ]; then
  echo "FAIL: HTTP $HTTP_CODE"
  echo "$BODY"
  PASSED=false
else
  echo "$BODY" | python3 -c "
import json, sys
data = json.load(sys.stdin)
content = data['choices'][0]['message']['content']
patterns = ['TAX_ID_1', 'PHONE_1']
for p in patterns:
    assert p in content or p.lower() in content, f'Missing {p}'
print('GDPR response:', content)
" && echo "PASS: GDPR tokens found"
fi

[ "$PASSED" = true ] && exit 0 || exit 1
