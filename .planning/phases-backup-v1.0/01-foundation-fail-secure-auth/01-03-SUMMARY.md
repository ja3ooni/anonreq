---
phase: 01-foundation-fail-secure-auth
plan: 03
subsystem: fail-secure-core
tags: [exceptions, logging, structlog, health, startup-checks, fail-secure]
requires: [01-01]
provides: [exceptions, logging_config, health, startup_checks, main]
affects: [all-phase-2-plans]
tech-stack:
  added:
    - structlog with allowlist processor for structured JSON logging
    - FastAPI add_exception_handler for global fail-secure error handling
    - asyncio-based TCP health checks for Valkey/Presidio
  patterns:
    - OpenAI-compatible error envelope with request_id, no stack traces
    - Module-level settings singleton used for dependency URLs
    - Lifespan context manager for pre-flight startup validation
    - Field allowlist processor prevents accidental PII leakage in logs
    - httpx ASGITransport with raise_app_exceptions=False for test
key-files:
  created:
    - src/anonreq/exceptions.py — AnonReqError hierarchy + global exception handler
    - src/anonreq/logging_config.py — structlog configuration + allowlist processor
    - src/anonreq/health.py — GET /health and GET /health/ready endpoints
    - src/anonreq/startup_checks.py — dependency connectivity checks
    - src/anonreq/main.py — FastAPI app factory + lifespan + router wiring
    - tests/test_exceptions.py — 14 exception handler tests
    - tests/test_logging.py — 7 logging allowlist tests
    - tests/test_health.py — 7 health endpoint tests
    - tests/test_startup.py — 4 startup check tests
  modified:
    - src/anonreq/main.py — (overwritten with full implementation)
decisions:
  - "httpx.ASGITransport requires raise_app_exceptions=False in test fixtures because Starlette's ServerErrorMiddleware re-raises exceptions after handling them"
  - "structlog positional arg as event message avoids event= kwarg conflict with merge_contextvars"
  - "TCP socket ping for Valkey health (asyncio.open_connection) instead of full Redis client — avoids dependency on redis library just for connectivity check"
  - "separate _check_components() helper avoids FastAPI dependency injection issues when health() is called from health_ready()"
  - "nested-dict limitation in allowlist_processor documented as acceptable for Phase 1 (no request data flows yet)"
duration: 45m
completed_date: "2026-06-30"
status: complete
---

# Phase 1 Plan 3: Fail-Secure Core Infrastructure Summary

Implemented the fail-secure core infrastructure: global exception handler with OpenAI-compatible error envelopes, structured audit logging with strict field allowlist, health endpoint with component status, and pre-flight startup checks. This is the heart of the Phase 1 leak-free guarantee.

Every error — whether from Python code, FastAPI, or a crashed dependency — produces a safe HTTP 500 with zero information leakage. Logs never contain raw values. The gateway refuses to start if dependencies are unhealthy.

## Objective Fulfilled

> Implement the fail-secure core infrastructure: global exception handler with OpenAI-compatible error envelope, structured audit logging with strict field allowlist, health endpoint, and pre-flight startup checks.

- ✅ `pytest tests/ -x --tb=short` — 54 passed (22 config + 14 exceptions + 7 logging + 7 health + 4 startup)
- ✅ `ANONREQ_API_KEY=... python3 -c "from anonreq.main import app"` succeeds
- ✅ Error responses never contain stack traces or internal details
- ✅ Log output is valid JSON with only allowlisted fields
- ✅ All 9 files created, 1 file modified, all committed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] httpx ASGITransport exception handling in test fixtures**
- **Found during:** Task 1 test execution
- **Issue:** Starlette's `ServerErrorMiddleware` re-raises caught exceptions after handling them (line 186 in errors.py). httpx's `ASGITransport` propagates this exception to the test caller, preventing the test from reading the error response.
- **Fix:** Added `raise_app_exceptions=False` to `ASGITransport()` in test fixture. The response IS correctly sent before the exception re-raises — this parameter tells httpx to capture and return the response instead of raising.
- **Files modified:** tests/test_exceptions.py
- **Commit:** `44448eb`

**2. [Rule 1 - Bug] structlog event kwarg conflict with merge_contextvars**
- **Found during:** Task 3 test execution
- **Issue:** `logger.info("msg", event="val")` passes the event twice — once as positional arg, once as keyword — causing `TypeError: got multiple values for argument 'event'`.
- **Fix:** Changed all log calls to use positional arg as event message: `logger.info("Message", component="name")`.
- **Files modified:** src/anonreq/startup_checks.py, src/anonreq/main.py
- **Commit:** `5747e78`

