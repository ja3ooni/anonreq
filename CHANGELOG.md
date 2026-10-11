# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Database-backed tenant registry shared by all replicas, with a short per-replica cache (`ANONREQ_TENANT_CACHE_TTL_SECONDS`). Startup fails if the `tenant` table is missing.
- Tenant admin API: `GET/PUT /v1/admin/tenants[/{id}]`, `POST .../disable`, `POST .../enable`. Authenticated with the admin credential only.
- Per-tenant enforcement of `allowed_models` and `allowed_providers`.
- `docs/en/multi-tenant.md`.
- `ANONREQ_API_KEY_PREVIOUS`: a second accepted chat key so the key can be rotated without failed requests.

### Fixed

- Documentation and Helm chart used port 8000 and env var names that do not exist (`ANONREQ_CACHE_URL`, `PRESIDIO_ANALYZER_URL`, `ANONREQ_COMPLIANCE_PRESET`, `ANONREQ_LOCALE`, `ANONREQ_CONFIDENCE_THRESHOLD`, `ANONREQ_CACHE_PASSWORD`). The gateway listens on 8080 and uses `ANONREQ_VALKEY_URL`, `ANONREQ_PRESIDIO_URL`, `ANONREQ_ACTIVE_PRESETS`.
- Helm liveness and readiness probes called `/health` and `/ready` without the bearer key (and `/ready` does not exist); they now run the same authenticated check as the Dockerfile.
- `greenlet` was not declared, so async SQLAlchemy failed on Apple Silicon. Declared via `sqlalchemy[asyncio]`.

### Known gaps

- `spend_limits`, `rate_limits`, and `kms_key_arn` on a tenant are stored but not enforced.
- Compliance presets are deployment-wide, not per tenant.
- The policy, provider, usage, incident, and compliance admin routers in `admin/router.py` are not mounted by `create_app`.
- Six tests in `tests/policy/test_integration.py` and `tests/unit/middleware/test_policy.py` fail on a clean checkout.

## [0.1.0] - 2026-06-19

### Added

- Docker Compose setup with anonreq, presidio-analyzer, and valkey containers
- Static bearer token authentication with key length validation
- Fail-secure global exception handler returning static HTTP 500
- Structured JSON audit logging with field allowlist
- Pre-flight health checks for Valkey and Presilio dependencies
- PII detection pipeline (regex + NER via Microsoft Presidio Analyzer)
- Tokenization engine with deduplication and reverse-offset replacement
- Restoration engine with case-insensitive, bracket-optional matching
- Cache Manager with Valkey (ephemeral, TTL-based, DEL post-response)
- SSE streaming with Tail_Buffer FSM for split-token handling
- Multi-provider support for Anthropic Claude, Google Gemini, and Ollama
- Model alias routing and GET /v1/models endpoint
- Multi-locale detection with 8 locales and locale-specific recognizer bundles
- Checksum validation for national IDs (Steuer-ID, BSN, NIR, CPF, CNPJ, Codice Fiscale)
- 6 compliance presets (GDPR, LGPD, PDPA, POPIA, Privacy Act AU, PIPEDA)
- Prometheus metrics endpoint with request counts, detection latency, entity counters
- Post-restoration residual token verification scan
- Custom detection rules API with hot-reload
- Property-based test suite (fail-secure, no-PII-in-logs, cross-request randomization, locale checksum)
- Classification engine (4 tiers: Block, Route Local, Anonymize, Pass) with YAML rules

### Security

- Fail-secure architecture: ForwardingGuard requires signed SanitizedEnvelope before upstream calls
- No-PII-in-logs enforcement via structlog field allowlist
- Ephemeral cache: Valkey with `save ""`, no RDB/AOF
- Cross-session token randomization with P(duplicate) ≤ 2⁻³²

## [0.1.1] - 2026-06-20

### Added

- Developer documentation (EN and DE)
- Executable quickstart scripts for gateway startup, anonymization test, and cleanup
- SDK examples for curl, Python, TypeScript, and Go (4 use cases each)
- Apache 2.0 LICENSE file
- NOTICE file with third-party attribution notices
- SECURITY.md with vulnerability disclosure policy
- Comprehensive README.md with 13 sections
- Documentation CI pipeline (markdown lint, link check, Mermaid validation, OpenAPI sync)
