# Phase 18 Context: Trust Center

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Goal

Phase 18 publish customer-facing security, privacy, compliance, detection quality, SLO, SBOM, incident, and data-sovereignty evidence without exposing tenant-sensitive material. The work is scoped as a production enterprise capability, not a prototype. It must preserve the core AnonReq guarantees: fail secure, no PII in logs, ephemeral mappings, streaming correctness, OpenAPI as source of truth, tenant isolation, and measurable security acceptance.

## Scope

In scope:
- Requirements: Req 14, Req 15, Req 21, Req 24, Req 26, Req 35, Req 37, Req 47.
- Components: TrustCenterSite, PublicEvidencePublisher, SBOMPublisher, DetectionQualityPublisher, SLOStatusPublisher, SecurityQuestionnairePackager, LegalDocumentRegistry.
- API surface: GET /trust, GET /trust/sbom, GET /trust/detection-quality, GET /trust/slo, GET /trust/security-package.
- Metrics: anonreq_trust_artifacts_published_total, anonreq_public_slo_status, anonreq_security_package_downloads_total.
- Audit events: trust_artifact_published, security_package_generated, public_slo_status_updated, sbom_published.

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