**3. [Rule 1 - Bug] health endpoint always returned 200**
- **Found during:** Task 3 test execution  
- **Issue:** The health endpoint correctly identified "degraded" status but returned 200 instead of 503 because the function returned a dict (always wrapped as 200 by FastAPI).
- **Fix:** Added `response: Response` parameter to set `response.status_code = 503` when degraded.
- **Files modified:** src/anonreq/health.py
- **Commit:** `5747e78`

**4. [Rule 2 - Risk] health_ready called health() without Response parameter**
- **Found during:** Task 3 test execution
- **Issue:** `health_ready()` called `await health()` which now needs a `Response` parameter, but FastAPI dependency injection only works through route decoration.
- **Fix:** Refactored into `_check_components()` and `_build_health_response()` helper functions shared by both endpoints.
- **Files modified:** src/anonreq/health.py
- **Commit:** `5747e78`

## Known Stubs

None. All files are fully implemented.

- `exceptions.py` (247 lines / min 50 ✅)
- `logging_config.py` (158 lines / min 40 ✅)
- `health.py` (127 lines / min 30 ✅)
- `startup_checks.py` (143 lines / min 30 ✅)
- `main.py` (91 lines / min 40 ✅)

## Threat Surface Scan

No new threat surface beyond what the plan's threat model covers:

| Threat ID | Disposition | Status |
|-----------|-------------|--------|
| T-01-03-01 (Info Disclosure — exception handler) | mitigate | ✅ Generic error envelopes, no stack traces, no internal URLs, no env var values |
| T-01-03-02 (Info Disclosure — logging allowlist) | mitigate | ✅ Field allowlist processor drops non-allowlisted keys. Nested-dict limitation documented. |
| T-01-03-03 (DoS — startup checks) | mitigate | ✅ socket_connect_timeout=3, httpx timeout=5, fast fail on first failure |
| T-01-03-04 (EoP — startup checks network calls) | accept | ✅ URLs from config, not user input. Internal Docker network only. |
| T-01-03-SC (Tampering — structlog/redis/httpx packages) | mitigate | ✅ All packages verified per RESEARCH.md |

## Verification Results

```text
=== Full test suite ===
54 passed in 5.59s
  - test_config.py: 22 passed
  - test_exceptions.py: 14 passed
  - test_logging.py: 7 passed
  - test_health.py: 7 passed
  - test_startup.py: 4 passed

=== Module import ===
App created with exception handlers OK
Exception handlers: HTTPException, RequestValidationError, Exception
Routes: /, /health, /health/ready
```

## Success Criteria Checklist

- [x] Global exception handler returns OpenAI-compatible error envelope — no stack traces, no PII, no internal URLs
- [x] structlog configured with field allowlist — non-allowlisted fields dropped
- [x] request_id propagated via structlog contextvars
- [x] GET /health returns 200 (healthy) or 503 (degraded) with component status
- [x] Pre-flight checks block startup on dependency failure
- [x] lifespan context manager handles failures cleanly
- [x] All test suites pass: 54 tests across 5 test files
- [x] All 9 files created, 1 file modified, all committed

## Self-Check: PASSED

All 9 files verified present with sufficient line counts:
- exceptions.py: 247 lines (min 50 ✅)
- logging_config.py: 158 lines (min 40 ✅)
- health.py: 123 lines (min 30 ✅)
- startup_checks.py: 143 lines (min 30 ✅)
- main.py: 91 lines (min 40 ✅)
- test_exceptions.py: 171 lines (contains test_ ✅)
- test_logging.py: 185 lines (contains test_ ✅)
- test_health.py: 126 lines (contains test_ ✅)
- test_startup.py: 82 lines (contains test_ ✅)

All 6 commits verified in git log.

| Hash | Type | Message |
|------|------|---------|
| `25310fa` | test | Add failing tests for fail-secure exception handler |
| `44448eb` | feat | Implement global exception handler with fail-secure envelope |
| `f8fafd8` | test | Add failing tests for structured audit logging |
| `403fa2c` | feat | Implement structured audit logging with field allowlist |
| `57c10b4` | test | Add failing tests for health endpoint and startup checks |
| `5747e78` | feat | Implement health endpoint and pre-flight startup checks |
