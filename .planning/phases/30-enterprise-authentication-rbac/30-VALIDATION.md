---
phase: 30
slug: enterprise-authentication-rbac
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-13
---

# Phase 30 Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest with FastAPI test clients, dependency overrides, and mocked JWKS/ingress headers |
| **Config file** | `pyproject.toml` |
| **Wave 1 command** | `uv run pytest tests/unit/auth/test_oidc_jwks_cache.py tests/integration/test_oidc_admin_gate.py -q` |
| **Wave 2 command** | `uv run pytest tests/admin/test_rbac.py tests/unit/admin/test_role_normalization.py tests/integration/test_admin_role_enforcement.py -q` |
| **Wave 3 command** | `uv run pytest tests/unit/middleware/test_mtls_ingress.py tests/integration/test_mtls_proxy_forwarding.py -q` |
| **Full suite command** | `uv run pytest` |

## Sampling Rate

- **After Wave 1:** Verify OIDC/JWKS claim handling and principal construction.
- **After Wave 2:** Verify enterprise role names and route-level RBAC enforcement.
- **After Wave 3:** Verify trusted ingress client-certificate handling and fail-closed behavior.
- **Before `$gsd-verify-work`:** Full suite must be green.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Requirement Focus | Test Type | Automated Command | Status |
|---------|------|------|-------------|-------------------|-----------|-------------------|--------|
| 30-01-01 | 01 | 1 | SSO-01 | JWTs verify against cached JWKS and populate a normalized principal. | unit + integration | `uv run pytest tests/unit/auth/test_oidc_jwks_cache.py tests/integration/test_oidc_admin_gate.py -q` | pending |
| 30-02-01 | 02 | 2 | SSO-02 | Enterprise roles enforce least-privilege access consistently across admin and gateway routes. | unit + integration | `uv run pytest tests/admin/test_rbac.py tests/unit/admin/test_role_normalization.py tests/integration/test_admin_role_enforcement.py -q` | pending |
| 30-03-01 | 03 | 3 | SSO-03 | Trusted ingress client certificates are validated and untrusted forwarding is rejected. | unit + integration | `uv run pytest tests/unit/middleware/test_mtls_ingress.py tests/integration/test_mtls_proxy_forwarding.py -q` | pending |

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live OIDC issuer/JWKS rotation | SSO-01 | Needs a real IdP and real token issuance/rotation. | Rotate JWKS in the identity provider and confirm the gateway refreshes keys without accepting invalid tokens. |
| Trusted ingress header provenance | SSO-03 | Requires deployment ingress configuration. | Confirm only the trusted proxy can set the forwarded client-cert header and that direct client injection is rejected. |

## Validation Sign-Off

- [x] All tasks have automated verification or manual fallback
- [x] Sampling continuity is maintained
- [x] No watch-mode flags required
- [x] nyquist_compliant set in frontmatter

**Approval:** pending

