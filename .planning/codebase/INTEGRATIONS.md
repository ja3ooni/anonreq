# External Integrations

**Analysis Date:** 2026-07-17

## APIs & External Services

### LLM Provider APIs (Upstream)

| Provider | Protocol | Implementation | Auth Env Var |
|----------|----------|----------------|--------------|
| **OpenAI** | OpenAI-compatible Chat Completions | `src/anonreq/providers/openai.py` (`OpenAIAdapter`) | `ANONREQ_OPENAI_API_KEY` or `OPENAI_API_KEY` |
| **Anthropic** | Anthropic Messages API (translated from OpenAI schema) | `src/anonreq/providers/anthropic.py` (`AnthropicAdapter`) | `ANONREQ_ANTHROPIC_API_KEY` or `ANTHROPIC_API_KEY` |
| **Gemini** | Google Gemini API (translated from OpenAI schema) | `src/anonreq/providers/gemini.py` (`GeminiAdapter`) | `ANONREQ_GEMINI_API_KEY` or `GEMINI_API_KEY` |
| **Ollama** | Ollama Chat API (translated from OpenAI schema) | `src/anonreq/providers/ollama.py` (`OllamaAdapter`) | `ANONREQ_OLLAMA_API_KEY` or `OLLAMA_API_KEY` |

**Adapter architecture:** All providers are registered via `config/providers.yaml`, loaded by `ProviderRegistry` (`src/anonreq/providers/registry.py`). Each adapter translates from OpenAI-compatible input schema to provider-native format. Response normalization maps back to OpenAI-compatible chat completions. Adapters are pure schema translators — zero policy, detection, or caching logic. All `httpx.AsyncClient` instances across adapters and pipeline use `follow_redirects=False` (SSRF hardening, Phase 29).

**Provider capability config:** `config/providers.yaml` maps provider names to adapter class paths (e.g., `anonreq.providers.anthropic.AnthropicAdapter`). Capability flags (streaming, tool_calling, vision, etc.) resolved via `config/capabilities.yaml` and `CapabilityResolver`.

**Runtime secret store:** Provider API keys can be loaded from a `RuntimeSecretStore` (`src/anonreq/secrets/store.py`) at startup and hot-reloaded via file watcher (`src/anonreq/secrets/reloader.py`). `ProviderRegistry` accepts an optional `secret_store` parameter, falling back to the process-wide store via `get_runtime_secret_store()`.

## Data Storage

**Databases:**
- **PostgreSQL 16** — Audit log database (observability profile, `docker-compose.yml` service `postgres`)
  - Connection: `ANONREQ_DATABASE_URL` env var (default: `sqlite+aiosqlite:///./anonreq.db`)
  - Client: SQLAlchemy 2.0 async (`create_async_engine`) + `asyncpg` driver
  - Migrations: Alembic (`alembic.ini`, `alembic/`)
  - Alternative: SQLite with aiosqlite for development/testing
  - Prometheus metrics via `postgres-exporter` (observability profile)
  - Docker Compose now uses `${POSTGRES_USER:?err}` / `${POSTGRES_PASSWORD:?err}` — no hardcoded credentials

**File Storage:**
- **MinIO** — S3-compatible object storage for compliance archives (SEC 17a-4 MNPI audit retention) — optional extra `[storage]`
  - Client: `minio` Python SDK in `src/anonreq/storage/minio.py` (`MinioWormBucket`)
  - Bucket: `anonreq-mnpi-audit` with WORM (Write Once Read Many) mode
  - Retention: COMPLIANCE mode, 7-year retain-until-date (2557 days)
  - Only SHA-256 hashes stored, never raw PII/MNPI
  - Credentials: `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` env vars (Docker Compose, no defaults)
  - Endpoint: `minio:9000` (internal network)

**Caching:**
- **Valkey 8** (Redis-compatible) — Ephemeral token mapping store, TTL-based eviction
  - Client: `redis-py` (`redis.asyncio`), in `src/anonreq/cache/manager.py` (`CacheManager`)
  - Connection: `ANONREQ_VALKEY_URL` env var
  - **Topology support** (Phase 28): standalone (`redis://`), Sentinel (`redis+sentinel://`), Cluster (`redis+cluster://`)
  - Persistence disabled: `--save "" --appendonly no`
  - Key format: `anonreq:{tenant_id}:{session_id}` per D-13
  - TTL range: 60–3600 seconds (configurable via `ANONREQ_CACHE_TTL_SECONDS`)
  - Atomic HSET + EXPIRE via pipeline transactions
  - Health checks every 5s via `health_check_interval`
  - **Retry with tenacity** (Phase 28): exponential backoff with jitter, 30s stop delay, covers `ConnectionError`, `TimeoutError`, `ReadOnlyError`, `ClusterDownError`, `MasterDownError`; translates to `DependencyUnavailableError` on exhaustion
  - Prometheus metrics via `valkey-exporter` (observability profile)

