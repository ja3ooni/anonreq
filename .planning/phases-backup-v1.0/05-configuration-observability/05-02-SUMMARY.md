---
phase: 05
plan: 02
subsystem: verification-admin
tags:
  - post-restoration-scanner
  - hot-reload-admin
  - atomic-config-registry
  - verification
  - admin-api
depends:
  requires: [05-01]
  provides: [08-01, 08-03, 09-01]
  affects: [pipeline/detection, routing, main]
tech-stack:
  added: [re (stdlib), threading.Lock, FastAPI Header, prometheus_client]
  patterns: [TDD, AtomicConfigRegistry singleton, module-level registry]
key-files:
  created:
    - src/anonreq/verification/scanner.py
    - src/anonreq/verification/stages.py
    - src/anonreq/admin/__init__.py
    - src/anonreq/admin/auth.py
    - src/anonreq/admin/config.py
    - src/anonreq/admin/routes.py
    - tests/unit/verification/test_scanner.py
    - tests/unit/admin/test_config_registry.py
    - tests/unit/admin/test_validation.py
    - tests/integration/test_scan_stages.py
    - tests/integration/test_admin_rules.py
    - tests/integration/test_hot_reload.py
  modified:
    - src/anonreq/config.py
    - src/anonreq/models/processing_context.py
    - src/anonreq/pipeline/detection.py
    - src/anonreq/main.py
    - src/anonreq/routing/chat.py
    - .env.example
decisions:
  - "ResponseScanner as standalone class (not stage) — reused across both scan stages"
  - "AtomicConfigRegistry module-level singleton injected into DetectionStage — no notification channel needed for MVP"
  - "GET /v1/config/ruses uses gateway auth (not admin key) — config metadata is safe to expose to all authenticated clients"
  - "validate_and_swap returns (bool, str | None) tuple — error message enables precise logging of why a config was rejected"
metrics:
  duration: 10m
  commits: 6
  files_changed: 20
  tests_added: 64
  completed_date: 2026-07-02
status: complete
---

# Phase 5 Plan 2: Post-Restoration Verification & Hot-Reload Admin

## One-liner

Implements post-restoration verification scanner (ResponseScanner, ScanStage, StreamScanStage) and a hot-reload admin API (AtomicConfigRegistry, admin auth, CRUD routes) with custom recognizer injection into the detection pipeline.

## Objective

Provide operational safety (AG-16: fail-secure, AG-17: warn-only scans) and runtime configurability (D-152: hot-reload) for the AnonReq gateway. Post-restoration verification scans LLM responses for residual `[TYPE_N]` tokens that were not restored, exposing them as a Prometheus counter. The admin API enables operators to add custom PII recognizers, adjust confidence thresholds, and manage exclusion lists without restarting the gateway.

## Tasks Executed

| # | Type | Name | Commit | Files |
|---|------|------|--------|-------|
| 1 | TDD | ResponseScanner, ScanStage, StreamScanStage | `fe8c808` (RED), `c57118e` (GREEN) | `verification/scanner.py`, `verification/stages.py`, `models/processing_context.py`, unit + integration tests |
| 2 | TDD | AtomicConfigRegistry, admin auth, API routes | `ba07eb0` (RED), `dff7ff9` (GREEN) | `admin/config.py`, `admin/auth.py`, `admin/routes.py`, `config.py`, unit + integration tests |
| 3 | auto | Wire config_registry into DetectionStage, register admin_router, .env.example | `c35fb98`, `8a0844b` | `pipeline/detection.py`, `main.py`, `routing/chat.py`, `.env.example`, hot-reload integration test |

## TDD Gate Compliance

RED and GREEN gate commits verified for both TDD tasks:
- Task 1: `fe8c808` (test) → `c57118e` (feat) — correct ordering
- Task 2: `ba07eb0` (test) → `dff7ff9` (feat) — correct ordering

## Verification Results

All 64 new tests pass. Existing passing tests unaffected.

- `tests/unit/verification/test_scanner.py` — 16/16 passed
- `tests/unit/admin/test_config_registry.py` — 14/14 passed
- `tests/unit/admin/test_validation.py` — 8/8 passed
- `tests/integration/test_scan_stages.py` — 11/11 passed
- `tests/integration/test_admin_rules.py` — 7/7 passed
- `tests/integration/test_hot_reload.py` — 8/8 passed

