# Phase 08 Security Acceptance: Enterprise Policy Engine

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Controls

- Fail-secure forwarding control: Policy evaluation is fail-closed: unavailable cache, missing tenant policy, malformed policy bundle, or unknown provider region returns 503/403 before forwarding.
- Tenant isolation control: all reads and writes derive tenant scope from authenticated request context.
- RBAC control: all administrative routes require explicit permission.
- Metadata-only control: logs, metrics, traces, UI responses, exports, and evidence records exclude raw payloads, token strings, entity values, secrets, and internal URLs.
- Configuration integrity control: invalid or partial configuration is rejected at startup or activation time.
- OpenAPI control: route schemas, errors, and examples are generated and validated in CI.

## Required Metrics

- `anonreq_policy_decisions_total` must be exposed and covered by tests.
- `anonreq_policy_denials_total` must be exposed and covered by tests.
- `anonreq_rate_limit_hits_total` must be exposed and covered by tests.
- `anonreq_spend_limit_hits_total` must be exposed and covered by tests.

## Required Audit Events

- policy_decision_recorded audit event must be emitted with metadata only.
- rate_limit_exceeded audit event must be emitted with metadata only.
- spend_limit_exceeded audit event must be emitted with metadata only.
- routing_policy_violation audit event must be emitted with metadata only.
- classification_block audit event must be emitted with metadata only.

## Release Gate

The phase may be released only when unit, integration, property, load, security, OpenAPI, documentation, and traceability checks pass. Security review must confirm zero provider forwards on injected dependency failures and zero sensitive substrings in generated logs, traces, UI payloads, and exports.

## Go/No-Go Criteria

Go:
- All tests in `08-TEST-PLAN.md` pass.
- Metrics and audit event assertions pass.
- RBAC matrix covers every new endpoint.
- No PII/logging scanner findings remain.
- Performance budgets are within the master SLO or have an approved documented exception.

No-go:
- Any fail-secure test forwards a request.
- Any durable record contains raw prompt, response, token, entity value, secret, or internal endpoint.
- Any endpoint lacks auth or tenant filtering.
- Any required audit event or metric is missing.