## Authentication & Identity

**Auth Provider:**
- **Custom** (self-hosted, no external IdP) — Bearer token authentication
  - Implementation: `src/anonreq/dependencies.py` (`verify_api_key`, `auth_context`)
  - Scheme: HTTP Bearer via `fastapi.security.HTTPBearer(auto_error=True)`
  - Token validation: constant-time comparison (`hmac.compare_digest`) against `ANONREQ_API_KEY` env var (min 32 chars)
  - Admin endpoints: Separate `ANONREQ_ADMIN_API_KEY` env var
  - Auth applies to all protected routes via `Depends(auth_context)`
  - Health routes, chat routes, compliance routes, governance routes, admin routes — all auth-protected
  - PAC file endpoint is public (no auth)
  - `/metrics` is public (secured at network level)

**OIDC Support (Phase 29):**
- **OIDCVerifier** — Optional external IdP integration for admin identity tokens
  - Implementation: `src/anonreq/auth/oidc.py` (`OIDCVerifier`, `JWKSCache`)
  - Config: `ANONREQ_OIDC_ISSUER`, `ANONREQ_OIDC_AUDIENCE`, `ANONREQ_OIDC_JWKS_URL`, `ANONREQ_OIDC_ROLE_CLAIM`, `ANONREQ_OIDC_JWKS_CACHE_SECONDS`
  - JWKS: Cached public keys with configurable TTL (default 300s), async refresh with lock
  - Token verification: JWT signature validation via RSA public keys from JWKS endpoint
  - Role claim extraction for RBAC integration

**RBAC (Phase 29):**
- **Role hierarchy** with 4 levels: `ADMINISTRATOR` (4) > `SECURITY_OFFICER` (3) > `OPERATOR` (2) > `READ_ONLY_AUDITOR` (1)
  - Implementation: `src/anonreq/middleware/rbac.py` (`require_role()`)
  - Role normalization: legacy `read_only` maps to `read_only_auditor`
  - Used on admin routes, audit routes, compliance routes

**mTLS (Phase 29):**
- **IngressMTLSMiddleware** — Validates forwarded client certificates from trusted reverse proxies
  - Implementation: `src/anonreq/middleware/mtls.py`
  - Config: `ANONREQ_MTLS_ENFORCE`, `ANONREQ_MTLS_TRUSTED_PROXY_CIDRS`, `ANONREQ_MTLS_FORWARD_CERT_HEADER`
  - Certificate formats: PEM, DER, base64-encoded DER
  - Trusted proxy validation: CIDR allowlist matching against request client IP
  - Machine principal extraction from certificate subject/issuer/fingerprint

## Runtime Secret Management (Phase 29)

- **RuntimeSecretStore** — Thread-safe in-memory secret snapshot container
  - Implementation: `src/anonreq/secrets/store.py` (`RuntimeSecretStore`, `SecretSnapshot`)
  - Protocol-based source abstraction (`SecretSource`)
  - Request-scoped binding via ContextVar

- **SecretRotationBuffer** — Rotation support for long-lived streaming connections
  - Implementation: `src/anonreq/secrets/rotation.py`
  - Atomic rotation with previous snapshot retention
  - Per-session read-only views

- **VaultSecretSource** — HashiCorp Vault KV v2 backend
  - Implementation: `src/anonreq/secrets/bootstrap.py` (`VaultSecretSource`)
  - Config: `ANONREQ_SECRET_BACKEND=vault`, `ANONREQ_SECRET_BACKEND_PATH`
  - Requires `hvac` package (optional dependency)

- **SecretVolumeReloader** — Watchdog-based file watcher for mounted secret volumes
  - Implementation: `src/anonreq/secrets/reloader.py`
  - Config: `ANONREQ_SECRET_VOLUME_DIR`, `ANONREQ_SECRET_VOLUME_FILE`
  - YAML format with `provider_api_keys` mapping
  - Atomic snapshot replacement on file change

## License Validation (Phase 26)

- **HMAC-SHA256 commercial license** — Offline license key verification
  - Implementation: `src/anonreq/license/validator.py` (`LicenseValidator`)
  - Config: `ANONREQ_LICENSE_SECRET` (HMAC signing key), `ANONREQ_LICENSE_KEY` (base64-encoded signed payload)
  - Feature gating: `src/anonreq/license/models.py` (`FeatureGate`, `LicensePayload`)
  - Constant-time signature comparison
  - In-memory caching of validation status
  - Routes: `src/anonreq/license/router.py`

