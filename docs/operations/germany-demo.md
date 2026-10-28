# Germany one-day demo

A Frankfurt CISO should be able to drop AnonReq in front of **their** Claude / ChatGPT / Gemini key and see identifiers leave as tokens. This is the honest path — not a 140-model cloud.

## What you are proving

1. A German bank ticket / insurance claim can be sent to `/v1/chat/completions`.
2. Steuer-ID, Personalausweis, KVNR, DE-IBAN never appear in the upstream prompt.
3. The user still gets a restored answer (except API keys, which stay masked).
4. A DPO can export a CSV of *entity types* masked — never the raw values.

## Path A — Docker Compose (fastest)

```bash
cp .env.example .env
# ANONREQ_API_KEY                 gateway client key (>= 32 chars)
# PROVIDER_API_KEY                customer OpenAI-compatible key (not ANONREQ_API_KEY)
# ANONREQ_OPENAI_API_KEY          optional; if set, it takes precedence over PROVIDER_API_KEY
# ANONREQ_ANTHROPIC_API_KEY       optional in Compose; startup still requires it while smart is configured
# ANONREQ_GEMINI_API_KEY          optional in Compose; startup still requires it while gemini-pro is configured
# mock, local, and ollama need no key. Startup refuses to boot otherwise.
# Placeholder values (change-me*, changeme, <...>, your-...-key) count as unset.

docker compose -f docker-compose.yml -f docker-compose.germany.yml up --build
```

`ANONREQ_OPENAI_API_KEY` is resolved before `PROVIDER_API_KEY`. When both are set, the OpenAI-compatible upstream receives `ANONREQ_OPENAI_API_KEY`. The xAI demo sets `ANONREQ_OPENAI_API_KEY` from `XAI_API_KEY` so that key is the one forwarded; `PROVIDER_API_KEY` is not used for OpenAI in that case. Compose leaves `ANONREQ_ANTHROPIC_API_KEY` and `ANONREQ_GEMINI_API_KEY` optional (`:-`) because `:?` is evaluated before overlays and would block an xAI-only render. Startup still refuses to boot while the `smart` or `gemini-pro` aliases exist and those keys are missing.

Gateway: `http://localhost:8080`

Load the keys from `.env` into your shell (Compose already injects them into the container; your terminal does not):

```bash
set -a && source .env && set +a
```

```bash
curl -s http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer $ANONREQ_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-AnonReq-Tenant-ID: default" \
  -H "X-AnonReq-Locale: de-DE" \
  -d '{
    "model": "fast",
    "messages": [{"role": "user", "content": "IBAN DE89370400440532013000 für Anna prüfen"}]
  }'
```

Use a configured alias from `config/model_aliases.yaml` (`fast` → OpenAI `gpt-4o-mini`, or `smart` / `gemini-pro` / `local`). Raw provider names like `gpt-4o` are rejected unless you add an alias.

**Prove anonymization:** response header `X-AnonReq-Processed: true`, model answer must not restate a clear DE-IBAN / Steuer-ID / Ausweis, and logs show `ForwardingGuard` `action: ANONYMIZE` (not `PASS`) plus non-empty `entity_counts` (`IBAN_DE`, …). A vague model refusal alone is not proof — OpenAI often refuses to echo IBANs even when cleartext was forwarded. Rebuild after pulling classification / policy-stage fixes:

```bash
docker compose -f docker-compose.yml -f docker-compose.germany.yml up --build -d
```

`X-AnonReq-Tenant-ID` is required on every `/v1` route (seed tenant: `default`).

Regulator export (admin key):

```bash
curl -s "http://localhost:8080/v1/admin/audit/anonymization-export?format=csv" \
  -H "Authorization: Bearer $ANONREQ_ADMIN_API_KEY" \
  -H "X-AnonReq-Tenant-ID: default" \
  -o anonymization-export.csv
```

The CSV columns are: timestamp, request_id, tenant, operator, model, locale, entity_types, token_count, decision. No identifiers.

Workflow inserts for the live demo (tickets / chat URL / claims text): `examples/connectors/`.

## Path B — Helm (their cluster)

Requires Valkey/Redis and Presidio reachable from the chart. Override the in-cluster URLs if your DNS names differ.

```bash
helm upgrade --install anonreq ./helm/anonreq \
  -f ./helm/anonreq/values-germany.yaml \
  --set secrets.ANONREQ_API_KEY="$ANONREQ_API_KEY" \
  --set secrets.PROVIDER_API_KEY="$PROVIDER_API_KEY" \
  --set secrets.ANONREQ_ANTHROPIC_API_KEY="$ANONREQ_ANTHROPIC_API_KEY" \
  --set secrets.ANONREQ_GEMINI_API_KEY="$ANONREQ_GEMINI_API_KEY" \
  --set env.ANONREQ_VALKEY_URL="redis://valkey:6379/0" \
  --set env.ANONREQ_PRESIDIO_URL="http://presidio-analyzer:3000"
```

The overlay exposes port **8080** (the image listen port). Point ingress TLS at that Service. HPA is **off** until you have a signed PoC.

## Fail-closed

If detection, cache, or the analyzer is down, AnonReq returns HTTP 5xx and **does not** forward the raw prompt.

## What this demo does not claim

- BSI C5
- ISO 27001
- Air-gap in four days (that is a later install bundle)
- Hosting 140 models — the customer brings the model key
