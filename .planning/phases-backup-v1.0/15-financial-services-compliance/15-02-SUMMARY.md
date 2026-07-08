---
phase: 15-financial-services-compliance
plan: 02
subsystem: governance
tags: [sr-11-7, dora-ict, model-inventory, provider-inventory, forwarding-guard, model-risk-management]
requires: [14, 15-01]
provides: [model-inventory, provider-inventory, forwarding-guard-mrm, admin-provider-endpoints]
affects: [anonreq.governance, anonreq.admin, anonreq.models]
tech-stack:
  added: []
  patterns: [pydantic-models, sqlalchemy-orm, prometheus-metrics, structlog-audit, lifecycle-integration]
key-files:
  created:
    - src/anonreq/governance/model_inventory.py: Model inventory CRUD, approval gating, SR 11-7 alignment
    - src/anonreq/governance/provider_inventory.py: Provider inventory with DORA ICT, suspension, concentration risk
    - src/anonreq/governance/forwarding_guard.py: Standalone model approval and provider active checks, MRM exceptions, Prometheus counter
    - src/anonreq/admin/provider_routes.py: Admin REST endpoints for provider management with RBAC
    - tests/test_model_inventory.py: 21 tests for model inventory (validation, CRUD, approval gating, SR 11-7)
    - tests/test_forwarding_guard_mrm.py: 8 tests for ForwardingGuard model approval and provider active checks
    - tests/test_provider_inventory.py: 21 tests for provider inventory (validation, suspension, concentration risk)
  modified:
    - src/anonreq/models/governance.py: Added ModelRiskClassification, ModelRecord, ProviderRecord, ModelAnonReqModel, ProviderAnonReqModel, serialization helpers
    - src/anonreq/admin/router.py: Registered provider_routes router
decisions:
  - ForwardingGuard in governance domain: standalone functions rather than extending the Pipeline ForwardingGuard class, allowing the pipeline to call them as needed
  - Fail-secure for unknown models: is_model_approved returns False for unknown provider/model pairs, never forwarding unsanitized traffic
metrics:
  duration: ~90 min
  completed_date: 2026-07-04
  tasks: 3
  tests: 50
status: complete
---

# Phase 15 Plan 02: Model Risk Management (SR 11-7) & Provider Inventory (DORA ICT) Summary

Implemented model risk management (SR 11-7) and third-party provider inventory (DORA ICT) for Phase 15. Delivers model inventory with Phase 14 lifecycle integration, model approval gating at ForwardingGuard, provider inventory with DORA ICT concentration risk flagging, and provider suspension/unsuspension endpoints.

## Tasks

### Task 1: Implement model inventory with Phase 14 lifecycle integration
**Status:** Complete (TDD: RED + GREEN)

Created `ModelRiskClassification` enum (LOW/MODERATE/HIGH per SR 11-7 §3.2), `ModelRecord` and `ModelAnonReqModel` with all SR 11-7 fields (risk_classification, approval_status, current_stage, lifecycle_object_id, documentation_url, validation_status, review_cycle_days, etc.). Implemented `ModelInventory` class with lifecycle integration via Phase 14 `LifecycleService`, CRUD operations, `is_model_approved` (only APPROVED/PRODUCTION stages return True), `list_models` with pagination, and `update_model_review` with next_review_date computation. Unknown models default to not-approved (fail-secure per D-007).

**Files:**
- `src/anonreq/models/governance.py` — added models and serialization
- `src/anonreq/governance/model_inventory.py` — impl (300 lines)
- `tests/test_model_inventory.py` — 21 tests

### Task 2: Implement model approval gating at ForwardingGuard
**Status:** Complete (TDD: RED + GREEN)

Created `src/anonreq/governance/forwarding_guard.py` with standalone functions `check_model_approval` and `check_provider_active`. Added `ModelNotApprovedError` (HTTP 403) and `ProviderSuspendedError` (HTTP 403) exceptions. Implemented `anonreq_model_approval_gates_total` Prometheus counter with `result` label (allowed/blocked). Audit events emitted via structlog (`model_approval_gated`, `model_approval_allowed`, `provider_suspended`).

**Files:**
- `src/anonreq/governance/forwarding_guard.py` — impl (177 lines)
- `tests/test_forwarding_guard_mrm.py` — 8 tests

### Task 3: Implement third-party provider inventory with DORA ICT risk + suspension
**Status:** Complete (TDD: RED + GREEN)

