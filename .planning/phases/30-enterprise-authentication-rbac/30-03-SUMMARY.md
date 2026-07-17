---
phase: 30-enterprise-authentication-rbac
plan: 03
wave: 3
status: complete
requirements:
  - SSO-03
---

# Phase 30 Plan 03 Summary

Ingress-forwarded mTLS validation is now enforced as a fail-closed request middleware.

## What Changed

- Added `src/anonreq/middleware/mtls.py` with:
  - trusted proxy CIDR checks
  - forwarded certificate decoding and validation
  - normalized machine principal projection into `request.state.machine_principal`
  - fail-closed JSON responses for untrusted, missing, or malformed forwarded certs
- Registered `IngressMTLSMiddleware` in `src/anonreq/main.py`.
- Reused the existing certificate parsing / fingerprinting helpers in the proxy TLS path.

## Verification

- `uv run pytest tests/unit/middleware/test_mtls_ingress.py tests/integration/test_mtls_proxy_forwarding.py -q`

## Result

- Only trusted ingress sources can forward client certificate material.
- Missing or malformed forwarded certs are rejected before route logic runs.
- Valid forwarded certs populate a normalized machine-auth principal.
