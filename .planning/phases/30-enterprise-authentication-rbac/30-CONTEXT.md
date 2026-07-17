# Phase 30: Enterprise Authentication & RBAC - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase replaces the remaining static API-key-authenticated admin path with enterprise identity checks: OIDC JWT verification against cached JWKS, a normalized role model for gateway/admin access, and ingress-forwarded mTLS client-certificate verification.

</domain>

<baseline>
## What Is Already Implemented

- `src/anonreq/admin/auth.py` still authenticates admin access with `ANONREQ_ADMIN_API_KEY`.
- `src/anonreq/admin/router.py` already centralizes admin principal creation and allows tests/upstream layers to inject `request.state.role_principal`.
- `src/anonreq/middleware/rbac.py` already enforces a hierarchical role model with `require_role()`, but it currently uses `read_only` rather than the enterprise `read_only_auditor` name.
- `src/anonreq/middleware/rbac.py`, `src/anonreq/admin/policy_routes.py`, and `src/anonreq/admin/usage_routes.py` already provide the RBAC dependency seams that need normalization rather than redesign.
- `src/anonreq/proxy/mitm_handler.py` and `src/anonreq/proxy/tls.py` already handle certificate-related trust decisions in the proxy layer, so mTLS verification can follow the same fail-closed pattern.
- `tests/admin/test_rbac.py` already exercises the role hierarchy and dependency override behavior, giving a clear regression seam for role renaming and stricter enforcement.

</baseline>

<decisions>
## Implementation Decisions

### OIDC/JWKS
- **D-01:** Verify bearer tokens against OIDC JWKS at the edge of request authentication, then convert validated claims into the existing `request.state.role_principal` shape.
- **D-02:** Cache JWKS locally and refresh it on a bounded interval or on cache miss so repeated requests do not hit the identity provider unnecessarily.

### RBAC Normalization
- **D-03:** Treat enterprise roles as the canonical model: `administrator`, `security_officer`, `operator`, and `read_only_auditor`.
- **D-04:** Preserve compatibility with the existing `read_only` tests/paths only where needed, but move the live enforcement path to the enterprise role name.

### mTLS
- **D-05:** Verify ingress-forwarded client certificates only when the request arrived through a trusted proxy path.
- **D-06:** Fail closed on missing, malformed, or untrusted certificate headers.

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` - Phase 30 definition, goals, and success criteria
- `.planning/REQUIREMENTS.md` - SSO-01 through SSO-03 traceability
- `src/anonreq/admin/auth.py` - current admin API-key auth seam
- `src/anonreq/admin/router.py` - admin principal construction seam
- `src/anonreq/middleware/rbac.py` - role hierarchy and enforcement dependency
- `src/anonreq/admin/policy_routes.py` - policy admin RBAC enforcement
- `src/anonreq/admin/usage_routes.py` - tenant-scoped RBAC enforcement
- `src/anonreq/proxy/mitm_handler.py` - existing certificate trust/inspection pattern
- `tests/admin/test_rbac.py` - current role hierarchy coverage

</canonical_refs>

<open_questions>
## Open Questions

- Which OIDC issuer and JWKS endpoint are canonical for the target deployment?
- Which ingress header carries the forwarded client certificate in the deployment environment, and which proxy sources are trusted to set it?

</open_questions>

