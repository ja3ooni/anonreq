# Phase 31: Multi-Tenant Segregation & Isolation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-18
**Phase:** 31-Multi-Tenant Segregation & Isolation
**Areas discussed:** Tenant validation & enforcement, Tenant registry & onboarding, KMS encryption strategy, Log & metrics tenant scoping

---

## Tenant Validation & Enforcement

### How should the gateway handle requests missing X-AnonReq-Tenant-ID?

| Option | Description | Selected |
|--------|-------------|----------|
| Hard reject | Reject with 400 if X-AnonReq-Tenant-ID is missing or not in the registry. Strict isolation — no implicit default tenant. | ✓ |
| Default fallback | Accept missing header as 'default' tenant for backward compatibility, but validate against registry when present. | |
| Configurable strictness | Reject in 'strict' mode only (configurable via env var), fall back to 'default' in permissive mode. | |

**User's choice:** Hard reject (Recommended)
**Notes:** Strict isolation is the priority for enterprise deployment.

### Where should tenant validation live?

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated middleware | New TenantContextMiddleware runs early in the stack (after auth, before classification), validates header + registry, sets request.state.tenant_id. Single responsibility. | ✓ |
| Extend policy middleware | Extend existing policy.py middleware to also validate tenant header. Fewer files, but mixes concerns. | |

**User's choice:** Dedicated middleware (Recommended)
**Notes:** Single responsibility principle.

### How should tenant_id flow from middleware into the pipeline?

| Option | Description | Selected |
|--------|-------------|----------|
| Middleware sets state, pipeline reads context | Middleware sets request.state.tenant_id and ProcessingContext.tenant_id is populated from it at pipeline start. Pipeline stages never read headers directly. | ✓ |
| Middleware sets state, pipeline reads request.state | Middleware validates and sets request.state; pipeline reads from request.state directly via dependency injection. | |

**User's choice:** Middleware sets state, pipeline reads context (Recommended)
**Notes:** Keeps pipeline stages decoupled from HTTP layer.

### What error response for missing/invalid tenant ID?

| Option | Description | Selected |
|--------|-------------|----------|
| JSON error response | Standard JSON error body: {"error": "missing_tenant", "message": "X-AnonReq-Tenant-ID header required"}, status 400. Matches existing error patterns. | ✓ |
| Fail-secure 503 | Fail-secure 503 with no body — treat missing tenant as security violation, not client error. | |

**User's choice:** JSON error response (Recommended)
**Notes:** Matches existing error patterns in exceptions.py.

---

## Tenant Registry & Onboarding

### Where should the tenant registry live?

| Option | Description | Selected |
|--------|-------------|----------|
| YAML config file | YAML file (config/tenants.yaml) listing valid tenant IDs, display names, and per-tenant settings. Hot-reloadable via watchdog. | |
| Database + admin API | Database-backed tenant registry via SQLAlchemy models. CRUD admin API for tenant management. | |
| YAML seed + admin API | Static YAML for initial load, with an admin API to add/modify tenants at runtime. | |

**User's choice:** "why not 1 and 2" — requested hybrid YAML + DB approach.

### For hybrid YAML + DB: which is the source of truth?

| Option | Description | Selected |
|--------|-------------|----------|
| YAML seed + DB runtime | YAML is the seed/seed list loaded at startup. Admin API can add/remove tenants at runtime, persisted to DB. Both sources merged at startup — YAML wins on conflicts. | ✓ |
| YAML-only with admin API | YAML is the single source of truth. Admin API reads/writes YAML directly (file-based CRUD). No DB for tenants. | |

**User's choice:** YAML seed + DB runtime (Recommended)
**Notes:** YAML for bootstrapping, DB for runtime flexibility.

### What fields should the tenant registry store?

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal core fields | tenant_id, display_name, enabled, kms_key_arn, created_at, updated_at. Minimal — spend limits and policies are separate concerns. | |
| Full denormalized profile | All above + spend_limits, rate_limits, allowed_providers, allowed_models. Denormalized for fast lookup but duplicates policy engine. | ✓ |

**User's choice:** Full denormalized profile
**Notes:** Fast middleware-layer lookup without hitting the policy engine on every request.

### What happens when a tenant is disabled?

