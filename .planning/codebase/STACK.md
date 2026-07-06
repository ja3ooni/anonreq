# Technology Stack

**Analysis Date:** 2026-07-06

## Languages

**Primary:**
- Python >=3.12 — All gateway and service code; required by `pyproject.toml` (`requires-python = ">=3.12"`)
- YAML — Configuration files for providers, policies, compliance presets, SLOs, SOC sinks, DLP rules, and locales (in `config/`)

**Secondary (Example Clients):**
- TypeScript (Node.js) — Example SDK clients in `examples/typescript/`
- Go (1.22) — Example SDK clients in `examples/go/`
- Shell (bash) — Quickstart scripts in `examples/quickstart/`, build scripts in `scripts/`

## Runtime

**Environment:**
- Python 3.12-slim (official Docker image, multi-stage build in `Dockerfile`)
- ASGI via Uvicorn, served as `anonreq.main:app`

**Package Manager:**
- pip (Python) — Lockfile at `requirements.txt` (pinned exact versions) and `requirements-dev.txt`
- uv — Lockfile at `uv.lock` present (modern fast resolver)
- Build system: `setuptools >=64.0` via `pyproject.toml`

## Frameworks

**Core:**
- **FastAPI** >=0.138.0 — Web framework, async request handling, dependency injection, OpenAPI generation. Application factory in `src/anonreq/main.py` (`create_app()`)
- **Uvicorn** >=0.49.0 — ASGI server, configured with `--no-server-header` for security (no version leak)
- **Pydantic v2** — Data validation via `pydantic.BaseModel` and `pydantic_settings.BaseSettings` for configuration
- **SQLAlchemy 2.0** — Async ORM (`create_async_engine`), used by `AuditChainService` and `ChainAnchorService`
- **Alembic** — Database migrations (`alembic.ini`, `alembic/` directory)

**Testing:**
- **pytest** >=9.0 — Test runner with asyncio_mode=auto, test discovery in `tests/`
- **pytest-asyncio** — Async fixture/test support
- **Hypothesis** >=6.155.0 — Property-based testing for round-trip correctness, token uniqueness, fail-secure invariants
- **respx** >=0.23.0 — HTTP request mocking for `httpx`
- **fakeredis** >=2.0 — In-memory Redis fake for cache tests (dev dependency in `pyproject.toml`)

**Build/Dev:**
- **setuptools** >=64.0 — Package build backend
- **cyclonedx-bom** — SBOM generation (CI, `scripts/sbom.sh`)
- **markdownlint-cli2** — Documentation linting (CI)
- **lychee** — Link checking (CI)
- **@mermaid-js/mermaid-cli** — Mermaid diagram validation (CI)

## Key Dependencies

**Critical:**
| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | >=0.138.0 | Web framework, routes, middleware |
| `uvicorn[standard]` | >=0.49.0 | ASGI server |
| `pydantic-settings` | >=2.14.2 | Env-based configuration with ANONREQ_ prefix |
| `redis` | >=8.0.0 | Valkey/Redis async client (`redis.asyncio`) for token mapping cache |
| `httpx` | >=0.28.1 | Async HTTP client to Presidio Analyzer, LLM provider APIs, webhooks |
| `structlog` | >=26.1.0 | Structured JSON logging |
| `presidio-analyzer` | >=2.2.35 | PII/PHI detection engine (Microsoft Presidio) |
| `sqlalchemy` | >=2.0.51 | Async ORM for audit database |
| `prometheus-client` | >=0.25.0 | `/metrics` endpoint, Prometheus counters/histograms |
| `cryptography` | >=42.0.0 | TLS interception CA management, chain anchoring |
| `pyyaml` | >=6.0.3 | YAML config file parsing (`yaml.safe_load`) |
| `jinja2` | >=3.1.0 | Template rendering (SIEM webhook payloads, breach notifications) |
| `minio` | >=7.2.0 | MinIO S3-compatible object storage client (WORM compliance) |
| `onnxruntime` | >=1.17.0 | ML model inference (jailbreak detection, fairness evaluation) |
| `openai-whisper` | >=20231117 | Local speech-to-text (voice pipeline) |
| `soundfile` | >=0.12.1 | Audio file I/O for voice pipeline |
| `pyarrow` | >=15.0.0 | Parquet/columnar format for ediscovery exports |
| `reportlab` | >=5.0.0 | PDF generation for compliance reports |

