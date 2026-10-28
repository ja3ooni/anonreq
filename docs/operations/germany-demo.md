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
# set ANONREQ_API_KEY (>= 32 chars) and PROVIDER_API_KEY (customer key)

docker compose -f docker-compose.yml -f docker-compose.germany.yml up --build
```

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
  --set env.ANONREQ_VALKEY_URL="redis://valkey:6379/0" \
  --set env.ANONREQ_PRESIDIO_URL="http://presidio-analyzer:3000"
```

The overlay exposes port **8080** (the image listen port). Point ingress TLS at that Service. HPA is **off** until you have a signed PoC.

## Names and street addresses

Names and street addresses are not in the German regex bundle. They are masked only when the analyzer runs with `language=de` and the German spaCy model is loaded. Send the same headers as the Path A request with a body such as:

```bash
curl -s http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer $ANONREQ_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-AnonReq-Tenant-ID: default" \
  -H "X-AnonReq-Locale: de-DE" \
  -d '{
    "model": "fast",
    "messages": [{"role": "user", "content": "Hans Müller, Hauptstraße 12, 60311 Frankfurt"}]
  }'
```

The upstream prompt must not contain `Hans Müller`, `Hauptstraße 12`, or `60311 Frankfurt`. The restored client response may contain them again.

## Presidio image (DevOps review)

The demo stack, including this Germany overlay, does **not** run the stock `mcr.microsoft.com/presidio-analyzer:2.2.354` container. `docker-compose.yml` builds `anonreq/presidio-analyzer:2.2.354-de` from `docker/presidio/Dockerfile`.

| Item | Stock image | Demo image |
| --- | --- | --- |
| Base | `mcr.microsoft.com/presidio-analyzer:2.2.354` | same pin, then a local build |
| spaCy models | `en_core_web_lg` | `en_core_web_lg` and `de_core_news_lg` (~540 MB extra) |
| Recognizer languages | `en` only (`AnalyzerEngine()` default) | `en` and `de` |
| Address patterns | none for German streets | `docker/presidio/german_recognizers.yaml` (street line and PLZ+city, score 0.85) |
| Listen port | 3000 | 3000 (unchanged) |
| RAM | stock | budget at least 4 GB once both models are loaded |
| Healthcheck `start_period` | 30s | 120s |

`X-AnonReq-Locale: de-DE` is mapped to Presidio `language=de`. A stock analyzer rejects that language (HTTP 500, no German recognizers). The gateway then fails closed and does not forward the prompt. Publishing the image:

```bash
docker compose build presidio-analyzer
docker tag anonreq/presidio-analyzer:2.2.354-de <registry>/anonreq/presidio-analyzer:2.2.354-de
docker push <registry>/anonreq/presidio-analyzer:2.2.354-de
```

Helm (`helm/anonreq/values-germany.yaml`) does not build this image. The in-cluster analyzer behind `ANONREQ_PRESIDIO_URL` must be this bilingual image, or `de-DE` name and address masking will not happen.

## Fail-closed

If detection, cache, or the analyzer is down — including a Presidio error when `language=de` is not loaded — AnonReq returns HTTP 5xx and **does not** forward the raw prompt.

## What this demo does not claim

- BSI C5
- ISO 27001
- Air-gap in four days (that is a later install bundle)
- Hosting 140 models — the customer brings the model key
