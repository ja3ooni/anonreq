#!/usr/bin/env bash
# One-command xAI demo: generate missing local secrets into .env (gitignored),
# bring up base + Germany + demo overlays, wait for health, warm Presidio.
set -euo pipefail
cd "$(dirname "$0")/.."
ENV_FILE=.env
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.germany.yml -f docker-compose.demo.yml)

touch "$ENV_FILE"; chmod 600 "$ENV_FILE"
gen() { python3 -c "import secrets;print(secrets.token_urlsafe($1))"; }
ensure() { # ensure VAR value-if-missing
  local cur; cur=$(grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- || true)
  if [[ -z "$cur" || "$cur" == \<* ]]; then
    sed -i.bak "/^$1=/d" "$ENV_FILE" && rm -f "$ENV_FILE.bak"; echo "$1=$2" >> "$ENV_FILE"; echo "generated $1"
  fi
}
ensure ANONREQ_API_KEY "$(gen 32)"
ensure ANONREQ_ADMIN_API_KEY "$(gen 32)"
ensure ANONREQ_KMS_MASTER_KEY "$(gen 32)"
ensure ANONREQ_ANCHOR_SIGNING_KEY "$(gen 32)"
ensure POSTGRES_USER "anonreq"
ensure MINIO_ROOT_USER "anonreq-demo"
ensure MINIO_ROOT_PASSWORD "$(gen 24)"
ensure POSTGRES_PASSWORD "$(gen 24)"
ensure ANONREQ_DEMO_MODEL "grok-4"
if [[ -n "${XAI_API_KEY:-}" ]]; then ensure XAI_API_KEY "$XAI_API_KEY"; fi
if ! grep -qE '^XAI_API_KEY=[^<]' "$ENV_FILE"; then
  echo "ERROR: XAI_API_KEY not set. export XAI_API_KEY=... (or add it to .env) and re-run." >&2; exit 1
fi

# PROVIDER_API_KEY is required by the Germany overlay; for the xAI demo it is
# the xAI key (the demo overlay maps XAI_API_KEY -> PROVIDER_API_KEY).
XAI_VAL=$(grep -E "^XAI_API_KEY=" "$ENV_FILE" | tail -1 | cut -d= -f2-)
sed -i.bak "/^PROVIDER_API_KEY=/d" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
echo "PROVIDER_API_KEY=$XAI_VAL" >> "$ENV_FILE"

# Presidio (en+de spaCy) needs >= 4 GB; check the Docker VM.
MEM=$(docker info --format '{{.MemTotal}}' 2>/dev/null || echo 0)
if [[ "$MEM" -lt 4000000000 ]]; then
  echo "ERROR: Docker has $((MEM/1024/1024)) MiB RAM; the German Presidio image needs >= 4 GB." >&2
  echo "Docker Desktop: Settings > Resources > Memory >= 6 GB, then re-run." >&2
  exit 1
fi

"${COMPOSE[@]}" config -q
echo "Building images (incl. local anonreq/presidio-analyzer:2.2.354-de; first build downloads ~540 MB de_core_news_lg)..."
"${COMPOSE[@]}" build
"${COMPOSE[@]}" up -d --wait --wait-timeout 420

echo "Warming Presidio (first analyze loads models)..."
for i in $(seq 1 30); do
  if "${COMPOSE[@]}" exec -T presidio-analyzer python -c "import json,urllib.request as u;r=u.Request('http://localhost:3000/analyze',data=json.dumps({'text':'Max Mustermann wohnt in Berlin','language':'de'}).encode(),headers={'Content-Type':'application/json'});u.urlopen(r,timeout=60).read()" >/dev/null 2>&1; then
    echo "Presidio warm."; break; fi; sleep 3
done

ANONREQ_DEMO_MODEL=$(grep -E "^ANONREQ_DEMO_MODEL=" "$ENV_FILE" | tail -1 | cut -d= -f2-)
echo "Demo ready: http://localhost:8080  (model: $ANONREQ_DEMO_MODEL)"
echo "Try: curl -s localhost:8080/v1/chat/completions -H \"Authorization: Bearer \$ANONREQ_API_KEY\" -H 'X-AnonReq-Locale: de-DE' -H 'Content-Type: application/json' -d '{\"model\":\"$ANONREQ_DEMO_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Hallo, ich bin Max Mustermann\"}]}'"