| Option | Description | Selected |
|--------|-------------|----------|
| 403 Forbidden | Reject with 403 Forbidden — tenant exists but is disabled. Different from 400 (missing/invalid header). | ✓ |
| 400 Bad Request | Treat disabled the same as unknown — 400 Bad Request. Simpler, less info leaked. | |

**User's choice:** 403 Forbidden (Recommended)
**Notes:** Distinct error codes help debugging and client handling.

---

## KMS Encryption Strategy

### Which KMS backend(s) should be supported?

| Option | Description | Selected |
|--------|-------------|----------|
| Pluggable KMS backends | Abstract KMS interface (KMSClient ABC) with concrete implementations: AWS KMS, GCP KMS, local AES-256-GCM with key derivation. Tenant registry stores key ARN per tenant. | ✓ |
| AWS KMS only | Direct boto3 integration. Simplest, but locks to AWS. | |
| Local encryption only | Local AES-256-GCM only — derive keys from a master secret + tenant_id. No cloud dependency. | |

**User's choice:** Pluggable KMS backends (Recommended)
**Notes:** Follows the same pluggable pattern as Vault integration from Phase 29.

### What scope should encryption cover?

| Option | Description | Selected |
|--------|-------------|----------|
| Encrypt at storage layer | Encrypt token-to-value mappings in memory before writing to Valkey, decrypt on read. Valkey stores ciphertext. | ✓ |
| Encrypt entire value | Encrypt the entire Valkey value (JSON blob) with tenant-specific key. Coarser granularity. | |
| TLS transit only | Use Valkey's built-in TLS for transit encryption only. No application-level encryption. | |

**User's choice:** Encrypt at storage layer (Recommended)
**Notes:** Protects against Valkey data dump exposure.

### How should KMS data keys be cached?

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory key cache | Cache KMS data keys in memory per tenant with bounded TTL. Avoids KMS call on every encrypt/decrypt. | ✓ |
| No caching (per-operation) | Call KMS on every encrypt/decrypt. Simplest but high latency and cost. | |
| Valkey-cached keys | Cache keys in Valkey itself (encrypted with master key). Distributed across pods. | |

**User's choice:** In-memory key cache (Recommended)
**Notes:** Bounded TTL prevents stale keys; rotation signal triggers refresh.

---

## Log & Metrics Tenant Scoping

### How should tenant_id appear in structured logs?

| Option | Description | Selected |
|--------|-------------|----------|
| structlog contextvars | TenantContextMiddleware binds tenant_id to structlog contextvars. All loggers automatically include tenant_id. Same pattern as request_id. | ✓ |
| Explicit field passing | Middleware sets tenant_id on request.state; each module explicitly logs tenant_id=ctx.tenant_id. More control, more boilerplate. | |

**User's choice:** structlog contextvars (Recommended)
**Notes:** Follows existing request_id pattern exactly.

### How should Prometheus metrics be tenant-scoped?

| Option | Description | Selected |
|--------|-------------|----------|
| Tenant label on existing metrics | Add tenant_id as a label on existing custom Prometheus counters/histograms. Same metric names, tenant-aware aggregation. | ✓ |
| Per-tenant metric namespace | Separate metric namespace per tenant (e.g., anonreq_tenant_{id}_requests_total). Explodes cardinality. | |

**User's choice:** Tenant label on existing metrics (Recommended)
**Notes:** Low-friction, existing dashboards still work.

### Should there be a cardinality guard on tenant labels?

| Option | Description | Selected |
|--------|-------------|----------|
| Bounded cardinality with overflow | Configurable max unique tenants for metrics (default 100). TenantRegistry enforces at onboarding. Excess tenants get _overflow label. | ✓ |
| No cardinality guard | No limit — trust that production won't have thousands of tenants. | |

**User's choice:** Bounded cardinality with overflow (Recommended)
**Notes:** Prevents Prometheus storage explosion in multi-tenant environments.

---

## the agent's Discretion

- Middleware ordering within the stack
- Database model design for tenant registry
- Admin API endpoints for tenant CRUD
- KMS key rotation flow and stale key handling
- Prometheus metric label naming conventions
- Test strategy and coverage targets

## Deferred Ideas

None — discussion stayed within phase scope.
