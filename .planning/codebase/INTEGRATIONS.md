# External Integrations

**Analysis Date:** 2026-07-06

## APIs & External Services

### LLM Provider APIs (Upstream)

| Provider | Protocol | Implementation | Auth Env Var |
|----------|----------|----------------|--------------|
| **OpenAI** | OpenAI-compatible Chat Completions | `src/anonreq/providers/openai.py` (`OpenAIAdapter`) | `ANONREQ_OPENAI_API_KEY` or `OPENAI_API_KEY` |
| **Anthropic** | Anthropic Messages API (translated from OpenAI schema) | `src/anonreq/providers/anthropic.py` (`AnthropicAdapter`) | `ANONREQ_ANTHROPIC_API_KEY` or `ANTHROPIC_API_KEY` |
| **Gemini** | Google Gemini API (translated from OpenAI schema) | `src/anonreq/providers/gemini.py` (`GeminiAdapter`) | `ANONREQ_GEMINI_API_KEY` or `GEMINI_API_KEY` |
| **Ollama** | Ollama Chat API (translated from OpenAI schema) | `src/anonreq/providers/ollama.py` (`OllamaAdapter`) | `ANONREQ_OLLAMA_API_KEY` or `OLLAMA_API_KEY` |

**Adapter architecture:** All providers are registered via `config/providers.yaml`, loaded by `ProviderRegistry` (`src/anonreq/providers/registry.py`). Each adapter translates from OpenAI-compatible input schema to provider-native format. Response normalization maps back to OpenAI-compatible chat completions. Adapters are pure schema translators — zero policy, detection, or caching logic. API keys resolved at call time by `resolve_api_key()` using `ANONREQ_{PROVIDER}_API_KEY` → `{PROVIDER}_API_KEY` fallback chain.

**Provider capability config:** `config/providers.yaml` maps provider names to adapter class paths (e.g., `anonreq.providers.anthropic.AnthropicAdapter`). Capability flags (streaming, tool_calling, vision, etc.) resolved via `config/capabilities.yaml` and `CapabilityResolver`.

## Data Storage

**Databases:**
- **PostgreSQL 16** — Audit log database (observability profile, `docker-compose.yml` service `postgres`)
  - Connection: `ANONREQ_DATABASE_URL` env var (default: `sqlite+aiosqlite:////app/anonreq.db`)
  - Client: SQLAlchemy 2.0 async (`create_async_engine`) + `asyncpg` driver
  - Migrations: Alembic (`alembic.ini`, `alembic/`)
  - Alternative: SQLite with aiosqlite for development/testing
  - Prometheus metrics via `postgres-exporter` (observability profile)

**File Storage:**
- **MinIO** — S3-compatible object storage for compliance archives (SEC 17a-4 MNPI audit retention)
  - Client: `minio` Python SDK in `src/anonreq/storage/minio.py` (`MinioWormBucket`)
  - Bucket: `anonreq-mnpi-audit` with WORM (Write Once Read Many) mode
  - Retention: COMPLIANCE mode, 7-year retain-until-date (2557 days)
  - Only SHA-256 hashes stored, never raw PII/MNPI
  - Credentials: `ANONREQ_MINIO_ACCESS_KEY`, `ANONREQ_MINIO_SECRET_KEY` env vars
  - Endpoint: `minio:9000` (internal network)

**Caching:**
- **Valkey 8** (Redis-compatible) — Ephemeral token mapping store, TTL-based eviction
  - Client: `redis-py` (`redis.asyncio`), in `src/anonreq/cache/manager.py` (`CacheManager`)
  - Connection: `ANONREQ_VALKEY_URL` env var (`redis://valkey:6379/0`)
  - Persistence disabled: `--save "" --appendonly no`
  - Key format: `anonreq:{tenant_id}:{session_id}` per D-13
  - TTL range: 60–3600 seconds (configurable via `ANONREQ_CACHE_TTL_SECONDS`)
  - Atomic HSET + EXPIRE via pipeline transactions
  - Health checks every 5s via `health_check_interval`
  - Prometheus metrics via `valkey-exporter` (observability profile)

