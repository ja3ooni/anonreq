# Phase 17 Context: Disaster Recovery

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Goal

Phase 17 deliver RTO, RPO, failover, backup, restore, chaos testing, and operational runbooks for enterprise and financial-services deployments. The work is scoped as a production enterprise capability, not a prototype. It must preserve the core AnonReq guarantees: fail secure, no PII in logs, ephemeral mappings, streaming correctness, OpenAPI as source of truth, tenant isolation, and measurable security acceptance.

## Scope

In scope:
- Requirements: Req 20, Req 24, Req 25, Req 34, Req 43, Req 45.
- Components: DRRunbookSet, ConfigBackupService, RestoreVerifier, ChaosScenarioRunner, IncidentClassifier, ResilienceEvidenceStore, FailoverCoordinator.
- API surface: GET /v1/admin/resilience/test-records, POST /v1/admin/resilience/test-records, GET /v1/admin/incidents, POST /v1/admin/incidents/{incident_id}/close.
- Metrics: anonreq_failover_duration_seconds, anonreq_restore_verification_total, anonreq_incidents_open_total, anonreq_resilience_tests_total.
- Audit events: incident_opened, incident_closed, resilience_test_recorded, backup_completed, restore_verified.

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
