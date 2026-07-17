# Phase 30 Research

## Local Codebase Findings

1. `src/anonreq/admin/auth.py` is still hard-wired to `ANONREQ_ADMIN_API_KEY`, so the plan needs a new identity-verification seam instead of trying to extend the key check.
2. `src/anonreq/admin/router.py` already produces the `request.state.role_principal` object that the RBAC middleware consumes. That is the clean handoff point for OIDC claims.
3. `src/anonreq/middleware/rbac.py` already has a hierarchy and a reusable dependency factory. The phase can normalize the role names without changing the dependency contract.
4. `src/anonreq/admin/policy_routes.py` and `src/anonreq/admin/usage_routes.py` already gate access with `require_role()`, so their dependency declarations can be updated in place after the role model changes.
5. `tests/admin/test_rbac.py` already covers the role ladder and 401/403 behavior. That gives a direct regression suite for the role rename and stricter enterprise-role enforcement.
6. The repo already has certificate-trust code in `src/anonreq/proxy/mitm_handler.py` and `src/anonreq/proxy/tls.py`, but it does not yet validate ingress-forwarded client certificates for gateway/admin auth.
7. There is no local OIDC/JWKS client package already in `pyproject.toml`, so phase 30 needs an explicit auth dependency for claim verification and JWKS caching.

## Planning Implications

- The phase should split into three clearly bounded pieces: OIDC verification, RBAC normalization, and mTLS ingress validation.
- The OIDC work should not invent a parallel principal model; it should populate the same request-state shape the RBAC layer already understands.
- Role normalization should be intentional about the enterprise role name `read_only_auditor`, because the current code uses `read_only`.
- mTLS verification should stay fail-closed and proxy-aware. It should trust only the configured ingress headers and never accept raw client-provided certificate claims without a trusted proxy boundary.

