# Phase 15 Security Acceptance: Deployment Models

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Controls

- Fail-secure forwarding control: Every deployment profile preserves no-disk PII mappings, TLS/mTLS controls, secrets source validation, startup preflight, and fail-secure forwarding guards.
- Tenant isolation control: all reads and writes derive tenant scope from authenticated request context.
- RBAC control: all administrative routes require explicit permission.
- Metadata-only control: logs, metrics, traces, UI responses, exports, and evidence records exclude raw payloads, token strings, entity values, secrets, and internal URLs.
- Configuration integrity control: invalid or partial configuration is rejected at startup or activation time.
- OpenAPI control: route schemas, errors, and examples are generated and validated in CI.

## Required Metrics

- `anonreq_readiness_state` must be exposed and covered by tests.
- `anonreq_startup_preflight_seconds` must be exposed and covered by tests.
- `anonreq_proxy_passthrough_total` must be exposed and covered by tests.
- `anonreq_upgrade_events_total` must be exposed and covered by tests.

## Required Audit Events

- deployment_preflight_failed audit event must be emitted with metadata only.
- deployment_profile_changed audit event must be emitted with metadata only.
- tls_interception_enabled audit event must be emitted with metadata only.
- upgrade_started audit event must be emitted with metadata only.
- upgrade_completed audit event must be emitted with metadata only.

## Release Gate

The phase may be released only when unit, integration, property, load, security, OpenAPI, documentation, and traceability checks pass. Security review must confirm zero provider forwards on injected dependency failures and zero sensitive substrings in generated logs, traces, UI payloads, and exports.

## Go/No-Go Criteria

Go:
- All tests in `15-TEST-PLAN.md` pass.
- Metrics and audit event assertions pass.
- RBAC matrix covers every new endpoint.
- No PII/logging scanner findings remain.
- Performance budgets are within the master SLO or have an approved documented exception.

No-go:
- Any fail-secure test forwards a request.
- Any durable record contains raw prompt, response, token, entity value, secret, or internal endpoint.
- Any endpoint lacks auth or tenant filtering.
- Any required audit event or metric is missing.
