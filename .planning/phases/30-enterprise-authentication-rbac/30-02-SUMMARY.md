---
phase: 30-enterprise-authentication-rbac
plan: 02
wave: 2
status: complete
requirements:
  - SSO-02
---

# Phase 30 Plan 02 Summary

The RBAC vocabulary is now normalized around the enterprise role set.

## What Changed

- Updated `src/anonreq/middleware/rbac.py` so the canonical lowest-privilege role is `read_only_auditor`.
- Kept compatibility for legacy injected principals by normalizing `read_only` to `read_only_auditor`.
- Updated admin route decorators in:
  - `src/anonreq/admin/compliance_routes.py`
  - `src/anonreq/admin/incident_routes.py`
  - `src/anonreq/admin/aml_webhook_routes.py`
- Kept the existing hierarchy and fail-closed `require_role()` contract intact.

## Verification

- `uv run pytest tests/admin/test_rbac.py tests/unit/admin/test_role_normalization.py tests/integration/test_admin_role_enforcement.py -q`

## Result

- Enterprise role names are now the canonical vocabulary.
- The role hierarchy still enforces 401/403 correctly.
- Admin-only routes now declare the correct minimum role with enum constants instead of string literals.