## PII Detection

- **Microsoft Presidio Analyzer** — PII/PHI detection sidecar service
  - Container: `mcr.microsoft.com/presidio-analyzer:latest` (Docker Compose)
  - Client: `src/anonreq/detection/presidio_client.py` (`PresidioClient`)
  - Connection: `ANONREQ_PRESIDIO_URL` env var (`http://presidio-analyzer:3000`)
  - Endpoint: `POST /analyze` per text node
  - Concurrency: Semaphore-limited `asyncio.gather()` (max 10 concurrent requests, configurable via `ANONREQ_PRESIDIO_MAX_CONCURRENCY`)
  - Timeout: 2 seconds per request (D-50), configurable via `ANONREQ_REQUEST_TIMEOUT_SECONDS`
  - Skip threshold: text nodes < 20 chars skip Presidio (D-34)
  - Default score threshold: 0.7 (D-37)
  - Locale-specific recognizer bundles via `config/locales/` and locale negotiation header `X-AnonReq-Locale`
  - All `httpx.AsyncClient` instances use `follow_redirects=False` (SSRF hardening)

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
  - Anonymous auth disabled (Phase 24 security fix)

**Logging:**
- **Structured JSON logging** via `structlog` + `python-json-logger`
  - Metadata-only audit, never raw PII values
  - Log levels configurable via `ANONREQ_LOG_LEVEL`
  - Request-scoped `request_id` bound via structlog contextvars
  - Config: `src/anonreq/logging_config.py`

## SIEM & SOC Integrations

**Config-driven SIEM sink framework** (`config/soc-sinks.yaml`, `src/anonreq/soc/`):

| Sink | Type | Protocol | Status | Details |
|------|------|----------|--------|---------|
| **Splunk HEC** | `splunk_hec` | HTTPS POST | Enabled | `src/anonreq/soc/sinks/splunk_hec.py` — HEC JSON envelopes, sourcetype `anonreq:ai_security` |
| **QRadar CEF** | `qradar_cef` | TCP syslog (port 514) | Enabled | `src/anonreq/soc/sinks/qradar_cef.py` — CEF:0\|AnonReq\| format |
| **Azure Sentinel** | `sentinel_dcr` | HTTPS (OAuth2) | Disabled | `src/anonreq/soc/sinks/sentinel_dcr.py` — DCR stream records via Azure AD `client_credentials` grant |
| **Elasticsearch** | `elastic_bulk` | HTTPS Bulk API | Disabled | `src/anonreq/soc/sinks/elastic_bulk.py` — NDJSON `/_bulk` API with ApiKey auth |
| **Datadog Logs** | `datadog_logs` | HTTPS | Disabled | `src/anonreq/soc/sinks/datadog_logs.py` — `https://http-intake.logs.{site}/api/v2/logs` |
| **Custom Webhook** | `webhook` | HTTPS (Jinja2 templated) | Disabled | `src/anonreq/soc/sinks/webhook.py` — Configurable method, URL, headers, Jinja2 payload |

**SOC event pipeline:**
- `SOCNormalizer` (`src/anonreq/soc/normalizer.py`) — MITRE ATT&CK mapping via `config/mitre-mapping.yaml`
- `MITREMapper` (`src/anonreq/soc/mitre.py`) — ATT&CK technique/ID resolution
- SOC event buffer (`src/anonreq/soc/buffer.py`) — Async event buffering
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

## Trust Center (Phase 24)

- **Public compliance portal** — External-facing trust status endpoint
  - Service: `src/anonreq/trust_center/service.py` (`TrustCenterService`)
  - Router: `src/anonreq/trust_center/router.py`
  - Config: `config/trust_center.yaml` (enabled, display name, supported frameworks)
  - Rate limiting: `TrustCenterRateLimiter` (`src/anonreq/trust_center/service.py`)
  - Schemas: `src/anonreq/trust_center/schemas.py` (`TrustStatus`, `TrustCompliance`, `TrustSecurity`, `TrustMetrics`)
  - Enabled by default (Phase 27 made it default)

## Audit & Chain of Custody

- **AuditChainService** (`src/anonreq/services/audit_chain.py`) — Immutable audit log with cryptographic chain anchoring
- **ChainAnchorService** (`src/anonreq/services/chain_anchor.py`) — Merkle-tree style anchoring
- **Signing key:** `ANONREQ_ANCHOR_SIGNING_KEY` env var
- **Retention:** 2557 days (7 years) per `config/audit.yaml`
- Database: PostgreSQL (async, via SQLAlchemy)
- **Admin Audit API** (Phase 29): `src/anonreq/api/v1/admin/audit.py` — `/v1/admin/audit/config-history` endpoint for querying/filtering/exporting config change audit trail, RBAC-protected (ADMINISTRATOR role)

