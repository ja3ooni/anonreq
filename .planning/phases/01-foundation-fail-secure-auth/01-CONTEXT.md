# Phase 1: Foundation, Fail-Secure & Auth - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish a leak-free, authenticated scaffold — global exception handler, no-PII logging, static bearer token middleware, Docker Compose deployment, health endpoint, and pre-flight startup checks. Nothing that touches request data ships until these guarantees are in place.

All Phase 1 code is infrastructure: exception handling, logging, config, Docker, auth health checks. The detection/pipeline/tokenization layer starts in Phase 2.
</domain>

<decisions>
## Implementation Decisions

### Exception Handling & Error Model
- **D-01:** Differentiate client vs server errors using status codes: 401 (auth), 400/422 (invalid request), 403 (policy blocked), 415 (unsupported content), 429 (rate limit), 503 (dependency unavailable), 500 (internal gateway error)
- **D-02:** Error responses use OpenAI-compatible envelope extended with `request_id`:
  ```json
  {"error": {"message": "...", "type": "...", "code": "...", "request_id": "req_xxxxx"}}
  ```
  No prompt content, PII, token mappings, provider URLs, API keys, stack traces, or dependency internals.
- **D-03: FAIL-05 — Forwarding_Guard** — Verify classification, policy evaluation, detection, tokenization, and mapping persisted before any outbound provider call. Missing prerequisite → abort with 503.

### Logging
- **D-04:** Use `structlog` for structured logging
- **D-05:** Strict field allowlist — only these fields survive serialization:
  - `timestamp`, `level`, `event`, `request_id`, `component`, `status_code`, `duration_ms`, `error_type`, `version`
- **D-06:** Explicitly excluded: request content, response content, entity values, token mappings, prompts, headers, authorization data, IP addresses, session identifiers. Non-allowlisted fields are dropped before serialization.

### Configuration
- **D-07:** Hybrid model — Pydantic Settings for runtime/env var config, YAML for security policy and business logic
- **D-08:** Required env vars: `ANONREQ_API_KEY` (≥ 32 chars), `ANONREQ_VALKEY_URL`, `ANONREQ_PRESIDIO_URL`
- **D-09:** Optional env vars: `ANONREQ_HOST` (0.0.0.0), `ANONREQ_PORT` (8080), `ANONREQ_LOG_LEVEL` (INFO), `ANONREQ_REQUEST_TIMEOUT_SECONDS` (30)
- **D-10:** Startup validation: API key length, all required URLs present, connectivity to Valkey and Presidio verified before serving traffic

### Tenant Isolation
- **D-11:** Tenant-ready architecture from Phase 1. Default tenant_id = "default". Tenant_ID included in: cache key namespace (`anonreq:{tenant_id}:{session_id}`), audit events, metrics labels, policy lookups, configuration objects
- **D-12:** Core `RequestContext` class: request_id, tenant_id, session_id

### Mapping Store (Valkey)
- **D-13:** Valkey HASH for mapping: `anonreq:{tenant_id}:{session_id}`, fields are `token → original_value`
- **D-14:** Atomic HSET + EXPIRE via MULTI/EXEC or pipeline (no orphaned mappings without TTL)
- **D-15:** HGETALL for SSE pre-fetch, async DEL after response, TTL extension during long streams

### Provider Capabilities
- **D-16:** YAML-based capability registry loaded at startup, not hard-coded in adapters
- **D-17:** Adapters handle: request translation, response translation, authentication, error normalization. Registry handles: streaming, tool calling, vision, JSON mode, embeddings, reasoning, context limits
- **D-18:** Future: provider-level → model-level capabilities

### Testing
- **D-19:** Invariant-driven exit criteria, not coverage-driven
- **D-20:** Required: unit tests (config, auth, exception handler, health, logging, startup checks), Docker integration tests (gateway + valkey + presidio), security invariants (no PII in logs or error responses, dependency failures block forwarding and startup)
- **D-21:** 80% overall coverage, 100% for security-critical modules. Fail-secure guarantees proven automatically in CI.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — FAIL-01 to FAIL-04, AUDT-01 to AUDT-03, AUTH-MINIMAL-01, DOCK-01 to DOCK-07
- `.planning/ROADMAP.md` § Phase 1 — Success criteria, 5 plans (01-01 to 01-05)

### Project Decisions
- `.planning/PROJECT.md` — Python 3.12 + FastAPI, Presidio sidecar, Valkey, Docker Compose, Apache 2.0, fail-secure mandate, no-PII logging constraint

### Hardening Decisions (from ROADMAP.md § Stage 1)
- Fail-secure error boundaries and auth are Phase 1, Plans 01-02 and 01-05
- Classification runs before anonymization (Phase 2, Plan 02-02)
- Property-based tests are written alongside the phases they prove
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
None — this is a greenfield project. No code exists yet.

### Established Patterns
Python 3.12 + FastAPI + Pydantic v2 documented in PROJECT.md Key Decisions.

### Integration Points
- Presidio Analyzer at `ANONREQ_PRESIDIO_URL` (Docker sidecar)
- Valkey at `ANONREQ_VALKEY_URL` (Docker sidecar)
- Docker Compose with 3 services: anonreq, presidio-analyzer, valkey
</code_context>

<specifics>
## Specific Ideas

- FAIL-05 Forwarding_Guard: every outbound provider call must pass through a guard verifying classification, policy evaluation, detection, tokenization, and mapping persistence completed
- `RequestContext` data class: `request_id: str, tenant_id: str, session_id: str`
- Error envelope: `{"error": {"message": "...", "type": "...", "code": "...", "request_id": "req_xxxxx"}}`
- Logging principle: "If a field is not explicitly allowlisted, it is dropped before serialization"
</specifics>

<deferred>
## Deferred Ideas

- Classification framework details — Phase 2 concern
- Policy engine evolution — Phase 2+ concern
- Dynamic provider/model discovery — Phase 3+ concern
- Multi-tenancy (non-default tenants) — Deferred Req 19, post-Stage 3
</deferred>

---

*Phase: 1-Foundation, Fail-Secure & Auth*
*Context gathered: 2026-06-20*
