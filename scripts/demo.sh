#!/usr/bin/env bash
# One-command xAI demo: generate missing local secrets into .env (gitignored),
# bring up base + Germany + demo overlays, wait for health, warm Presidio.
set -euo pipefail
cd "$(dirname "$0")/.."
ENV_FILE=.env
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.germany.yml -f docker-compose.demo.yml)
WEB_COMPOSE=(docker compose -p anonreq-web --env-file "$ENV_FILE" -f web/docker-compose.yml -f web/docker-compose.demo.yml)

touch "$ENV_FILE"; chmod 600 "$ENV_FILE"
# shellcheck source=scripts/lib/demo_env.sh
. scripts/lib/demo_env.sh   # cwd is the repo root (cd above)
repair_glued_env "$ENV_FILE"
sanitize_db_url "$ENV_FILE"
gen() { python3 -c "import secrets;print(secrets.token_urlsafe($1))"; }
ensure() { # ensure VAR value-if-missing
  local cur; cur=$(get_env_var "$1")
  # Treat empty, <placeholder> and well-known default creds (minioadmin) as missing.
  if [[ -z "$cur" || "$cur" == \<* || "$cur" == "minioadmin" ]]; then
    set_env_var "$1" "$2"; echo "generated $1"
  fi
}
ensure ANONREQ_API_KEY "$(gen 32)"
ensure ANONREQ_ADMIN_API_KEY "$(gen 32)"
ensure ANONREQ_ADMIN_TENANT_ID "default"
ensure ANONREQ_KMS_MASTER_KEY "$(gen 32)"
ensure ANONREQ_ANCHOR_SIGNING_KEY "$(gen 32)"
ensure POSTGRES_USER "anonreq"
ensure MINIO_ROOT_USER "anonreq-$(python3 -c "import secrets;print(secrets.token_hex(6))")"
ensure MINIO_ROOT_PASSWORD "$(gen 24)"
ensure POSTGRES_PASSWORD "$(gen 24)"
ensure ANONREQ_DEMO_MODEL "grok-4"
if [[ -n "${XAI_API_KEY:-}" ]]; then ensure XAI_API_KEY "$XAI_API_KEY"; fi
XAI_VAL=$(get_env_var XAI_API_KEY)
if [[ -z "$XAI_VAL" || "$XAI_VAL" == \<* ]]; then
  echo "ERROR: XAI_API_KEY not set. export XAI_API_KEY=... (or add it to .env) and re-run." >&2; exit 1
fi

# PROVIDER_API_KEY is required by the Germany overlay; for the xAI demo it is
# the xAI key (the demo overlay maps XAI_API_KEY -> PROVIDER_API_KEY).
set_env_var PROVIDER_API_KEY "$XAI_VAL"

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
WARM_OK=0
for _ in $(seq 1 30); do
  if "${COMPOSE[@]}" exec -T presidio-analyzer python -c "import json,urllib.request as u;r=u.Request('http://localhost:3000/analyze',data=json.dumps({'text':'Max Mustermann wohnt in Berlin','language':'de'}).encode(),headers={'Content-Type':'application/json'});u.urlopen(r,timeout=60).read()" >/dev/null 2>&1; then
    WARM_OK=1; echo "Presidio warm."; break; fi; sleep 3
done
if [[ "$WARM_OK" -ne 1 ]]; then
  echo "ERROR: Presidio warm-up failed after 30 attempts (German /analyze never succeeded)." >&2
  echo "Check: ${COMPOSE[*]} logs presidio-analyzer   (memory >= 6 GB? still loading models?)" >&2
  exit 1
fi

# Demo UI (web/, PR #12). Started after the gateway stack is healthy so it can
# join anonreq_anonreq-net and reach anonreq-gateway:8080. --env-file: the web
# compose interpolates ANONREQ_* from the root .env (its project dir is web/).
UI_URL=""
if [[ -f web/docker-compose.demo.yml ]]; then
  echo "Starting demo UI (web/docker-compose.demo.yml)..."
  "${WEB_COMPOSE[@]}" up -d --build --wait --wait-timeout 300
  UI_URL="http://localhost:3000"
else
  echo "NOTE: web/docker-compose.demo.yml not found (PR #12 not merged); skipping the UI. API only on http://localhost:8080."
fi

ANONREQ_DEMO_MODEL=$(get_env_var ANONREQ_DEMO_MODEL)
if [[ -n "$UI_URL" ]]; then echo "Demo UI ready: $UI_URL"; fi
echo "Gateway API: http://localhost:8080  (model: $ANONREQ_DEMO_MODEL)"
# Keys are never printed. These lines (literal, single-quoted heredoc) load
# them from .env into the user's shell; tr strips a CRLF ending.
echo "Load the keys into your shell (run from the repo root; values are not shown):"
cat <<'EOS'
  export ANONREQ_API_KEY="$(grep -E '^[[:space:]]*(export[[:space:]]+)?ANONREQ_API_KEY=' .env | tail -n1 | cut -d= -f2- | tr -d '\r')"
  export ANONREQ_ADMIN_API_KEY="$(grep -E '^[[:space:]]*(export[[:space:]]+)?ANONREQ_ADMIN_API_KEY=' .env | tail -n1 | cut -d= -f2- | tr -d '\r')"
EOS
echo "Try: curl -s localhost:8080/v1/chat/completions -H \"Authorization: Bearer \$ANONREQ_API_KEY\" -H 'X-AnonReq-Tenant-ID: default' -H 'X-AnonReq-Locale: de-DE' -H 'Content-Type: application/json' -d '{\"model\":\"$ANONREQ_DEMO_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Hallo, ich bin Max Mustermann\"}]}'"
