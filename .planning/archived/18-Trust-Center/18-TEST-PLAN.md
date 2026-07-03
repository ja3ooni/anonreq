# Phase 18 Test Plan: Trust Center

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Unit Tests

- Pydantic validation rejects malformed configuration and accepts documented examples.
- Service-level decisions are deterministic for the same input and config version.
- Error mapping returns the documented HTTP status and structured error body.
- Metrics helpers reject unbounded label values.
- Audit payload builders enforce the metadata-only allowlist.

## Integration Tests

- Authenticated tenant-scoped requests exercise all OpenAPI endpoints: GET /trust, GET /trust/sbom, GET /trust/detection-quality, GET /trust/slo, GET /trust/security-package.
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

- artifact allowlist enforcement.
- SBOM hash integrity.
- detection quality report freshness.
- broken link scan.
- public/private evidence separation.
- No raw prompt, raw response, token string, original entity value, secret, or internal endpoint appears in logs, traces, metrics, UI JSON, or exports.
- All administrative endpoints require authentication and correct role authorization.

## Acceptance Tests

- Required audit events are emitted: trust_artifact_published, security_package_generated, public_slo_status_updated, sbom_published.
- Required metrics are present: anonreq_trust_artifacts_published_total, anonreq_public_slo_status, anonreq_security_package_downloads_total.
- OpenAPI schema validates and SDK contract tests remain green.
- Security acceptance gates in `18-SECURITY-ACCEPTANCE.md` pass without exception.
