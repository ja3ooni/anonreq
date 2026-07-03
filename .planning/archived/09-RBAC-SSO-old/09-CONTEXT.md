# Phase 09 Context: RBAC and SSO

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Goal

Phase 09 replace minimal bearer authentication with enterprise-grade API key, OIDC, SAML, mTLS, revocation, and role authorization across every administrative surface. The work is scoped as a production enterprise capability, not a prototype. It must preserve the core AnonReq guarantees: fail secure, no PII in logs, ephemeral mappings, streaming correctness, OpenAPI as source of truth, tenant isolation, and measurable security acceptance.

## Scope

In scope:
- Requirements: Req 17, Req 18, Req 19, Req 25, Req 27, Req 29.
- Components: CredentialVerifier, OIDCVerifier, SAMLServiceProvider, MTLSIdentityExtractor, RBACAuthorizer, RevocationCache, SessionPrincipalMiddleware.
- API surface: GET /v1/security/status, POST /v1/admin/api-keys, DELETE /v1/admin/api-keys/{key_id}, GET /v1/admin/auth/events.
- Metrics: anonreq_auth_events_total, anonreq_authz_denials_total, anonreq_jwks_refresh_total, anonreq_revocation_lookup_seconds.
- Audit events: auth_success, auth_failure, authz_denied, api_key_created, api_key_revoked, sso_mapping_updated.

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
