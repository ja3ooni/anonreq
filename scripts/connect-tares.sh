#!/usr/bin/env bash
# Connect AnonReq Demo to GlassFlow Tares (sunny-ridge-aj.tares-glassflow.com or local).
# Usage:
#   ./scripts/connect-tares.sh [TARES_URL] [TARES_TOKEN]
# Examples:
#   ./scripts/connect-tares.sh https://sunny-ridge-aj.tares-glassflow.com/read <YOUR_TARES_API_KEY>
#   ./scripts/connect-tares.sh https://sunny-ridge-aj.tares-glassflow.com <YOUR_TARES_API_KEY>
set -euo pipefail
cd "$(dirname "$0")/.."

TARES_INPUT="${1:-${GLASSFLOW_TARES_WEBHOOK_URL:-https://sunny-ridge-aj.tares-glassflow.com}}"
TARES_TOKEN="${2:-${GLASSFLOW_TARES_TOKEN:-}}"
TARES_INPUT="${TARES_INPUT%/}"
TARES_BASE="${TARES_INPUT%/read}"
TARES_BASE="${TARES_BASE%/remember}"
TARES_BASE="${TARES_BASE%/health}"

echo "0. Checking Tares cell health at $TARES_BASE/health ..."
curl -sS "$TARES_BASE/health" && echo ""

AUTH_ARGS=()
if [[ -n "$TARES_TOKEN" ]]; then
  AUTH_ARGS=(-H "Authorization: Bearer $TARES_TOKEN" -H "X-API-Key: $TARES_TOKEN")
else
  echo ""
  echo "NOTE: Cell requires authentication. Grab your key from:"
  echo "  -> https://console.tares-glassflow.com/workspaces/sunny-ridge-aj#settings"
  echo "  -> or https://sunny-ridge-aj.tares-glassflow.com/"
  echo "Then re-run:"
  echo "  ./scripts/connect-tares.sh $TARES_BASE <YOUR_API_KEY>"
  echo "Or paste the key directly in the Web UI at http://127.0.0.1:3000/en (Tab 1: GlassFlow)."
  exit 0
fi

INGEST_URL="$TARES_INPUT"

echo "1. Pushing sanitized observation to $TARES_BASE/remember ..."
REM_CODE=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$TARES_BASE/remember" \
  -H "Content-Type: application/json" \
  "${AUTH_ARGS[@]}" \
  -d '{
    "key": "frankfurt-build-days-demo",
    "content": "[AnonReq ALLOW] scenario=sepa-dispute classification=CONFIDENTIAL highest_entity=IBAN_DE prompt=\"SEPA Dispute #4920 — Customer: [PERSON_1], verify IBAN [IBAN_DE_1] and Steuer-ID [TAX_ID_DE_1].\"",
    "memory_type": "observation",
    "source": "anonreq_gateway",
    "fields": {
      "correlation_key": "frankfurt-build-days-demo",
      "tenant_id": "frankfurt-demo-eu",
      "scenario": "sepa-dispute",
      "decision": "ALLOW",
      "classification": "CONFIDENTIAL",
      "highest_entity": "IBAN_DE",
      "raw_pii_leaked": false
    }
  }' || true)
echo "   -> POST /remember responded with HTTP $REM_CODE"

if [[ "$TARES_INPUT" != *"/ingest/"* ]]; then
  echo "2. Registering 'anonreq_gateway' webhook source on $TARES_BASE/api/sources ..."
  RESP=$(curl -sS -X POST "$TARES_BASE/api/sources" \
    -H "Content-Type: application/json" \
    "${AUTH_ARGS[@]}" \
    -d '{
      "name": "anonreq_gateway",
      "connector": "webhook",
      "config": {
        "event_type": "sanitized_interaction",
        "labels": [
          {"name": "correlation_key", "field": "correlation_key", "primary": true},
          {"name": "scenario", "field": "scenario", "primary": false},
          {"name": "decision", "field": "decision", "primary": false},
          {"name": "classification", "field": "classification", "primary": false}
        ]
      }
    }' || true)
  INGEST_KEY=$(python3 -c "import sys,json; d=json.loads(sys.argv[1]) if sys.argv[1].strip().startswith('{') else {}; print(d.get('ingest_key') or d.get('token') or '')" "$RESP" 2>/dev/null || true)
  if [[ -n "$INGEST_KEY" ]]; then
    INGEST_URL="$TARES_BASE/ingest/$INGEST_KEY"
    echo "   -> Created webhook source! Ingest URL: $INGEST_URL"
    HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$INGEST_URL" \
      -H "Content-Type: application/json" \
      "${AUTH_ARGS[@]}" \
      -d '{
        "specversion": "1.0",
        "id": "evt_smoke_frankfurt_01",
        "source": "urn:anonreq:gateway:de-frankfurt",
        "service": "anonreq-gateway",
        "type": "io.anonreq.gateway.sanitized_interaction",
        "subject": "tenant:frankfurt-demo-eu:scenario:sepa-dispute",
        "correlation_key": "frankfurt-build-days-demo",
        "tenant_id": "frankfurt-demo-eu",
        "scenario": "sepa-dispute",
        "decision": "ALLOW",
        "classification": "CONFIDENTIAL",
        "highest_entity": "IBAN_DE"
      }')
    echo "   -> POST $INGEST_URL responded with HTTP $HTTP_CODE"
  else
    INGEST_URL="$TARES_BASE"
  fi
fi

echo "3. Querying live POST $TARES_BASE/read ..."
curl -sS -X POST "$TARES_BASE/read" \
  -H "Content-Type: application/json" \
  "${AUTH_ARGS[@]}" \
  -d '{"selector": {}, "window": "15m", "client": "anonreq-cli", "include_payload": true}' | head -c 500
echo ""

if [[ -f scripts/lib/demo_env.sh ]]; then
  . scripts/lib/demo_env.sh
  set_env_var GLASSFLOW_TARES_WEBHOOK_URL "$INGEST_URL" .env
  set_env_var GLASSFLOW_TARES_TOKEN "$TARES_TOKEN" .env
  echo "4. Saved GLASSFLOW_TARES_WEBHOOK_URL and GLASSFLOW_TARES_TOKEN to .env"
fi
