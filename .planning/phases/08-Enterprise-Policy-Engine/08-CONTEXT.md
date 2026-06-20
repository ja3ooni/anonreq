# Phase 08 Context: Enterprise Policy Engine

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Goal

Phase 08 centralize policy evaluation for rate limits, spend controls, data residency, classification handling, and high-risk routing decisions before any provider forwarding can occur. The work is scoped as a production enterprise capability, not a prototype. It must preserve the core AnonReq guarantees: fail secure, no PII in logs, ephemeral mappings, streaming correctness, OpenAPI as source of truth, tenant isolation, and measurable security acceptance.

## Scope

In scope:
- Requirements: Req 21, Req 22, Req 29, Req 30, Req 36, Req 41, Req 46, Req 48, Req 49.
- Components: PolicyDecisionPoint, PolicyEnforcementPoint, PolicyStore, UsageLimiter, SpendController, ResidencyRouter, DecisionAuditPublisher.
- API surface: GET /v1/admin/policies, PUT /v1/admin/policies/{policy_id}, POST /v1/policy/evaluate, GET /v1/admin/tenants/{tenant_id}/usage.
- Metrics: anonreq_policy_decisions_total, anonreq_policy_denials_total, anonreq_rate_limit_hits_total, anonreq_spend_limit_hits_total.
- Audit events: policy_decision_recorded, rate_limit_exceeded, spend_limit_exceeded, routing_policy_violation, classification_block.

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
