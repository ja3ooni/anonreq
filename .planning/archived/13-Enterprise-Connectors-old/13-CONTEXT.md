# Phase 13 Context: Enterprise Connectors

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Goal

Phase 13 connect AnonReq to enterprise identity, secrets, SIEM, CASB, vector stores, voice systems, meeting assistants, and agent frameworks without weakening fail-secure guarantees. The work is scoped as a production enterprise capability, not a prototype. It must preserve the core AnonReq guarantees: fail secure, no PII in logs, ephemeral mappings, streaming correctness, OpenAPI as source of truth, tenant isolation, and measurable security acceptance.

## Scope

In scope:
- Requirements: Req 18, Req 33, Req 40, Req 50, Req 51, Req 53, Req 54, Req 55, Req 56.
- Components: ConnectorRuntime, SecretsProviderAdapters, SIEMSinkManager, CASBIngestor, RAGConnectorManager, VoiceConnectorGateway, AgentToolGovernanceBridge.
- API surface: GET /v1/admin/connectors, PUT /v1/admin/connectors/{connector_id}, GET /v1/admin/soc/integration/status, GET /v1/admin/discovery/inventory, GET /v1/admin/casb/activity.
- Metrics: anonreq_connector_events_total, anonreq_soc_delivery_failures_total, anonreq_shadow_ai_detected_total, anonreq_rag_chunks_anonymized_total.
- Audit events: connector_config_updated, soc_event_forwarded, shadow_ai_detected, rag_content_anonymized, tool_approval_required, unsanctioned_ai_access.

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
