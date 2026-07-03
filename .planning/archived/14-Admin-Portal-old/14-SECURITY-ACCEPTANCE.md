# Phase 14 Security Acceptance: Admin Portal

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Controls

- Fail-secure forwarding control: The portal is metadata-only: it never renders raw prompts, raw responses, token strings, provider secrets, or original detected values.
- Tenant isolation control: all reads and writes derive tenant scope from authenticated request context.
- RBAC control: all administrative routes require explicit permission.
- Metadata-only control: logs, metrics, traces, UI responses, exports, and evidence records exclude raw payloads, token strings, entity values, secrets, and internal URLs.
- Configuration integrity control: invalid or partial configuration is rejected at startup or activation time.
- OpenAPI control: route schemas, errors, and examples are generated and validated in CI.

## Required Metrics

- `anonreq_admin_actions_total` must be exposed and covered by tests.
- `anonreq_admin_page_load_seconds` must be exposed and covered by tests.
- `anonreq_oversight_queue_depth` must be exposed and covered by tests.
- `anonreq_kill_switch_state` must be exposed and covered by tests.

## Required Audit Events

- admin_login audit event must be emitted with metadata only.
- admin_action_recorded audit event must be emitted with metadata only.
- human_approval audit event must be emitted with metadata only.
- human_rejection audit event must be emitted with metadata only.
- kill_switch_activated audit event must be emitted with metadata only.
- executive_report_generated audit event must be emitted with metadata only.

## Release Gate

The phase may be released only when unit, integration, property, load, security, OpenAPI, documentation, and traceability checks pass. Security review must confirm zero provider forwards on injected dependency failures and zero sensitive substrings in generated logs, traces, UI payloads, and exports.

## Go/No-Go Criteria

Go:
- All tests in `14-TEST-PLAN.md` pass.
- Metrics and audit event assertions pass.
- RBAC matrix covers every new endpoint.
- No PII/logging scanner findings remain.
- Performance budgets are within the master SLO or have an approved documented exception.

No-go:
- Any fail-secure test forwards a request.
- Any durable record contains raw prompt, response, token, entity value, secret, or internal endpoint.
- Any endpoint lacks auth or tenant filtering.
- Any required audit event or metric is missing.
