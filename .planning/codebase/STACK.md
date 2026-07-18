# Technology Stack

**Analysis Date:** 2026-07-18

## Languages

**Primary:**
- Python 3.12 — entire application (`src/anonreq/`), configuration, tests

**Secondary:**
- YAML — configuration files (`config/*.yaml`, `config/locales/*.yaml`)
- JavaScript — PAC file generation (`src/anonreq/proxy/pac.py` generates PAC JS)

## Runtime

**Environment:**
- Python 3.12 (strict: `requires-python = ">=3.12"`)
- ASGI event loop via uvicorn

**Package Manager:**
- uv (recommended per AGENTS.md), pip (Dockerfile uses pip)
- Lockfile: not present (no `requirements.txt` lock committed; `requirements.txt` is generated for Docker)

## Frameworks

**Core:**
- FastAPI >=0.138.0 — main web framework, ASGI app at `src/anonreq/main.py`
- Uvicorn[standard] >=0.49.0 — ASGI server (`uvicorn anonreq.main:app --host 0.0.0.0 --port 8080`)

**Testing:**
- pytest >=9.0 — test runner (`tests/`)
- pytest-asyncio >=1.4.0 — async test support (`asyncio_mode = "auto"` in `pyproject.toml`)
- Hypothesis >=6.155.0 — property-based testing
- respx >=0.21.0 — httpx mock library for provider adapter tests
- fakeredis >=2.0 — in-memory Redis mock for cache tests

**Build/Dev:**
- setuptools >=64.0 — build backend (`pyproject.toml`)
- ruff >=0.9.0 — linter/formatter (`target-version = "py312"`, `line-length = 100`)
- mypy >=1.15.0 — strict type checking with pydantic and sqlalchemy plugins

## Key Dependencies

**Critical:**
- `fastapi>=0.138.0` — gateway HTTP framework
- `pydantic-settings>=2.14.2` — env-var configuration loading
- `httpx>=0.28.1` — async HTTP client for provider APIs, Presidio, SOC sinks, OIDC JWKS
- `redis>=8.0.0` — async Redis/Valkey client for token mapping cache
- `structlog>=26.1.0` — structured logging with field allowlist
- `prometheus-client>=0.25.0` — Prometheus metrics exposition
- `sqlalchemy>=2.0.0` — ORM for governance/audit persistence
- `cryptography>=42.0.0` — TLS cert generation, HMAC signing, JWT verification

**Infrastructure:**
- `asyncpg>=0.31.0` — async PostgreSQL driver for governance DB
- `aiosqlite>=0.20.0` — async SQLite driver (default fallback database)
- `pyyaml>=6.0.3` — YAML config loading (safe_load only)
- `tenacity>=9.1.4` — retry logic with exponential backoff for cache operations
- `watchdog>=4.0.0` — filesystem watcher for CA cert hot-reload and secret volume monitoring
- `jinja2>=3.1.0` — template rendering (breach notifications, exports)
- `python-json-logger>=4.1.0` — JSON log formatting
- `h11>=0.16.0` — low-level HTTP protocol handling (proxy)
- `soundfile>=0.12.1` — audio file I/O for voice pipeline

**Optional (extras):**
- `minio>=7.2.0` (`[storage]`) — S3-compatible object storage for compliance archives
- `pyarrow>=15.0.0` (`[exports]`) — Parquet/Arrow export
- `reportlab>=4.3.0,<5.0.0` (`[exports]`) — PDF compliance report generation
- `onnxruntime>=1.17.0` (`[ml]`) — ML inference runtime
- `openai-whisper>=20231117` (`[voice]`) — local speech-to-text
- `presidio-analyzer>=2.2.35` — PII/PHI detection (local Python recognizer support)

## Configuration

**Environment:**
- Pydantic Settings v2 via `src/anonreq/config/__init__.py`
- All env vars prefixed with `ANONREQ_` (`model_config = SettingsConfigDict(env_prefix="ANONREQ_")`)
- Module-level `settings = Settings()` singleton — validates at import time (fail-secure)
- Required vars: `ANONREQ_API_KEY` (min 32 chars), `ANONREQ_VALKEY_URL`, `ANONREQ_PRESIDIO_URL`
- Optional vars with defaults: `PROVIDER_BASE_URL`, `DATABASE_URL`, `CACHE_TTL_SECONDS`, `PROXY_MODE`, etc.

