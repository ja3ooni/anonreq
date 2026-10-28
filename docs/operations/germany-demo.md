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
| spaCy models | unpinned `en_core_web_lg` | **pinned** `en_core_web_lg==3.7.1` and `de_core_news_lg==3.7.0`, sha256 checked before install, canonical wheel filenames |
| Recognizer languages | `en` only (`AnalyzerEngine()` default) | `en` and `de` |
| Address patterns | none for German streets | `docker/presidio/german_recognizers.yaml` (street line and PLZ+city, score 0.85) |
| Process user | root | `presidio` (uid 10001) after the installs |
| Listen port | 3000 | 3000 (unchanged) |
| RAM | stock | budget at least 4 GB once both models are loaded |
| Healthcheck | `GET /health` | `POST /analyze` with `language=de`; must return a `PERSON` span. Start period 120s |

`X-AnonReq-Locale: de-DE` is sent as Presidio `language=de` only when `de` is in `ANONREQ_PRESIDIO_LANGUAGES`. The wheel download reads those build args from the environment and saves canonical `*.whl` names. DevOps must run the first real image build; it has not been built in this pull request. Publishing the image:

```bash
docker compose build presidio-analyzer
docker tag anonreq/presidio-analyzer:2.2.354-de <registry>/anonreq/presidio-analyzer:2.2.354-de
docker push <registry>/anonreq/presidio-analyzer:2.2.354-de
```

Helm (`helm/anonreq/values-germany.yaml`) does not build this image. The in-cluster analyzer behind `ANONREQ_PRESIDIO_URL` must be this bilingual image, or `de-DE` name and address masking will not happen.

## Presidio languages

`ANONREQ_PRESIDIO_LANGUAGES` is the allowlist of analyzer languages (default `en`). The demo Compose file sets `en,de` because this image loads both models. A negotiated locale whose language is **not** on the list (`fr-FR`, `es`, `ar`, and `de-DE` when `de` is not configured) is analyzed as English. Each such locale increments `anonreq_presidio_unsupported_locales_total{locale="..."}` and logs `detection.presidio_locale_not_configured`. Every negotiated locale is considered, not only the first.

At startup the gateway probes `/analyze` for every configured language, plus English. If a configured language is missing, the process refuses to serve.

## Fail-closed when `de` is configured but missing

If `de` is on the allowlist and the sidecar rejects it, the request is **not** retried with `language=en`. The English model misses German names and street addresses, so that fallback would forward PII. The gateway returns HTTP 503 and does not call the provider:

```json
{
  "error": {
    "message": "Presidio analyzer does not support language 'de'. Refusing to fall back to English.",
    "type": "presidio_unsupported_language",
    "code": "presidio_unsupported_language"
  }
}
```

The message names the language code only. It does not include the prompt.

How to tell the image is missing German:

- **Log:** stdout JSON event `detection.presidio_language_unsupported` at warning, with `presidio_language` set to `de` and `error_type` `presidio_unsupported_language`. `presidio_language` is on the log allowlist. Prompt text is not logged.
- **Metric:** `anonreq_fail_secure_events_total{failure_type="presidio_unsupported_language"}` increases by one per rejected request. A down analyzer (timeout, connection error, other HTTP failure) uses `failure_type="detection_error"` instead, and also does not forward.
- **Compose health:** the demo container runs `docker/presidio/healthcheck.py`, which POSTs `/analyze` with `language=de` and expects a `PERSON` span. `GET /health` alone does not prove the German model is loaded. A stock image stays unhealthy on this check.

Cache failures and other detection errors still return HTTP 5xx and do not forward the raw prompt.

## What this demo does not claim

- BSI C5
- ISO 27001
- Air-gap in four days (that is a later install bundle)
- Hosting 140 models — the customer brings the model key
