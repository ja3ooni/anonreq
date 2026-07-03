# Phase 14 Context: Admin Portal

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Goal

Phase 14 deliver a secure operational UI for tenant administration, policy management, governance queues, evidence export, incident review, and compliance reporting. The work is scoped as a production enterprise capability, not a prototype. It must preserve the core AnonReq guarantees: fail secure, no PII in logs, ephemeral mappings, streaming correctness, OpenAPI as source of truth, tenant isolation, and measurable security acceptance.

## Scope

In scope:
- Requirements: Req 17, Req 22, Req 24, Req 25, Req 27, Req 28, Req 29, Req 30, Req 34, Req 35, Req 47.
- Components: AdminFrontend, AdminBFF, PermissionAwareNavigation, PolicyEditor, OversightQueueUI, EvidenceExportUI, IncidentWorkbench, GovernanceDashboard.
- API surface: GET /admin, GET /v1/admin/ui/bootstrap, POST /v1/oversight/{request_id}/approve, POST /v1/oversight/{request_id}/reject, POST /v1/oversight/kill-switch.
- Metrics: anonreq_admin_actions_total, anonreq_admin_page_load_seconds, anonreq_oversight_queue_depth, anonreq_kill_switch_state.
- Audit events: admin_login, admin_action_recorded, human_approval, human_rejection, kill_switch_activated, executive_report_generated.

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
