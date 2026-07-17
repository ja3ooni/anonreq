---
phase: 30-enterprise-authentication-rbac
plan: 01
wave: 1
status: complete
requirements:
  - SSO-01
---

# Phase 30 Plan 01 Summary

OIDC authentication is now backed by cached JWKS verification instead of the static admin API-key gate.

## What Changed

- Added `src/anonreq/auth/oidc.py` with:
  - `JWKSCache` for cached JWKS retrieval and refresh on cache miss
  - `OIDCVerifier` for signature and claim validation
  - principal projection into the existing `request.state.role_principal` shape
- Reworked `src/anonreq/admin/auth.py` so admin requests validate OIDC bearer tokens when OIDC settings are present.
- Kept the legacy API-key path only as a migration fallback when OIDC is not configured.
- Wired `app.state.oidc_verifier` in `src/anonreq/main.py` so JWKS caching survives across requests.

## Verification

- `uv run pytest tests/unit/auth/test_oidc_jwks_cache.py tests/integration/test_oidc_admin_gate.py -q`
- `uv run pytest tests/admin/test_policy_routes.py tests/admin/test_usage_routes.py tests/integration/test_admin_rules.py -q`

## Result

- Valid JWTs authorize admin access.
- Invalid signatures, expired tokens, and missing claims fail closed.
- JWKS refresh works without restarting the service.
