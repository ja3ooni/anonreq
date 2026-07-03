# Phase 10 Test Plan: Tenant Isolation

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Unit Tests

- Pydantic validation rejects malformed configuration and accepts documented examples.
- Service-level decisions are deterministic for the same input and config version.
- Error mapping returns the documented HTTP status and structured error body.
- Metrics helpers reject unbounded label values.
- Audit payload builders enforce the metadata-only allowlist.

## Integration Tests

- Authenticated tenant-scoped requests exercise all OpenAPI endpoints: POST /v1/admin/tenants, GET /v1/admin/tenants, DELETE /v1/admin/tenants/{tenant_id}, GET /v1/admin/tenants/{tenant_id}/usage.
- Dependency outage scenarios return fail-secure 503/500 responses with zero provider forwards.
- Durable records are written with hashes, IDs, counts, and timestamps only.
- RBAC denies callers without the required role and emits `authz_denied`.
- Multi-tenant concurrent execution confirms no cross-tenant read, write, metric, or audit leak.

## Property Tests

- For generated tenant IDs, session IDs, actor IDs, and policy inputs, decisions remain tenant-scoped and never include raw generated sensitive strings in logs.
- For generated failure injection points, provider forward count remains zero unless all preconditions pass.
- For generated config permutations, deny actions dominate allow actions when policies conflict.

## Load Tests

- K6 scenarios run at baseline, burst, and soak profiles with latency budgets tied to the master SLOs.
- Queue, cache, and database pressure produce controlled backpressure instead of unsanitized forwarding.
- Metrics remain bounded in cardinality under randomized tenant and request IDs.

## Security Tests

- concurrent cross-tenant mapping isolation.
- tenant deprovision active session invalidation.
- metrics scrape filtering.
- config independence.
- provider credential separation.
- No raw prompt, raw response, token string, original entity value, secret, or internal endpoint appears in logs, traces, metrics, UI JSON, or exports.
- All administrative endpoints require authentication and correct role authorization.

## Acceptance Tests

- Required audit events are emitted: tenant_provisioned, tenant_deprovisioned, tenant_config_loaded, cross_tenant_access_denied.
- Required metrics are present: anonreq_tenant_active_sessions, anonreq_tenant_config_reload_total, anonreq_cross_tenant_denials_total.
- OpenAPI schema validates and SDK contract tests remain green.
- Security acceptance gates in `10-SECURITY-ACCEPTANCE.md` pass without exception.