## Authentication & Identity

**Auth Provider:**
- **Custom** (self-hosted, no external IdP) — Bearer token authentication
  - Implementation: `src/anonreq/dependencies.py` (`verify_api_key`, `auth_context`)
  - Scheme: HTTP Bearer via `fastapi.security.HTTPBearer(auto_error=True)`
  - Token validation: constant-time comparison against `ANONREQ_API_KEY` env var (min 32 chars)
  - Admin endpoints: Separate `ANONREQ_ADMIN_API_KEY` env var
  - Auth applies to all protected routes via `Depends(auth_context)`
  - Health routes, chat routes, compliance routes, governance routes, admin routes — all auth-protected
  - PAC file endpoint is public (no auth)
  - `/metrics` is public (secured at network level)

## PII Detection

- **Microsoft Presidio Analyzer** — PII/PHI detection sidecar service
  - Container: `mcr.microsoft.com/presidio-analyzer:latest` (Docker Compose)
  - Client: `src/anonreq/detection/presidio_client.py` (`PresidioClient`)
  - Connection: `ANONREQ_PRESIDIO_URL` env var (`http://presidio-analyzer:5001`)
  - Endpoint: `POST /analyze` per text node
  - Concurrency: Semaphore-limited `asyncio.gather()` (max 10 concurrent requests)
  - Timeout: 2 seconds per request (D-50), configurable via `ANONREQ_REQUEST_TIMEOUT_SECONDS`
  - Skip threshold: text nodes < 20 chars skip Presidio (D-34)
  - Default score threshold: 0.7 (D-37)
  - Locale-specific recognizer bundles via `config/locales/` and locale negotiation header `X-AnonReq-Locale`

## Monitoring & Observability

**Metrics:**
- **Prometheus** — Metrics collection and alerting engine
  - Client: `prometheus-client` Python library
  - Endpoint: `GET /metrics` (OpenMetrics text format)
  - Key metrics: request counts, latency histograms, DLP violations, exfiltration detections, SIEM sink counters
  - Prometheus server: `prom/prometheus:v2.53.0` (observability profile)
  - Scrape targets: anonreq gateway, postgres-exporter, valkey-exporter
  - Alert rules: `docker/prometheus/rules/slo_alerts.yml`
  - Retention: 30 days (`--storage.tsdb.retention.time=30d`)

**Dashboards:**
- **Grafana** — Visualization dashboards
  - Version: `grafana/grafana:11.0.0`
  - Provisioned datasources: Prometheus (`docker/grafana/datasources/prometheus.yml`)
  - Provisioned dashboards: SLO dashboard, Audit dashboard (`docker/grafana/dashboards/`)
  - Anonymous auth enabled (Viewer role)

**Logging:**
- **Structured JSON logging** via `structlog` + `python-json-logger`
  - Metadata-only audit, never raw PII values
  - Log levels configurable via `ANONREQ_LOG_LEVEL`
  - Request-scoped `request_id` bound via structlog contextvars

## SIEM & SOC Integrations

**Config-driven SIEM sink framework** (`config/soc-sinks.yaml`, `src/anonreq/soc/`):

