# Phase 11 Security Acceptance: Audit and Compliance Center

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Controls

- Fail-secure forwarding control: Evidence stores never contain raw prompts, raw responses, tokens, provider keys, internal URLs, or original entity values; all records use hashes and counts.
- Tenant isolation control: all reads and writes derive tenant scope from authenticated request context.
- RBAC control: all administrative routes require explicit permission.
- Metadata-only control: logs, metrics, traces, UI responses, exports, and evidence records exclude raw payloads, token strings, entity values, secrets, and internal URLs.
- Configuration integrity control: invalid or partial configuration is rejected at startup or activation time.
- OpenAPI control: route schemas, errors, and examples are generated and validated in CI.

## Required Metrics

- `anonreq_audit_log_failures_total` must be exposed and covered by tests.
- `anonreq_evidence_exports_total` must be exposed and covered by tests.
- `anonreq_lineage_integrity_failures_total` must be exposed and covered by tests.
- `anonreq_retention_actions_total` must be exposed and covered by tests.

## Required Audit Events

- config_change_recorded audit event must be emitted with metadata only.
- lineage_record_written audit event must be emitted with metadata only.
- compliance_report_generated audit event must be emitted with metadata only.
- conformity_package_generated audit event must be emitted with metadata only.
- retention_policy_applied audit event must be emitted with metadata only.

## Release Gate

The phase may be released only when unit, integration, property, load, security, OpenAPI, documentation, and traceability checks pass. Security review must confirm zero provider forwards on injected dependency failures and zero sensitive substrings in generated logs, traces, UI payloads, and exports.

## Go/No-Go Criteria

Go:
- All tests in `11-TEST-PLAN.md` pass.
- Metrics and audit event assertions pass.
- RBAC matrix covers every new endpoint.
- No PII/logging scanner findings remain.
- Performance budgets are within the master SLO or have an approved documented exception.

No-go:
- Any fail-secure test forwards a request.
- Any durable record contains raw prompt, response, token, entity value, secret, or internal endpoint.
- Any endpoint lacks auth or tenant filtering.
- Any required audit event or metric is missing.
