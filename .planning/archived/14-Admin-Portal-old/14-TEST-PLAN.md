# Phase 14 Test Plan: Admin Portal

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Unit Tests

- Pydantic validation rejects malformed configuration and accepts documented examples.
- Service-level decisions are deterministic for the same input and config version.
- Error mapping returns the documented HTTP status and structured error body.
- Metrics helpers reject unbounded label values.
- Audit payload builders enforce the metadata-only allowlist.

## Integration Tests

- Authenticated tenant-scoped requests exercise all OpenAPI endpoints: GET /admin, GET /v1/admin/ui/bootstrap, POST /v1/oversight/{request_id}/approve, POST /v1/oversight/{request_id}/reject, POST /v1/oversight/kill-switch.
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

- route permission matrix.
- CSRF and same-site cookie behavior.
- oversight action idempotency.
- no raw content in UI API responses.
- accessibility and responsive layout checks.
- No raw prompt, raw response, token string, original entity value, secret, or internal endpoint appears in logs, traces, metrics, UI JSON, or exports.
- All administrative endpoints require authentication and correct role authorization.

## Acceptance Tests

- Required audit events are emitted: admin_login, admin_action_recorded, human_approval, human_rejection, kill_switch_activated, executive_report_generated.
- Required metrics are present: anonreq_admin_actions_total, anonreq_admin_page_load_seconds, anonreq_oversight_queue_depth, anonreq_kill_switch_state.
- OpenAPI schema validates and SDK contract tests remain green.
- Security acceptance gates in `14-SECURITY-ACCEPTANCE.md` pass without exception.
