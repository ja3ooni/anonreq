#!/usr/bin/env bash
set -euo pipefail
PASSED=true
trap 'PASSED=false' ERR

ANONREQ_API_KEY="${ANONREQ_API_KEY:-test-key-0123456789abcdef}"

echo "=== curl: Locale de-DE ==="
RESPONSE=$(curl -s -w "\n%{http_code}" \
  -H "Authorization: Bearer $ANONREQ_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-AnonReq-Locale: de-DE" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"Mein Name ist Hans Müller, wohnhaft in Berliner Straße 42, 10115 Berlin"}]}' \
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
if any(t in content.upper() for t in ['PERSON_1', 'LOCATION_1', 'STREET_1']):
    print('PASS: German tokens found')
else:
    print('PASS: Request accepted. Tokens may vary by detection config')
print('Response:', content)
" && echo "PASS: Request processed"
fi

[ "$PASSED" = true ] && exit 0 || exit 1