## Success Criteria Verification

| # | Criterion | Status |
|---|-----------|--------|
| 1 | All existing tests still pass | ✅ (no changes to pre-existing test files) |
| 2 | New tests pass (scanner, provider, registry, validation, e2e, hot-reload) | ✅ 64/64 |
| 3 | No PII in fixture data | ✅ All test data uses example.com, test.com, synthetic data |
| 4 | All tests run without Presidio/Valkey for unit tests | ✅ conftest patches, mocked clients |
| 5 | Admin API key env var is optional (defaults None → 401) | ✅ `ADMIN_API_KEY: str | None = None` |
| 6 | Invalid config never replaces active config (AG-16) | ✅ `validate_and_swap` returns `(False, error_msg)` |
| 7 | Scan stages are warn-only, never modify response (AG-17) | ✅ Tests verify response unchanged, tokens-only counter |
| 8 | admin_router registered in main.py with gateway auth | ✅ `app.include_router(admin_router, dependencies=[Depends(auth_context)])` |
| 9 | Detection pipeline injects custom patterns via config_registry | ✅ Hot-reload test proves custom entity detected |
| 10 | .env.example includes ANONREQ_ADMIN_API_KEY | ✅ |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed span assertion in hot-reload integration test**
- **Found during:** Task 3 (hot-reload test)
- **Issue:** The test asserted `start == 10` but the actual span starts at index 9 for "ORD-123456" in "My order ORD-123456 was confirmed..."
- **Fix:** Corrected start/end values to match actual offsets
- **Files modified:** `tests/integration/test_hot_reload.py`
- **Commit:** `c35fb98`

**2. [Rule 3 - Missing] Added `config_registry` parameter to `DetectionStage.__init__`**
- **Found during:** Task 3 (wiring)
- **Issue:** The plan specified wiring `config_registry` into DetectionStage but the class did not accept it
- **Fix:** Added `config_registry: AtomicConfigRegistry | None = None` parameter and TYPE_CHECKING import
- **Files modified:** `src/anonreq/pipeline/detection.py`
- **Commit:** `c35fb98`

## Threat Flags

None — all new surface (admin POST endpoint, scan counter, config registry) is within the existing auth boundary. No new trust boundaries crossed.

## Key Files

### Created
- `src/anonreq/verification/scanner.py` — ResponseScanner: token pattern matching and scan results
- `src/anonreq/verification/stages.py` — ScanStage (non-streaming) + StreamScanStage (SSE)
- `src/anonreq/admin/config.py` — Domain models + AtomicConfigRegistry with Lock
- `src/anonreq/admin/auth.py` — verify_admin_api_key dependency with optional key
- `src/anonreq/admin/routes.py` — GET /v1/config/rules + POST /v1/admin/config/rules

### Modified
- `src/anonreq/config.py` — Added `ADMIN_API_KEY: str | None = None`
- `src/anonreq/models/processing_context.py` — Added `assembled_response` field
- `src/anonreq/pipeline/detection.py` — Accepts AtomicConfigRegistry for custom pattern injection
- `src/anonreq/main.py` — Registers admin_router with gateway auth
- `src/anonreq/routing/chat.py` — Pipes registry through pipeline construction
- `.env.example` — Added ANONREQ_ADMIN_API_KEY

## Commits

| Hash | Type | Message |
|------|------|---------|
| `fe8c808` | test | add failing test for ResponseScanner and scan stages |
| `c57118e` | feat | implement ResponseScanner, ScanStage, and StreamScanStage |
| `ba07eb0` | test | add failing test for AtomicConfigRegistry and admin API |
| `dff7ff9` | feat | implement AtomicConfigRegistry, admin auth, and API routes |
| `c35fb98` | feat | wire config_registry into DetectionStage and register admin_router |
| `8a0844b` | chore | add ANONREQ_ADMIN_API_KEY to .env.example |

## Self-Check: PASSED

All 20 key files verified on disk. All 6 commits verified in git log. All 64 tests pass.
