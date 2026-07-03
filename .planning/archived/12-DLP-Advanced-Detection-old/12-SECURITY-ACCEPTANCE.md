# Phase 12 Security Acceptance: DLP and Advanced Detection

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Controls

- Fail-secure forwarding control: DLP action resolution is deny-biased: block outranks quarantine, quarantine outranks redact, redact outranks anonymize, and anonymize outranks allow.
- Tenant isolation control: all reads and writes derive tenant scope from authenticated request context.
- RBAC control: all administrative routes require explicit permission.
- Metadata-only control: logs, metrics, traces, UI responses, exports, and evidence records exclude raw payloads, token strings, entity values, secrets, and internal URLs.
- Configuration integrity control: invalid or partial configuration is rejected at startup or activation time.
- OpenAPI control: route schemas, errors, and examples are generated and validated in CI.

## Required Metrics

- `anonreq_dlp_actions_total` must be exposed and covered by tests.
- `anonreq_prompt_security_events_total` must be exposed and covered by tests.
- `anonreq_firewall_events_total` must be exposed and covered by tests.
- `anonreq_detection_quality_score` must be exposed and covered by tests.

## Required Audit Events

- dlp_action_applied audit event must be emitted with metadata only.
- prompt_injection_blocked audit event must be emitted with metadata only.
- jailbreak_flagged audit event must be emitted with metadata only.
- output_policy_violation audit event must be emitted with metadata only.
- mnpi_detected audit event must be emitted with metadata only.
- financial_crime_entity_detected audit event must be emitted with metadata only.

## Release Gate

The phase may be released only when unit, integration, property, load, security, OpenAPI, documentation, and traceability checks pass. Security review must confirm zero provider forwards on injected dependency failures and zero sensitive substrings in generated logs, traces, UI payloads, and exports.

## Go/No-Go Criteria

Go:
- All tests in `12-TEST-PLAN.md` pass.
- Metrics and audit event assertions pass.
- RBAC matrix covers every new endpoint.
- No PII/logging scanner findings remain.
- Performance budgets are within the master SLO or have an approved documented exception.

No-go:
- Any fail-secure test forwards a request.
- Any durable record contains raw prompt, response, token, entity value, secret, or internal endpoint.
- Any endpoint lacks auth or tenant filtering.
- Any required audit event or metric is missing.