| Sink | Type | Protocol | Status | Details |
|------|------|----------|--------|---------|
| **Splunk HEC** | `splunk_hec` | HTTPS POST | Enabled | `src/anonreq/soc/sinks/splunk_hec.py` — HEC JSON envelopes, sourcetype `anonreq:ai_security` |
| **QRadar CEF** | `qradar_cef` | TCP syslog (port 514) | Enabled | `src/anonreq/soc/sinks/qradar_cef.py` — CEF:0|AnonReq| format |
| **Azure Sentinel** | `sentinel_dcr` | HTTPS (OAuth2) | Disabled | `src/anonreq/soc/sinks/sentinel_dcr.py` — DCR stream records via Azure AD `client_credentials` grant |
| **Elasticsearch** | `elastic_bulk` | HTTPS Bulk API | Disabled | `src/anonreq/soc/sinks/elastic_bulk.py` — NDJSON `/_bulk` API with ApiKey auth |
| **Datadog Logs** | `datadog_logs` | HTTPS | Disabled | `src/anonreq/soc/sinks/datadog_logs.py` — `https://http-intake.logs.{site}/api/v2/logs` |
| **Custom Webhook** | `webhook` | HTTPS (Jinja2 templated) | Disabled | `src/anonreq/soc/sinks/webhook.py` — Configurable method, URL, headers, Jinja2 payload |

**SOC event pipeline:**
- `SOCNormalizer` (`src/anonreq/soc/normalizer.py`) — MITRE ATT&CK mapping via `config/mitre-mapping.yaml`
- `MITREMapper` (`src/anonreq/soc/mitre.py`) — ATT&CK technique/ID resolution
- Health monitoring: per-sink health checks with periodic monitoring
- Config: `config/soc-sinks.yaml`, `config/mitre-mapping.yaml`, `config/mitre_atlas.yaml`, `config/mitre_attack.yaml`

## SLO Breach Notifications

- **Webhook** — Configurable SLO breach notification
  - URL: `ANONREQ_BREACH_WEBHOOK_URL` env var
  - Retry: exponential backoff (base 2s), max 3 retries, 10s timeout
  - DLQ: max 1000 entries
  - Implementation: `src/anonreq/breach/notifications.py`, config: `config/webhook.yaml`
  - Templates: `src/anonreq/breach/templates.py` (Jinja2-rendered)

## Compliance Presets

**Regional compliance configurations** in `config/compliance/`:
- GDPR (Europe)
- LGPD (Brazil)
- PDPA (Singapore/Thailand)
- PIPEDA (Canada)
- POPIA (South Africa)
- Privacy Act (Australia/New Zealand)

Loaded by `PresetEngine` (`src/anonreq/compliance/engine.py`). Active presets configured via `ANONREQ_ACTIVE_PRESETS` env var (comma-separated).

## Audit & Chain of Custody

- **AuditChainService** (`src/anonreq/services/audit_chain.py`) — Immutable audit log with cryptographic chain anchoring
- **ChainAnchorService** (`src/anonreq/services/chain_anchor.py`) — Merkle-tree style anchoring
- **Signing key:** `ANONREQ_ANCHOR_SIGNING_KEY` env var
- **Retention:** 2557 days (7 years) per `config/audit.yaml`
- Database: PostgreSQL (async, via SQLAlchemy)

## CI/CD & Deployment

**Hosting:**
- **Docker** — Multi-stage `Dockerfile`, `python:3.12-slim` base
  - Builder stage: installs deps, builds package
  - Runtime stage: minimal image, non-root `anonreq` user (uid 1001)
  - HEALTHCHECK on port 8080, `--no-server-header` for security
  - Port: 8080 (container), EXPOSE 8080

**CI Pipeline:**
- **GitHub Actions** — 3 workflows in `.github/workflows/`:
  - `docs-ci.yml` — Markdown lint, link check, Mermaid validation, OpenAPI sync check (on PR/push to main)
  - `docs-nightly.yml` — Scheduled doc rebuild
  - `release.yml` — SBOM generation (CycloneDX + Syft), Cosign attestation, artifact attachment (on release publish)

**Container Registry:**
- GitHub Container Registry (implied by `release.yml` workflow)
- Image labels: `org.opencontainers.image.source`, `version`, `description`

**Orchestration:**
- `docker-compose.yml` — Core services (anonreq, valkey, presidio-analyzer) on isolated `anonreq-net` bridge network
- Observability profile (`--profile observability`): adds postgres, postgres-exporter, minio, prometheus, grafana, valkey-exporter
- All services use `restart: unless-stopped`