## CI/CD & Deployment

**Hosting:**
- **Docker** — Multi-stage `Dockerfile`, `python:3.12-slim` base
  - Builder stage: installs deps with `pip install ".[all]"` (all optional extras)
  - Runtime stage: minimal image, non-root `anonreq` user (uid 1001)
  - HEALTHCHECK on port 8080, `--no-server-header` for security
  - Port: 8080 (container), EXPOSE 8080

**CI Pipeline:**
- **GitHub Actions** — 4 workflows in `.github/workflows/`:
  - `test.yml` — ruff lint, mypy type check, pytest with coverage, coverage summary (on PR/push to main)
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
- Docker secrets: All sensitive credentials use `${VAR:?err}` pattern (no hardcoded defaults)

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
- **LLM Provider API calls** — All outbound requests to upstream LLM APIs (OpenAI, Anthropic, Gemini, Ollama); all use `follow_redirects=False`
- **SIEM sinks** — Configurable outbound events to Splunk, QRadar, Azure Sentinel, Elastic, Datadog, custom webhook
- **Compliance archive** — WORM bucket writes to MinIO
- **PAC file** — Served at `GET /proxy.pac` (public, no auth)
- **JWKS fetch** — OIDC JWKS endpoint fetch for token verification (`httpx.AsyncClient` with timeout)

## AI-Specific Integrations

**Voice Pipeline:**
- **OpenAI Whisper** — Local STT via `openai-whisper` + `torch` (GPU/CPU detection); optional extra `[voice]`
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
  - `src/anonreq/agent/mcp_parser.py` — MCP protocol parser

**Agent-Tool Governance:**
- Tool use classification, approval workflows, result sanitization
  - `src/anonreq/agent/` — Agent tool governance framework
  - `src/anonreq/governance/` — AI governance, tool inspection, policy evaluation
  - `src/anonreq/governance/provider_inventory.py` — Provider inventory management
  - `src/anonreq/governance/model_inventory.py` — Model inventory management

**Fairness Evaluation:**
- ML-driven fairness monitoring for AI outputs (optional extra `[ml]`)
  - `src/anonreq/fairness/` — Dataset analysis, evaluation, monitoring

## Environment Configuration

**Required env vars (application fails to start without these):**
- `ANONREQ_API_KEY` — API authentication, min 32 chars
- `ANONREQ_VALKEY_URL` — Valkey/Redis connection (standalone, Sentinel, or Cluster)
- `ANONREQ_PRESIDIO_URL` — Presidio Analyzer URL

**Critical optional env vars:**
- `ANONREQ_ADMIN_API_KEY` — Separate key for admin endpoints
- `ANONREQ_DATABASE_URL` — Database URL (defaults to SQLite for dev)
- `ANONREQ_{PROVIDER}_API_KEY` — Per-provider LLM API keys (OpenAI, Anthropic, Gemini, Ollama)
- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` — MinIO credentials (required by Docker Compose)
- `ANONREQ_BREACH_WEBHOOK_URL` — SLO breach notification endpoint
- `ANONREQ_ANCHOR_SIGNING_KEY` — Audit chain signing key

**Security env vars (added in phases 28-30):**
- `ANONREQ_OIDC_ISSUER`, `ANONREQ_OIDC_AUDIENCE`, `ANONREQ_OIDC_JWKS_URL` — OIDC provider configuration
- `ANONREQ_MTLS_ENFORCE`, `ANONREQ_MTLS_TRUSTED_PROXY_CIDRS` — mTLS validation
- `ANONREQ_SECRET_BACKEND` (`vault`), `ANONREQ_SECRET_BACKEND_PATH` — Vault secret bootstrap
- `ANONREQ_SECRET_VOLUME_DIR`, `ANONREQ_SECRET_VOLUME_FILE` — File-based secret volume
- `VAULT_ADDR`, `VAULT_TOKEN` — Vault connection (when using Vault backend)
- `ANONREQ_LICENSE_SECRET`, `ANONREQ_LICENSE_KEY` — Commercial license

**Secrets location:**
- Environment variables (`ANONREQ_*` prefix), loaded via Pydantic Settings from `.env` file or process env
- Runtime secret store (`src/anonreq/secrets/store.py`) — in-memory with optional Vault bootstrap
- Secret volume directory (`ANONREQ_SECRET_VOLUME_DIR`) — YAML files watched by `watchdog`
- `config/soc-sinks.yaml` supports `$env:VAR_NAME` and `$file:/path/to/secret` reference patterns
- Docker Compose: `${VAR:?err}` pattern for required secrets, no hardcoded defaults

---

*Integration audit: 2026-07-17*