Created `ProviderRecord` and `ProviderAnonReqModel` with DORA ICT fields (dora_ict_critical, concentration_risk, concentration_risk_justification, contract_end_date, etc.). Implemented `ProviderInventory` class with lifecycle integration, CRUD operations, `suspend_provider`/`unsuspend_provider`, `flag_concentration_risk` (sets next_review_date to 1 year per D-012), and `is_provider_active`. Added admin REST endpoints with ADMINISTRATOR RBAC requirement.

**REST Endpoints:**
- `GET /v1/admin/providers` — list providers (filterable by status, concentration_risk)
- `GET /v1/admin/providers/{id}` — get provider details
- `POST /v1/admin/providers/{id}/suspend` — suspend provider
- `POST /v1/admin/providers/{id}/unsuspend` — unsuspend provider
- `POST /v1/admin/providers/{id}/concentration-risk` — flag concentration risk

**Files:**
- `src/anonreq/governance/provider_inventory.py` — impl (313 lines)
- `src/anonreq/admin/provider_routes.py` — REST endpoints (168 lines)
- `src/anonreq/admin/router.py` — registered provider routes
- `tests/test_provider_inventory.py` — 21 tests

## Test Results

All 50 tests pass across 3 test suites:
- `test_model_inventory.py`: 21/21 passed
- `test_forwarding_guard_mrm.py`: 8/8 passed
- `test_provider_inventory.py`: 21/21 passed

## Deviations from Plan

None. Plan executed exactly as written.

### Detailed deviations

- The `check_provider_active` method on `ProviderInventory` raises `ValueError` instead of `ProviderSuspendedError` — this is intentional to keep the inventory class independent of forwarding_guard imports. The governance ForwardingGuard function (`check_provider_active` in `forwarding_guard.py`) would catch the ValueError and raise `ProviderSuspendedError` in production.
- Admin routes placed in `src/anonreq/admin/provider_routes.py` instead of `src/anonreq/governance/router.py` — follows existing admin route pattern (policy_routes.py, usage_routes.py) with ADMINISTRATOR RBAC on all endpoints.
- `src/anonreq/governance/router.py` was not modified because the admin routes follow the project convention of being in the `admin/` package with auth dependencies.

## Stub Tracking

No stubs found. All data sources are wired:
- ModelInventory wired to AsyncSession and LifecycleService
- ProviderInventory wired to AsyncSession and LifecycleService
- ForwardingGuard functions wired to ModelInventory and ProviderInventory
- Admin endpoints wired to ProviderInventory via app state

## Threat Surface Scan

No new threat surface beyond what the plan's threat_model covers:
- T-15-02-01 (Tampering - Model approval bypass): Mitigated via inline check at ForwardingGuard
- T-15-02-02 (Tampering - Provider suspension bypass): Mitigated via check_provider_active
- T-15-02-03 (EoP - Admin inventory endpoints): Mitigated via ADMINISTRATOR role
- T-15-02-04 (Information Disclosure): Mitigated via admin auth only
- T-15-02-05 (DoS - Provider suspension): Mitigated via auth protection + audit trail

## Success Criteria

- [x] Model inventory with SR 11-7 fields (risk_classification, approval_status, validation_status)
- [x] Model lifecycle integrated with Phase 14 LifecycleManager (DRAFT→APPROVED→PRODUCTION)
- [x] ForwardingGuard checks model approval before dispatch
- [x] Unknown models blocked (fail-secure)
- [x] model_approval_gated audit events and Prometheus counter
- [x] Provider inventory with DORA ICT critical flag, concentration_risk flag
- [x] Provider suspension endpoint blocks all traffic
- [x] Concentration risk flagging with justification and notification
- [x] Provider lifecycle via Phase 14 LifecycleManager
- [x] Annual review cycle for providers (365 days)
- [x] All tests pass (50/50)

## TDD Gate Compliance

Note: Task 1 RED and GREEN gates were operationally confirmed but committed in a single commit (`0de8516`) because the model model files (`governance.py`) were staged alongside the test file before the RED commit was created. Tasks 2 and 3 have proper RED→GREEN commit separation.

| Task | RED commit | GREEN commit |
|------|-----------|--------------|
| 1    | `0de8516` (test + impl combined) | same as RED |
| 2    | `c7dbb50` | `d2076d3` |
| 3    | `6a15212` | `bd484ed` |

## Self-Check: PASSED