**System Deployment:**
- `systemd` unit at `systemd/anonreq-agent.service` for agent/endpoint visibility mode
- Appliance deployment modes: reverse proxy, transparent proxy, virtual, physical (in `src/anonreq/appliance/`, `src/anonreq/deployment/`)

## Webhooks & Callbacks

**Incoming:**
- **SLO Breach Callback** — Configurable webhook target for SLO breaches
  - Endpoint target: configured via `ANONREQ_BREACH_WEBHOOK_URL`
  - Event type header: `X-AnonReq-Event-Type: slo_breach`
  - Payload: `application/json`

**Outgoing:**
- **LLM Provider API calls** — All outbound requests to upstream LLM APIs (OpenAI, Anthropic, Gemini, Ollama)
- **SIEM sinks** — Configurable outbound events to Splunk, QRadar, Azure Sentinel, Elastic, Datadog, custom webhook
- **Compliance archive** — WORM bucket writes to MinIO
- **PAC file** — Served at `GET /proxy.pac` (public, no auth)

## AI-Specific Integrations

**Voice Pipeline:**
- **OpenAI Whisper** — Local STT via `openai-whisper` + `torch` (GPU/CPU detection)
  - `src/anonreq/voice/stt_engine.py`, `src/anonreq/voice/stt.py`
  - `src/anonreq/voice/connectors.py` — Voice provider connectors
  - Telephony integration support via `src/anonreq/voice/`

**RAG Pipeline:**
- **Vector store connectors** — Abstract interface with backends: Pinecone, Weaviate, Chroma, PGVector
  - `src/anonreq/rag/vector_connector.py` — `VectorStoreConnector` ABC
  - Ingest, detection, restoration, policy enforcement pipelines in `src/anonreq/rag/`

**MCP (Model Context Protocol):**
- **MCP Inspector** — Protocol detection and inspection for AI agent tool calls
  - `src/anonreq/mcp/inspector.py`, `src/anonreq/mcp/parser.py`

**Agent-Tool Governance:**
- Tool use classification, approval workflows, result sanitization
  - `src/anonreq/agent/` — Agent tool governance framework
  - `src/anonreq/governance/` — AI governance, tool inspection, policy evaluation

**Fairness Evaluation:**
- ML-driven fairness monitoring for AI outputs
  - `src/anonreq/fairness/` — Dataset analysis, evaluation, monitoring

## Environment Configuration

**Required env vars (application fails to start without these):**
- `ANONREQ_API_KEY` — API authentication, min 32 chars
- `ANONREQ_VALKEY_URL` — Valkey/Redis connection
- `ANONREQ_PRESIDIO_URL` — Presidio Analyzer URL

**Critical optional env vars:**
- `ANONREQ_ADMIN_API_KEY` — Separate key for admin endpoints
- `ANONREQ_DATABASE_URL` — Database URL (defaults to SQLite for dev)
- `ANONREQ_{PROVIDER}_API_KEY` — Per-provider LLM API keys (OpenAI, Anthropic, Gemini, Ollama)
- `ANONREQ_MINIO_ACCESS_KEY`, `ANONREQ_MINIO_SECRET_KEY` — MinIO credentials
- `ANONREQ_BREACH_WEBHOOK_URL` — SLO breach notification endpoint
- `ANONREQ_ANCHOR_SIGNING_KEY` — Audit chain signing key

**Secrets location:**
- Environment variables (`ANONREQ_*` prefix), loaded via Pydantic Settings from `.env` file or process env
- `config/soc-sinks.yaml` supports `$env:VAR_NAME` and `$file:/path/to/secret` reference patterns
- Docker Compose environment variables: `ANONREQ_API_KEY: ${ANONREQ_API_KEY:?err}` (required) and others with defaults

---

*Integration audit: 2026-07-06*
