# AGENTS.md

## Project status

Implementation in progress / alpha, not greenfield.

The repository now contains a substantial AnonReq implementation: a Python 3.12 FastAPI package
under `src/anonreq`, Docker/Compose deployment artifacts, YAML configuration, Alembic migrations,
OpenAPI docs, examples, operational docs, and a broad pytest/Hypothesis test suite.

Planning state as of 2026-07-06 indicates the v1.0 milestone implementation phases are complete
through Phase 21 (plus the 6.5 production-readiness checkpoint). Some `.planning/STATE.md` body
text is stale/conflicting; prefer concrete source files, phase summaries, and tests over stale
status prose.

## Source of truth

- `req/requirements.md` — core requirements (Req 1-21)
- `req/requirements_v2.md` — enterprise/Appliance requirements (Req 22-56)
- `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/phases/**` — implementation planning,
  decisions, phase summaries, and current milestone context
- `.planning/codebase/*.md` — mapped codebase structure, conventions, stack, testing, risks
- `AnonReq_Requirements_v1.0.docx` — original requirements source; use if `.md` requirements
  appear stale or contradictory

Read both requirements `.md` files before making architectural decisions. For implementation
details, inspect the actual code and tests before relying on planning docs.

## What this project builds

AnonReq: self-hosted AI security and anonymization gateway for regulated enterprises. It sits
between enterprise apps and external or local LLM APIs, detects/replaces sensitive data with
tokens, forwards sanitized requests, restores tokens in responses, and extends into Appliance-tier
AI traffic governance, DLP, prompt security, agent/tool governance, SOC/SIEM integration, endpoint
visibility, and sovereign control.

Core principle: raw PII must never cross the network boundary.

## Current implementation map

- **Gateway/API** — FastAPI app in `src/anonreq/main.py`; OpenAI-compatible chat routing,
  health/readiness, metrics, admin, governance, compliance, oversight, and SOC routes.
- **Pipeline** — staged orchestration in `src/anonreq/pipeline/` for classification, extraction,
  detection, tokenization, provider forwarding, restoration, cleanup, and forwarding guards.
- **Detection Engine** — `src/anonreq/detection/` combines regex/checksum recognizers,
  Presidio client integration, exclusion lists, span arbitration, locale bundles, MNPI, and
  context boosting.
- **Tokenization/Restoration** — `src/anonreq/tokenization/`, `src/anonreq/restore/`, and
  `src/anonreq/streaming/` implement `[TYPE_N]` tokens, deduplication, randomized sessions,
  case-insensitive/bracket-optional restoration, and SSE tail-buffer handling.
- **Cache Manager** — `src/anonreq/cache/` wraps Redis/Valkey for session-scoped ephemeral
  mappings and health checks.
- **Provider Adapters** — `src/anonreq/providers/` and `src/anonreq/routing/` support model
  aliases and OpenAI/Anthropic/Gemini/Ollama-style translation.
- **Policy/Governance** — `src/anonreq/policy/`, `src/anonreq/governance/`, `src/anonreq/admin/`,
  and related services cover PDP/PEP, RBAC, rate/spend controls, provider/model inventory,
  approvals, audit history, supplier risk, oversight, and compliance reports.
- **Enterprise Controls** — implemented domains include multimodal scanning, AI firewall, DLP,
  exfiltration detection, classification, DSAR, breach, retention/legal hold, lineage,
  eDiscovery, fairness monitoring, CASB, RAG governance, SOC/SIEM sinks, proxy/TLS/MITM/PAC,
  endpoint agent, voice sanitization, and deployment modes.
- **Observability/Ops** — Prometheus metrics, SLO engine, audit chain/export, structured logging,
  Docker Compose, Grafana/Prometheus config, runbooks, SBOM/security scripts, and OpenAPI output.

## Key files and directories

- `src/anonreq/` — application package
- `tests/` — pytest suite, including unit, integration, property, policy, firewall, multimodal,
  endpoint, RAG, CASB, discovery, admin, load, and restore tests
