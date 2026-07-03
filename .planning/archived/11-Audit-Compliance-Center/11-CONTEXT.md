# Phase 11 Context: Audit and Compliance Center

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Goal

Phase 11 provide immutable metadata-only audit, configuration history, lineage records, compliance exports, and regulator-ready evidence packages. The work is scoped as a production enterprise capability, not a prototype. It must preserve the core AnonReq guarantees: fail secure, no PII in logs, ephemeral mappings, streaming correctness, OpenAPI as source of truth, tenant isolation, and measurable security acceptance.

## Scope

In scope:
- Requirements: Req 10, Req 24, Req 25, Req 27, Req 30, Req 35, Req 37, Req 44, Req 45, Req 47.
- Components: AuditEventIngestor, AppendOnlyEvidenceStore, ConfigHistoryService, LineageService, ComplianceReportBuilder, EvidencePackageExporter, RetentionPolicyWorker.
- API surface: GET /v1/admin/audit/config-history, GET /v1/admin/audit/config-history/export, GET /v1/admin/lineage/{lineage_id}, GET /v1/admin/compliance/report, GET /v1/admin/compliance/conformity-package.
- Metrics: anonreq_audit_log_failures_total, anonreq_evidence_exports_total, anonreq_lineage_integrity_failures_total, anonreq_retention_actions_total.
- Audit events: config_change_recorded, lineage_record_written, compliance_report_generated, conformity_package_generated, retention_policy_applied.

Out of scope:
- Relaxing ForwardingGuard requirements.
- Persisting token mappings, raw prompts, raw responses, raw transcript text, or original entity values.
- Adding unauthenticated administrative routes.
- Provider-specific shortcuts that bypass the internal OpenAI-compatible envelope.

## Business Value

This phase moves AnonReq from a privacy gateway toward an enterprise AI control plane. It gives security, compliance, platform, and SRE teams enforceable controls they can operate, audit, and explain during procurement, regulator review, and incident response.

## Dependencies

The phase assumes the Stage 1 gateway pipeline exists: request context, detection, tokenization, Valkey mapping, provider routing, restoration, audit logging, health checks, metrics, and property tests. It also depends on the master security model's rule that all forwarding flows through ForwardingGuard after a sanitized envelope is produced.

## Success Criteria

- All new behavior is tenant-scoped and role-protected.
- All new failures are fail-secure and produce controlled 4xx/5xx responses.
- Required metrics and audit events are emitted with metadata only.
- Tests listed in the phase test plan pass in CI.
- Documentation and OpenAPI updates are complete before implementation is marked done.
