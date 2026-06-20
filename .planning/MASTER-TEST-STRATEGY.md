# AnonReq Master Test Strategy

## Test Layers

Unit tests cover pure policy, tokenization, restoration, recognizer checksum, RBAC, config, and serialization logic. Integration tests cover FastAPI routes, Valkey, PostgreSQL, Presidio, provider mocks, SSE, connector sinks, tenant isolation, and admin APIs. Property tests prove round-trip correctness, deduplication, token uniqueness, fail-secure invariants, no-PII logs, locale checksum rejection, streaming split-token restoration, and cross-request randomization. K6 tests prove latency, throughput, backpressure, transparent proxy, and audio budgets.

## Required Properties

- Anonymize then restore returns byte-for-byte original content.
- N distinct values of a type produce N distinct tokens.
- Repeated exact values produce one token per session.
- Detection/cache/timeout/policy-store failures cause zero provider forwards.
- Logs contain no exact synthetic PII substrings.
- Streaming restoration matches non-streaming restoration for every token split index.
- Tenant A cannot read or infer Tenant B mappings, metrics, config, audit records, or evidence.

## Release Gates

No phase is complete until its acceptance tests, security tests, metrics assertions, audit event assertions, and documentation traceability are green in CI. GA requires full regression, vulnerability scan, SBOM validation, image signing, upgrade/rollback rehearsal, and customer pilot scenario suite.
