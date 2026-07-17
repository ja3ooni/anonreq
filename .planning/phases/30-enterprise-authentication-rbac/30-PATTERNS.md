# Phase 30 Pattern Map

## File Roles

| File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/anonreq/admin/auth.py` | admin authentication | request auth | current API-key auth | exact |
| `src/anonreq/admin/router.py` | principal shaping | auth -> RBAC | current request.state principal population | exact |
| `src/anonreq/middleware/rbac.py` | role enforcement | request -> route access | current dependency-based guard | exact |
| `src/anonreq/admin/policy_routes.py` | role-gated admin route | request -> policy store | existing RBAC protected endpoints | exact |
| `src/anonreq/admin/usage_routes.py` | tenant-scoped admin route | request -> usage store | existing RBAC protected endpoints | exact |
| `src/anonreq/proxy/mitm_handler.py` | certificate trust handling | ingress -> proxy trust | current certificate pinning path | close |
| `src/anonreq/proxy/tls.py` | certificate parsing/validation | cert bytes -> trust decision | current certificate loader | close |
| `tests/admin/test_rbac.py` | RBAC contract | auth/role assertions | existing role hierarchy tests | exact |

## Pattern Assignments

### OIDC Verification

Use a request-authentication service that:

- extracts bearer tokens once
- verifies the JWT signature against cached JWKS
- validates issuer/audience/expiry
- projects claims into `request.state.role_principal`

The key property is that downstream RBAC code should not care whether the principal came from an API key, OIDC token, or an upstream trusted proxy. It should see one normalized principal shape.

### Role Normalization

Keep `require_role()` as the central enforcement primitive, but update the role vocabulary to match the enterprise milestone. Route decorators should refer to the normalized role constants, not hard-coded strings.

### mTLS Verification

Follow the existing proxy trust style:

- identify trusted ingress sources explicitly
- parse a forwarded client-cert header or env-backed proxy certificate metadata
- reject malformed or untrusted inputs before they reach route handlers

The middleware should be a fail-closed request filter, not a logging or advisory hook.

