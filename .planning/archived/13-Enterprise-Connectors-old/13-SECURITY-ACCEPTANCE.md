# Phase 13 Security Acceptance: Enterprise Connectors

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Controls

- Fail-secure forwarding control: Connectors are capability-scoped, tenant-scoped, and secrets-source backed; connector failures cannot cause raw data to bypass the gateway pipeline.
- Tenant isolation control: all reads and writes derive tenant scope from authenticated request context.
- RBAC control: all administrative routes require explicit permission.
- Metadata-only control: logs, metrics, traces, UI responses, exports, and evidence records exclude raw payloads, token strings, entity values, secrets, and internal URLs.
- Configuration integrity control: invalid or partial configuration is rejected at startup or activation time.
- OpenAPI control: route schemas, errors, and examples are generated and validated in CI.

## Required Metrics

- `anonreq_connector_events_total` must be exposed and covered by tests.
- `anonreq_soc_delivery_failures_total` must be exposed and covered by tests.
- `anonreq_shadow_ai_detected_total` must be exposed and covered by tests.
- `anonreq_rag_chunks_anonymized_total` must be exposed and covered by tests.

## Required Audit Events

- connector_config_updated audit event must be emitted with metadata only.
- soc_event_forwarded audit event must be emitted with metadata only.
- shadow_ai_detected audit event must be emitted with metadata only.
- rag_content_anonymized audit event must be emitted with metadata only.
- tool_approval_required audit event must be emitted with metadata only.
- unsanctioned_ai_access audit event must be emitted with metadata only.

## Release Gate

The phase may be released only when unit, integration, property, load, security, OpenAPI, documentation, and traceability checks pass. Security review must confirm zero provider forwards on injected dependency failures and zero sensitive substrings in generated logs, traces, UI payloads, and exports.

## Go/No-Go Criteria

Go:
- All tests in `13-TEST-PLAN.md` pass.
- Metrics and audit event assertions pass.
- RBAC matrix covers every new endpoint.
- No PII/logging scanner findings remain.
- Performance budgets are within the master SLO or have an approved documented exception.

No-go:
- Any fail-secure test forwards a request.
- Any durable record contains raw prompt, response, token, entity value, secret, or internal endpoint.
- Any endpoint lacks auth or tenant filtering.
- Any required audit event or metric is missing.
