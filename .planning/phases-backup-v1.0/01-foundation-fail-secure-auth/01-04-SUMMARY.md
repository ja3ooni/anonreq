---
phase: 01-foundation-fail-secure-auth
plan: 04
subsystem: fail-secure-auth
tags: [auth, bearer-token, request-context, middleware, tdd]
requires: [01-03]
provides: [auth_dependency, request_context, request_id_middleware]
affects: [all-phase-2-plans]
tech-stack:
  added:
    - fastapi.security.HTTPBearer for Bearer token extraction
    - uuid4 from stdlib for request_id generation
  patterns:
    - RequestContext dataclass with auto-generated request_id
    - Composite dependency (auth_context) combining auth + context
    - Middleware sets request_id before auth runs (available in 401 responses)
    - AuthenticationError raised for wrong tokens (not raw HTTPException)
key-files:
  created:
    - src/anonreq/models/request_context.py — RequestContext dataclass
    - src/anonreq/dependencies.py — Auth dependencies and request context
    - tests/test_auth.py — 15 auth and request context tests
  modified:
    - src/anonreq/main.py — Added middleware + auth wiring
decisions:
  - "Composite auth_context dependency combines verify_api_key + get_request_context for clean route signatures"
  - "Middleware sets request_id BEFORE auth runs so 401 responses include it (RESEARCH Open Q4)"
  - "Wrong token raises AuthenticationError (not HTTPException) to flow through global_exception_handler for correct envelope"
  - "HTTPBearer auto_error=True handles missing/malformed headers; verify_api_key handles wrong tokens"
metrics:
  duration: 25m
  completed_date: "2026-06-30"
  tasks: 2
  files: 4
status: complete
---

# Phase 1 Plan 4: Bearer Token Authentication and RequestContext Summary

Implemented static bearer token authentication and the RequestContext layer. Every route requires `Authorization: Bearer <ANONREQ_API_KEY>`. RequestContext propagates request_id, tenant_id, and session_id for correlation across logs, errors, and metrics.

## Objective Fulfilled

> Implement static bearer token authentication and the request context layer. Every route requires `Authorization: Bearer <ANONREQ_API_KEY>` header. RequestContext propagates request_id, tenant_id, and session_id for correlation across logs, errors, and metrics.

- ✅ `pytest -x --tb=short` — 69 passed (54 existing + 15 auth tests)
- ✅ All routes return 401 without valid Bearer token (verified via pytest + manual curl)
- ✅ Wrong/missing token returns 401 with OpenAI-compatible error envelope
- ✅ Auth errors include request_id in response body
- ✅ RequestContext populated with request_id, tenant_id="default" per D-11
- ✅ Middleware sets request_id before auth runs (available in 401 responses)

## Deviations from Plan

None — plan executed exactly as written.

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (test) | `f042c4f` — `test(01-04): add failing auth tests` | ✅ |
| GREEN (feat) | `f509d17` — `feat(01-04): implement auth dependency and request context` | ✅ |
| Task 2 (wire) | `c7bcb93` — `feat(01-04): wire auth into main.py with request_id middleware` | ✅ |

## Known Stubs

None. All files are fully implemented with no placeholder values or empty data flows.

- `request_context.py` (36 lines / min 15 ✅)
- `dependencies.py` (122 lines / min 30 ✅)
- `test_auth.py` (249 lines, 15 tests ✅)

## Threat Surface Scan

No new threat surface beyond what the plan's threat model covers:

| Threat ID | Disposition | Status |
|-----------|-------------|--------|
| T-01-04-01 (Spoofing — verify_api_key) | mitigate | ✅ HTTPBearer validates Authorization header format. Token compared against settings.API_KEY. Wrong/missing token returns 401 before any route handler runs per D-01. |
| T-01-04-02 (Info Disclosure — 401 response) | mitigate | ✅ Auth errors return OpenAI-compatible envelope — no stack traces, no hints about key format |
| T-01-04-03 (Info Disclosure — request_id) | accept | ✅ request_id is random hex, safe in error responses for trace correlation |
| T-01-04-04 (DoS — UUID allocation) | accept | ✅ uuid4() is lightweight (~60ns per call) |
| T-01-04-SC (Tampering — no new packages) | accept | ✅ Plan only uses stdlib (uuid, dataclasses) and existing FastAPI HTTPBearer |

## Verification Results

```text
=== Full test suite ===
69 passed in 0.37s
  - test_auth.py: 15 passed
  - test_config.py: 22 passed
  - test_exceptions.py: 14 passed
  - test_health.py: 7 passed
  - test_logging.py: 7 passed
  - test_startup.py: 4 passed

=== End-to-end auth scenarios ===
- No auth → 401 with OpenAI envelope, request_id present ✅
- Wrong token → 401 with authentication_error type, request_id present ✅
- Valid token → 200 on /health and / ✅
- Missing auth on root / → 401 ✅
```

## Success Criteria Checklist

- [x] All routes return 401 without valid Bearer token
- [x] Wrong Bearer token returns 401 with OpenAI-compatible error envelope
- [x] Valid Bearer token returns 200 on protected routes
- [x] Auth errors include request_id in response body
- [x] RequestContext populated with request_id, tenant_id="default" per D-11
- [x] Middleware sets request_id before auth runs (available in 401 responses)
- [x] All 6 test suites pass: test_config, test_exceptions, test_logging, test_health, test_startup, test_auth
- [x] All files committed to git (3 commits)

## Self-Check: PASSED

All 4 files verified present with sufficient line counts:
- request_context.py: 36 lines (min 15 ✅)
- dependencies.py: 122 lines (min 30 ✅)
- test_auth.py: 249 lines (contains test_ ✅)
- main.py: 111 lines (updated with middleware + auth wiring)

All 3 commits verified in git log:

| Hash | Type | Message |
|------|------|---------|
| `f042c4f` | test | Add failing auth tests |
| `f509d17` | feat | Implement auth dependency and request context |
| `c7bcb93` | feat | Wire auth into main.py with request_id middleware |
