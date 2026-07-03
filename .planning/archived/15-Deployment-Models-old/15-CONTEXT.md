# Phase 15 Context: Deployment Models

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Goal

Phase 15 support Docker Compose, Kubernetes Helm, HA Valkey, virtual appliance, physical appliance, transparent proxy, and air-gapped deployment patterns. The work is scoped as a production enterprise capability, not a prototype. It must preserve the core AnonReq guarantees: fail secure, no PII in logs, ephemeral mappings, streaming correctness, OpenAPI as source of truth, tenant isolation, and measurable security acceptance.

## Scope

In scope:
- Requirements: Req 12, Req 18, Req 20, Req 21, Req 43, Req 48, Req 57.
- Components: DockerPackaging, HelmChart, ValkeyHAProfiles, TransparentProxyRuntime, ApplianceBootstrapper, AirGapArtifactBundle, UpgradeController.
- API surface: GET /health, GET /metrics, GET /v1/admin/deployment/status, POST /v1/admin/deployment/preflight.
- Metrics: anonreq_readiness_state, anonreq_startup_preflight_seconds, anonreq_proxy_passthrough_total, anonreq_upgrade_events_total.
- Audit events: deployment_preflight_failed, deployment_profile_changed, tls_interception_enabled, upgrade_started, upgrade_completed.

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
