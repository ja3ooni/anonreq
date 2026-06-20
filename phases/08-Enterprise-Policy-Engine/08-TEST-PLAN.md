# Phase 08 Test Plan: Enterprise Policy Engine

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Unit Tests

- Pydantic validation rejects malformed configuration and accepts documented examples.
- Service-level decisions are deterministic for the same input and config version.
- Error mapping returns the documented HTTP status and structured error body.
- Metrics helpers reject unbounded label values.
- Audit payload builders enforce the metadata-only allowlist.

## Integration Tests

- Authenticated tenant-scoped requests exercise all OpenAPI endpoints: GET /v1/admin/policies, PUT /v1/admin/policies/{policy_id}, POST /v1/policy/evaluate, GET /v1/admin/tenants/{tenant_id}/usage.
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

- policy ordering and deterministic decisions.
- RPM/TPM/concurrency counters.
- budget windows at UTC boundaries.
- region routing fail-closed behavior.
- classification override handling.
- No raw prompt, raw response, token string, original entity value, secret, or internal endpoint appears in logs, traces, metrics, UI JSON, or exports.
- All administrative endpoints require authentication and correct role authorization.

## Acceptance Tests

- Required audit events are emitted: policy_decision_recorded, rate_limit_exceeded, spend_limit_exceeded, routing_policy_violation, classification_block.
- Required metrics are present: anonreq_policy_decisions_total, anonreq_policy_denials_total, anonreq_rate_limit_hits_total, anonreq_spend_limit_hits_total.
- OpenAPI schema validates and SDK contract tests remain green.
- Security acceptance gates in `08-SECURITY-ACCEPTANCE.md` pass without exception.