**Key env vars (non-secret):**
- `ANONREQ_API_KEY` — gateway auth key
- `ANONREQ_VALKEY_URL` — cache connection (supports standalone, sentinel, cluster)
- `ANONREQ_PRESIDIO_URL` — Presidio analyzer sidecar
- `ANONREQ_DATABASE_URL` — SQLAlchemy async DB URL (default: `sqlite+aiosqlite:///./anonreq.db`)
- `ANONREQ_POLICY_CONFIG_PATH` — enterprise policy YAML path
- `ANONREQ_PROXY_MODE` — proxy-only | transparent | full
- `ANONREQ_SECRET_BACKEND` — vault | volume | file
- `ANONREQ_CA_DIR` — CA cert directory for TLS interception
- `ANONREQ_LOG_LEVEL` — logging level (default: INFO)
- `ANONREQ_LICENSE_KEY` / `ANONREQ_LICENSE_SECRET` — appliance licensing

**YAML Configuration:**
- `config/providers.yaml` — provider adapter registry (maps provider name → adapter class path)
- `config/enterprise-policy.yaml` — PDP/PEP policy rules
- `config/soc-sinks.yaml` — SIEM sink definitions with `$env:` and `$file:` secret resolution
- `config/slo.yaml` — SLO targets and window configuration
- `config/classification.yaml` — classification levels and rules
- `config/dlp.yaml` — DLP detection patterns
- `config/compliance/*.yaml` — compliance presets (GDPR, CCPA, HIPAA, etc.)
- `config/locales/*.yaml` — multi-locale entity type bundles
- `config/model_aliases.yaml` — model alias mappings
- `config/capabilities.yaml` — provider capability flags
- `config/prompt-security-rules.yaml` — prompt injection/abuse rules
- `config/mitre_mapping.yaml` / `config/mitre_attack.yaml` / `config/mitre_atlas.yaml` — MITRE technique IDs

**Build:**
- `pyproject.toml` — package metadata, dependencies, tool configs (ruff, mypy, pytest, coverage)
- `Dockerfile` — multi-stage build (builder → runtime)
- `docker-compose.yml` — local deployment with core + observability profiles

## Observability

**Structured Logging:**
- `structlog` with strict field allowlist (`src/anonreq/logging_config.py`)
- `ALLOWLIST` frozenset drops non-allowlisted fields before serialization
- Secret redaction processor (`redact_secret_substrings_processor`) scrubs `sk-*`, `Bearer *`, `api_key=*` patterns
- JSON renderer to stderr via `structlog.processors.JSONRenderer()`

**Metrics:**
- `prometheus-client>=0.25.0` — Counter, Gauge, Histogram definitions in `src/anonreq/monitoring/metrics.py`
- Metrics endpoint: `GET /metrics` (no auth — network-level security)
- Core metrics: `requests_total`, `detection_latency`, `entities_detected`, `unrestored_tokens`, `fail_secure_events`, `audit_failures`, `processing_overhead`, `active_config_version`
- Proxy metrics: `proxy_connections_active`, `proxy_pinning_blocks`
- DLP metrics: `dlp_violations_total`, `dlp_exfiltration_total`, `dlp_actions_total`
- SOC metrics: `soc_events_normalized_total`, `soc_strip_failures_total`, per-sink counters

**SLO Engine:**
- `src/anonreq/services/slo_engine.py` — tracks success_rate, p95_latency_ms, fail_secure_rate, audit_write_rate
- Redis-backed counters with daily/monthly fixed windows and 24h/30d rolling windows
- Configuration loaded from `config/slo.yaml`

## Build & Packaging

**Docker:**
- Multi-stage Dockerfile (`Dockerfile`):
  - Stage 1 (builder): `python:3.12-slim`, installs build deps, pip installs `.[all]`
  - Stage 2 (runtime): `python:3.12-slim`, copies packages, creates `anonreq` user (uid 1001)
  - HEALTHCHECK on port 8080 with `python -c urllib.request` (no curl in slim image)
  - `--no-server-header` flag on uvicorn (prevents version leak)
- `docker-compose.yml` services:
  - Core: `valkey` (Valkey 8, no persistence), `presidio-analyzer` (Microsoft image), `anonreq` (built from Dockerfile)
  - Observability profile: `postgres` (16-alpine), `postgres-exporter`, `minio`, `prometheus` (v2.53.0), `grafana` (11.0.0), `valkey-exporter`
  - Isolated bridge network: `anonreq-net`

**Package:**
- `setuptools` build backend, `src/` layout (`[tool.setuptools.packages.find] where = ["src"]`)
- Optional dependency groups: `storage`, `exports`, `ml`, `voice`, `all`, `dev`

## Platform Requirements

**Development:**
- Python >=3.12
- uv or pip for dependency installation
- Valkey/Redis instance for cache
- Presidio Analyzer sidecar for PII detection

**Production:**
- Docker with docker-compose (core profile minimum)
- Valkey/Redis (standalone, sentinel, or cluster)
- Presidio Analyzer container
- Optional: PostgreSQL, MinIO, Prometheus, Grafana (observability profile)

---

*Stack analysis: 2026-07-18*
