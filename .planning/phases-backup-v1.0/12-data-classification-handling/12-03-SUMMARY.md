---
phase: 12-data-classification-handling
plan: 03
subsystem: response-headers
tags: [response-headers, audit-logger, property-tests, hypothesis, integration]
requires:
  - phase: 12-data-classification-handling
    plan: 02
    provides: SensitivityPipelineIntegration
provides:
  - ClassificationResponseMiddleware in response_headers.py to conditionally return results
  - Request audit logs in cleanup.py to log sensitivity metadata
  - Response unit and integration tests in test_classification_response.py
  - Property-based tests in test_classification_property.py
affects:
  - Audit logging structure in cleanup.py
  - HTTP 451 exception handler and blocked body formatting in exceptions.py
tech-stack:
  added: []
  patterns:
    - Conditional response header middleware
    - PII-free structured audit logging
key-files:
  created:
    - src/anonreq/middleware/response_headers.py
    - tests/test_classification_response.py
  modified:
    - src/anonreq/main.py
    - src/anonreq/routing/chat.py
    - src/anonreq/pipeline/cleanup.py
    - src/anonreq/exceptions.py
    - src/anonreq/middleware/classification.py
key-decisions:
  - "Extract ProcessingContext from request.state.ctx in middleware/handlers for error details"
  - "Assert EMAIL_ADDRESS instead of EMAIL to match exact Presidio entity classifications"
patterns-established:
  - "Hypothesis property-based statistics verification"
requirements-completed:
  - CLASS-05
duration: 20min
completed: 2026-07-04
status: complete
---

# Phase 12 Plan 03: Response Headers, Audit, and Property Tests Summary

**Conditional response headers, structured audit classification fields, blocked error response formats, and property tests**

## Performance

- **Duration:** 20 min
- **Started:** 2026-07-04T11:00:00Z
- **Completed:** 2026-07-04T11:20:00Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- **Conditional Response Headers**: Created `ClassificationResponseMiddleware` to check for `X-AnonReq-Return-Classification: true` and write the JSON-encoded `X-AnonReq-Classification-Result` header containing highest level, labels, and override status.
- **Detailed Error Bodies for HTTP 451**: Customized `http_exception_handler` and `ClassificationMiddleware` to serialize the classification details on blocked requests.
- **Sensitivity Audit Logging**: Updated `CleanupStage._build_audit_entry` to write PII-free metadata (`classification_level`, `classification_labels`, `classification_client_override`, and `classification_client_asserted_level`) to request completion log messages.
- **Robust Mocks**: Aligned mock presidio client responses with list-of-lists structures required for concurrent text node analysis in unit and response tests.
- **Comprehensive Property-based Tests**: Confirmed ordinal monotonicity, determinism, client assertion increase, and unknown entity crash safety via Hypothesis strategies (500 iterations per test).

## Files Created/Modified

- `src/anonreq/middleware/response_headers.py` — Created for conditional result headers.
- `src/anonreq/pipeline/cleanup.py` — Updated request completion logs with classification fields.
- `src/anonreq/exceptions.py` — Added classification details to HTTP 451 handlers.
- `src/anonreq/middleware/classification.py` — Added classification details to middleware-level block responses.
- `tests/test_classification_response.py` — Created unit and integration tests for headers and block bodies.
