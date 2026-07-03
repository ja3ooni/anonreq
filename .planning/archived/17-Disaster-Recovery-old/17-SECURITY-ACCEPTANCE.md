# Phase 17 Security Acceptance: Disaster Recovery

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Controls

- Fail-secure forwarding control: DR restores configuration and evidence, never volatile token mappings; during failover uncertainty, request forwarding is denied instead of running without cache or detection.
- Tenant isolation control: all reads and writes derive tenant scope from authenticated request context.
- RBAC control: all administrative routes require explicit permission.
- Metadata-only control: logs, metrics, traces, UI responses, exports, and evidence records exclude raw payloads, token strings, entity values, secrets, and internal URLs.
- Configuration integrity control: invalid or partial configuration is rejected at startup or activation time.
- OpenAPI control: route schemas, errors, and examples are generated and validated in CI.

## Required Metrics

- `anonreq_failover_duration_seconds` must be exposed and covered by tests.
- `anonreq_restore_verification_total` must be exposed and covered by tests.
- `anonreq_incidents_open_total` must be exposed and covered by tests.
- `anonreq_resilience_tests_total` must be exposed and covered by tests.

## Required Audit Events

- incident_opened audit event must be emitted with metadata only.
- incident_closed audit event must be emitted with metadata only.
- resilience_test_recorded audit event must be emitted with metadata only.
- backup_completed audit event must be emitted with metadata only.
- restore_verified audit event must be emitted with metadata only.

## Release Gate

The phase may be released only when unit, integration, property, load, security, OpenAPI, documentation, and traceability checks pass. Security review must confirm zero provider forwards on injected dependency failures and zero sensitive substrings in generated logs, traces, UI payloads, and exports.

## Go/No-Go Criteria

Go:
- All tests in `17-TEST-PLAN.md` pass.
- Metrics and audit event assertions pass.
- RBAC matrix covers every new endpoint.
- No PII/logging scanner findings remain.
- Performance budgets are within the master SLO or have an approved documented exception.

No-go:
- Any fail-secure test forwards a request.
- Any durable record contains raw prompt, response, token, entity value, secret, or internal endpoint.
- Any endpoint lacks auth or tenant filtering.
- Any required audit event or metric is missing.