- `config/` — YAML configuration for policies, providers, locales, compliance presets, DLP,
  SOC sinks, fairness, audit, SLOs, model aliases, and prompt-security rules
- `docker-compose.yml`, `Dockerfile`, `docker/` — local deployment and observability stack
- `alembic/` — database migrations for governance/audit persistence
- `docs/` — installation, deployment, API, compliance, security, architecture, and ops docs
- `examples/` — curl, Python, TypeScript, and Go quickstarts
- `openapi/openapi.yaml` — generated API specification

## Key constraints to preserve

- **Fail-secure/fail-closed**: any ambiguity, component failure, policy uncertainty, detection
  failure, cache failure, timeout, TLS/proxy failure, or unsupported content path must block
  forwarding and return an error.
- **No PII in logs or telemetry**: audit/log/SOC/metrics/events are metadata-only with allowlisted
  fields. Do not emit raw request bodies, raw detected values, raw tool results, or raw encoded
  exfiltration content.
- **Ephemeral sensitive mappings**: token mappings are session-scoped (`anonreq:{Session_ID}`),
  TTL-bound, deleted after response/cleanup, and must not be persisted to durable storage.
- **Token contract**: tokens use `[TYPE_N]`; restoration must handle case-insensitive and
  bracket-optional variants and split tokens in streaming responses.
- **OpenAI-compatible wire protocol**: keep `/v1/chat/completions` and `/v1/models` compatible;
  adapters translate to Anthropic/Gemini/Ollama/provider-specific formats internally.
- **Classification before anonymization/forwarding**: BLOCK, ROUTE_LOCAL, ANONYMIZE, PASS
  decisions happen before external provider forwarding.
- **Multi-locale/compliance behavior**: preserve `X-AnonReq-Locale`, locale checksums, locale
  bundle merging, compliance presets, and startup validation of required entity types.
- **Tenant isolation**: tenant-scoped policy, usage, spend, audit, cache, metrics labels, and
  governance records must not bleed across tenants.
- **Appliance interception safety**: transparent/reverse proxy, TLS/MITM, PAC, endpoint, agent,
  voice, and SOC paths must follow the same fail-secure and metadata-only rules as the core API.

## Testing expectations

Use the existing pytest setup from `pyproject.toml`:

```bash
uv run pytest
uv run pytest tests/property/
uv run pytest tests/unit/
uv run pytest tests/test_cache.py::test_name
uv run pytest -m load
```

When changing behavior, add or update focused tests near the affected module. Keep property-based
coverage for invariants called out in Req 16 and later enterprise requirements:

- round-trip correctness
- token uniqueness, deduplication, and cross-request randomization
- fail-secure invariants with zero forwarded data
- locale checksum validation
- no-PII-in-logs/telemetry
- streaming restoration for split tokens
- tenant isolation and policy/DLP/governance invariants

## Tech stack

- Python 3.12, FastAPI, Pydantic Settings, httpx, Redis/Valkey, Presidio Analyzer,
  prometheus-client, structlog/python-json-logger, SQLAlchemy/Alembic for governance records,
  MinIO/pyarrow/reportlab for compliance/export paths, watchdog for hot reload, cryptography for
  TLS/cert handling, and pytest/Hypothesis/fakeredis/respx for tests.
- Deployment target: Docker Compose with `anonreq`, Presidio, Valkey, and optional observability
  profile services. Multi-stage Dockerfile, Apache 2.0 license.

## Working guidance

- Treat the existing implementation and tests as real product code. Do not overwrite or revert
  unrelated dirty work.
- Read the relevant source and tests before editing; many planning docs and phase artifacts exist,
  but source and tests are the operational truth.
- Keep edits narrow and compatible with established package structure, configuration style, and
  metadata-only audit patterns.
- For security/compliance behavior, default to blocking rather than permissive fallback.
- If generated docs or planning files contradict code, verify against tests and current source
  before changing architecture.
