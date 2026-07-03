# Phase 10 Context: Tenant Isolation

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Goal

Phase 10 make tenant context structurally mandatory and isolate cache keys, configuration, provider credentials, audit streams, metrics, and administrative visibility. The work is scoped as a production enterprise capability, not a prototype. It must preserve the core AnonReq guarantees: fail secure, no PII in logs, ephemeral mappings, streaming correctness, OpenAPI as source of truth, tenant isolation, and measurable security acceptance.

## Scope

In scope:
- Requirements: Req 19, Req 21, Req 22, Req 24, Req 25, Req 44, Req 46.
- Components: TenantRegistry, TenantContextMiddleware, TenantConfigResolver, TenantScopedCache, TenantMetricFilter, TenantAuditRouter, TenantProvisioningService.
- API surface: POST /v1/admin/tenants, GET /v1/admin/tenants, DELETE /v1/admin/tenants/{tenant_id}, GET /v1/admin/tenants/{tenant_id}/usage.
- Metrics: anonreq_tenant_active_sessions, anonreq_tenant_config_reload_total, anonreq_cross_tenant_denials_total.
- Audit events: tenant_provisioned, tenant_deprovisioned, tenant_config_loaded, cross_tenant_access_denied.

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