**Infrastructure:**
| Package | Version | Purpose |
|---------|---------|---------|
| `asyncpg` | 0.31.0 | Async PostgreSQL driver |
| `greenlet` | 3.5.3 | SQLAlchemy async support |
| `aiosqlite` | 0.22.1 | Async SQLite (dev/test, dev-dependency) |
| `watchdog` | >=4.0.0 | File system watcher for hot-reload of config files |

## Configuration

**Environment:**
- Pydantic Settings v2 with `ANONREQ_` prefix (`SettingsConfigDict(env_prefix="ANONREQ_")`)
- `.env` file auto-loaded (existence noted — never read contents)
- Required vars validated at import time: `API_KEY` (min 32 chars), `VALKEY_URL`, `PRESIDIO_URL`
- `extra="ignore"` for forward-compatibility

**Required env vars:**
- `ANONREQ_API_KEY` — Bearer token for API authentication (min 32 chars)
- `ANONREQ_VALKEY_URL` — Valkey/Redis connection string
- `ANONREQ_PRESIDIO_URL` — Presidio Analyzer HTTP endpoint

**Key optional env vars:**
- `ANONREQ_ADMIN_API_KEY`, `ANONREQ_ADMIN_ROLE` — Admin endpoint authentication
- `ANONREQ_DATABASE_URL` — Audit database (default: SQLite)
- `ANONREQ_MINIO_ACCESS_KEY`, `ANONREQ_MINIO_SECRET_KEY` — MinIO S3 credentials
- `ANONREQ_BREACH_WEBHOOK_URL` — SLO breach notification webhook
- `ANONREQ_ANCHOR_SIGNING_KEY` — Audit chain signing key
- `ANONREQ_LOG_LEVEL`, `ANONREQ_HOST`, `ANONREQ_PORT`
- `ANONREQ_PROXY_MODE` — proxy-only | transparent | full
- `ANONREQ_CA_DIR` — CA certificate directory
- `ANONREQ_START_NETWORK_PROXY` — Autostart network proxy listener
- `ANONREQ_{PROVIDER}_API_KEY` — Per-LLM-provider API keys (e.g., `ANONREQ_OPENAI_API_KEY`)

**Build:**
- `pyproject.toml` — Package metadata, dependencies, pytest/coverage config
- `requirements.txt` — Pinned production dependencies (from pip freeze)
- `requirements-dev.txt` — Development dependencies (includes production)
- `uv.lock` — uv lockfile

**Config files (YAML, all in `config/`):**
| File | Purpose |
|------|---------|
| `config/providers.yaml` | LLM provider adapter class mapping |
| `config/policy.yaml` | Policy engine rules, rate limits, spend budgets, CA cert config, proxy settings |
| `config/webhook.yaml` | SLO breach webhook configuration |
| `config/slo.yaml` | SLO targets (success rate, p95 latency, fail-secure rate, audit write rate) |
| `config/audit.yaml` | Audit retention and chain anchoring settings |
| `config/soc-sinks.yaml` | SIEM sink definitions (Splunk, QRadar, Sentinel, Elastic, Datadog, webhook) |
| `config/compliance/*.yaml` | Regional compliance presets (GDPR, LGPD, PDPA, PIPEDA, POPIA, Privacy Act) |
| Multiple other YAML files | Classification, DLP, MNPI recognizers, model aliases, prompt security rules, etc. |

## Platform Requirements

**Development:**
- Python >=3.12
- Docker Desktop or Docker Engine (for Presidio Analyzer and Valkey containers)
- `docker compose` (for `docker-compose.yml` orchestration)
- macOS endpoint visibility requires libpcap/Npcap (for `endpoint/macos/capture.py`)

**Production:**
- Docker Engine (Linux hosts recommended)
- Docker Compose for multi-service orchestration
- Deployment modes: reverse proxy, transparent proxy, virtual/physical appliance
- `systemd` unit provided at `systemd/anonreq-agent.service`

---

*Stack analysis: 2026-07-06*
