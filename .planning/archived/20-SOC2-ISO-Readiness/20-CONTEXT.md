# Phase 20 Context: SOC2 and ISO Readiness

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Goal

Phase 20 prepare controls, evidence, policies, and technical mappings for SOC 2, ISO 27001, ISO 42001, GDPR, NIS2, DORA, and financial-services procurement reviews. The work is scoped as a production enterprise capability, not a prototype. It must preserve the core AnonReq guarantees: fail secure, no PII in logs, ephemeral mappings, streaming correctness, OpenAPI as source of truth, tenant isolation, and measurable security acceptance.

## Scope

In scope:
- Requirements: Req 24, Req 25, Req 26, Req 27, Req 28, Req 32, Req 35, Req 37, Req 43, Req 47.
- Components: ControlCatalog, EvidenceCollector, PolicyDocumentSet, TraceabilityMatrix, RiskRegisterWorkflow, AuditReadinessExporter, VendorQuestionnaireResponder.
- API surface: GET /v1/admin/compliance/report, GET /v1/admin/governance/export, GET /v1/admin/risk-assessments/export, GET /v1/admin/fairness/report.
- Metrics: anonreq_controls_implemented_total, anonreq_evidence_freshness_seconds, anonreq_risk_treatments_overdue_total.
- Audit events: control_evidence_updated, risk_assessment_approved, governance_review_recorded, audit_package_exported.

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
