# Phase 31: Multi-Tenant Segregation & Isolation - Context

**Gathered:** 2026-07-18
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase enforces strict multi-tenant isolation: mandatory tenant validation at the gateway edge, namespace-partitioned cache with per-tenant KMS encryption of token mappings, and tenant-scoped structured logging and Prometheus metrics.

</domain>

<decisions>
## Implementation Decisions

### Tenant Validation & Enforcement
- **D-01:** Hard reject — requests missing or invalid `X-AnonReq-Tenant-ID` header return HTTP 400 with JSON error body `{"error": "missing_tenant", "message": "X-AnonReq-Tenant-ID header required"}`. No implicit default tenant.
- **D-02:** Dedicated `TenantContextMiddleware` runs after auth, before classification. Validates header against tenant registry, sets `request.state.tenant_id`.
- **D-03:** Middleware sets `request.state.tenant_id`; `ProcessingContext.tenant_id` is populated from it at pipeline start. Pipeline stages never read headers directly.
- **D-04:** Disabled tenants (valid ID but `enabled=false`) receive HTTP 403 Forbidden with `{"error": "tenant_disabled"}`. Distinct from 400 (missing/invalid).

### Tenant Registry & Onboarding
- **D-05:** Hybrid model — YAML seed file (`config/tenants.yaml`) loaded at startup as seed. Admin API adds/modifies tenants at runtime, persisted to DB. YAML wins on conflicts.
- **D-06:** Full denormalized profile per tenant: `tenant_id`, `display_name`, `enabled`, `kms_key_arn`, `spend_limits`, `rate_limits`, `allowed_providers`, `allowed_models`, `created_at`, `updated_at`. Duplicates some policy engine data for fast middleware-layer lookup.

### KMS Encryption Strategy
- **D-07:** Pluggable KMS backends — abstract `KMSClient` ABC with concrete implementations: AWS KMS, GCP KMS, local AES-256-GCM with key derivation. Tenant registry stores key ARN per tenant.
- **D-08:** Encrypt at storage layer — encrypt token-to-value mappings in memory before Valkey write, decrypt on read. Valkey stores ciphertext. Protects against Valkey data dump exposure.
- **D-09:** In-memory key cache — cache KMS data keys per tenant with bounded TTL. Avoids KMS call on every encrypt/decrypt. Re-fetch on TTL expiry or rotation signal.

### Log & Metrics Tenant Scoping
- **D-10:** structlog contextvars — TenantContextMiddleware binds `tenant_id` to structlog contextvars. All loggers automatically include `tenant_id` without explicit passing. Same pattern as existing `request_id`.
- **D-11:** Tenant label on existing Prometheus counters/histograms — add `tenant_id` label to existing metrics. Same metric names, tenant-aware aggregation.
- **D-12:** Bounded cardinality — configurable max unique tenants for metrics labels (default 100). TenantRegistry enforces at onboarding. Excess tenants get `_overflow` label to prevent cardinality explosion.

### the agent's Discretion
- Exact middleware ordering within the stack (after auth, before classification — but exact position relative to other middleware)
- Database model design for tenant registry (SQLAlchemy schema, migration strategy)
- Admin API endpoints for tenant CRUD (REST design, request/response schemas)
- KMS key rotation flow and stale key handling
- Prometheus metric label naming conventions
- Test strategy and coverage targets

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/ROADMAP.md` — Phase 31 definition, goals, success criteria
- `.planning/REQUIREMENTS.md` — TEN-01 through TEN-04 traceability

### Existing Tenant-Scoped Code
- `src/anonreq/cache/manager.py` — CacheManager with `anonreq:{tenant_id}:{session_id}` key format (D-13)
- `src/anonreq/models/processing_context.py` — ProcessingContext.tenant_id field (currently defaults to "default")
- `src/anonreq/middleware/policy.py` — PolicyMiddleware._extract_tenant_id() pattern
- `src/anonreq/policy/pdp.py` — PDP tenant-scoped evaluation flow
- `src/anonreq/policy/spend_controller.py` — SpendController tenant-scoped keys
- `src/anonreq/policy/store.py` — PolicyStore tenant-scoped rule loading
- `src/anonreq/services/transparency.py` — TransparencyService tenant-scoped sessions
- `src/anonreq/services/dsar.py` — DSARService tenant-scoped requests
- `src/anonreq/policy/evidence.py` — EvidenceService tenant-scoped records

### Middleware & Auth Patterns
- `src/anonreq/middleware/rbac.py` — Existing RBAC middleware pattern
- `src/anonreq/middleware/classification.py` — ClassificationMiddleware pattern
- `src/anonreq/admin/auth.py` — Admin auth seam
- `src/anonreq/exceptions.py` — Error response patterns

### Configuration Patterns
- `config/enterprise-policy.yaml` — YAML config loading pattern
- `src/anonreq/config/__init__.py` — Settings singleton pattern
- `.env.example` — Environment variable conventions

### Observability
- `src/anonreq/monitoring/` — SLO engine and Prometheus metrics
- `src/anonreq/logging_config.py` — Structured logging setup

### Phase 30 Context (precedent)
- `.planning/phases/30-enterprise-authentication-rbac/30-CONTEXT.md` — Enterprise auth decisions that flow into tenant validation

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **CacheManager._key()**: Already implements `anonreq:{tenant_id}:{session_id}` format — just needs tenant_id to be non-default
- **PolicyMiddleware._extract_tenant_id()**: Pattern for extracting tenant from auth principal — can be adapted for header validation
- **structlog contextvars**: Already used for request_id — tenant_id follows same pattern
- **ProcessingContext.tenant_id**: Field exists, defaults to "default" — needs to be populated from validated middleware state

### Established Patterns
- **Fail-secure**: Any validation failure blocks the request immediately (HTTP 400/403)
- **Middleware ordering**: Auth → Classification → Policy pipeline; tenant validation fits between auth and classification
- **YAML config + admin API**: Enterprise policy already uses YAML seed + runtime reload pattern
- **Tenant-scoped cache keys**: All cache operations already accept tenant_id parameter

### Integration Points
- **TenantContextMiddleware**: New middleware, slots into main.py middleware stack after auth
- **CacheManager**: Needs KMS encryption layer wrapping encrypt/decrypt calls
- **structlog bind**: TenantContextMiddleware binds tenant_id to contextvars at request start
- **Prometheus metrics**: Existing metrics need tenant_id label added to Counter/Histogram definitions

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The existing codebase patterns (YAML config, middleware stacking, structlog contextvars, pluggable backends) provide strong guidance for implementation.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 31-Multi-Tenant Segregation & Isolation*
*Context gathered: 2026-07-18*
