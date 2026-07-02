---
phase: 05-configuration-observability
plan: 01
subsystem: api, monitoring
tags: prometheus, metrics, fastapi, k6, load-testing, middleware
requires:
  - phase: 01-foundation-fail-secure-auth
    provides: FastAPI application, auth middleware, config
  - phase: 02-core-pipeline-classification-non-streaming
    provides: ProcessingContext, DetectionStage, ForwardingGuard, RestorationStage, pipeline orchestration
  - phase: 03-sse-streaming-multi-provider
    provides: ProviderAdapter interface, model alias routing
  - phase: 04-multi-locale-detection-compliance-presets
    provides: LocaleRegistry, RecognizerMerger
provides:
  - Prometheus metrics module with 8 counters/histograms/gauges
  - MetricsMiddleware for request timing and response count on every route
  - Pipeline instrumentation: detection latency, provider dispatch tracking, processing overhead, fail-secure counting
  - GET /metrics endpoint returning Prometheus text format
  - Integration test for /metrics endpoint validating all 8 metric families
  - k6 load test script (benchmark.js) for P95 overhead validation
  - Load test documentation (README.md)
affects: phase 05-02, phase 06, phase 07
tech-stack:
  added:
    - prometheus_client 0.25+ (Prometheus metrics library)
    - prometheus_client.parser (for integration test metric validation)
    - k6 (load testing tool, user-installed)
  patterns:
    - Low-cardinality-only metric labels (AG-15: no PII, no request identifiers)
    - BaseHTTPMiddleware subclass for request timing and label population
    - fail_secure_events_total incremented per failure_type on error paths
    - Processing overhead measured as provider_dispatch_time minus request_receipt_time
    - Metric docstrings describe purpose and label semantics
key-files:
  created:
    - src/anonreq/monitoring/__init__.py
    - src/anonreq/monitoring/metrics.py
    - src/anonreq/monitoring/middleware.py
    - tests/unit/monitoring/__init__.py
    - tests/unit/monitoring/test_metrics.py
    - tests/unit/monitoring/test_middleware.py
    - tests/integration/test_metrics_endpoint.py
    - tests/load/benchmark.js
    - tests/load/README.md
  modified:
    - src/anonreq/models/processing_context.py
    - src/anonreq/pipeline/detection.py
    - src/anonreq/pipeline/forwarding_guard.py
    - src/anonreq/pipeline/restoration.py
    - src/anonreq/main.py
key-decisions:
  - "Low-cardinality labels only — no tenant_id, request_id, session_id in labels (AG-15)"
  - "BaseHTTPMiddleware subclass for metrics middleware (not pure ASGI) — simpler API, FastAPI-compatible"
  - "Unrestored tokens counter uses entity_type label (not endpoint) — tracks residual per entity type"
  - "ForwardingGuard sets provider_dispatch_time before early PASS return — PASS branches skip provider dispatch"
  - "Prometheus /metrics endpoint is unauthenticated for MVP — scraped on internal network (T-05-01-01)"
  - "k6 load test measures total round-trip; overhead derived from anonreq_processing_overhead_ms metric"
  - "Non-streaming load test only in MVP (D-158) — streaming deferred to Phase 6+"
patterns-established:
  - "Pipeline stage instrumentation pattern: each stage imports and updates relevant metrics after its core work"
  - "Fail-secure metric pattern: fail_secure_events_total incremented per failure_type on every error return path"
  - "Timing chain: request_receipt_time (middleware) → provider_dispatch_time (ForwardingGuard) → processing_overhead_ms (RestorationStage)"
  - "Metric resilience: all metric accesses use safe getattr defaults to avoid crashing on missing request.state attributes"
requirements-completed:
  - METR-03
  - PIPE-06
duration: 47min
completed: 2026-07-02
status: complete
---

# Phase 5 Plan 1: Prometheus Metrics and Pipeline Instrumentation

**8 Prometheus metrics (counters, histograms, gauge) with FastAPI middleware for request timing, pipeline instrumentation for detection/restoration overhead, GET /metrics endpoint returning Prometheus text format, and k6 load test script for P95 overhead validation**

## Performance

- **Duration:** 47 min
- **Started:** 2026-07-02T07:08:53Z
- **Completed:** 2026-07-02T07:55:47Z
- **Tasks:** 3 (all auto, 2 with TDD)
- **Files modified:** 13

## Accomplishments

- Created Prometheus metrics module (`metrics.py`) with all 8 metric families per D-139: `requests_total`, `detection_latency_ms`, `entities_detected_total`, `unrestored_tokens_total`, `fail_secure_events_total`, `audit_failures_total`, `processing_overhead_ms`, `active_config_version`
- Implemented `MetricsMiddleware` (BaseHTTPMiddleware subclass) — records `request_receipt_time` on request start, increments `requests_total` with endpoint/status_code/provider/classification labels on response
- Instrumented `DetectionStage.execute()` — records `detection_latency_ms` histogram, increments `entities_detected` counter per entity_type/locale, increments `fail_secure_events_total` on detection failure
- Instrumented `ForwardingGuard.execute()` — sets `provider_dispatch_time` on ProcessingContext, increments `fail_secure_events_total` on forwarding denial
- Instrumented `RestorationStage.execute()` — calculates `processing_overhead_ms`, records `processing_overhead` histogram, increments `unrestored_tokens` per entity_type, increments `fail_secure_events_total` on restoration failure
- Wired `GET /metrics` endpoint returning all 8 metric families in Prometheus text format
- Added integration test (`test_metrics_endpoint.py`) validating endpoint behavior and metric output
- Created k6 load test script (`benchmark.js`) with configurable concurrency, prompt size, and duration
- Added load test documentation (`tests/load/README.md`) with interpretation guide and target thresholds
- All 58 tests pass (52 unit + 6 integration)

## Task Commits

Each task was committed atomically with TDD RED/GREEN phases:

1. **Task 1: Create Prometheus metrics module** (TDD)
   - `391851b` — `test(05-01): add failing tests for Prometheus metrics module` (RED)
   - `e4d7641` — `feat(05-01): implement Prometheus metrics module with 8 metric definitions` (GREEN)

2. **Task 2: Implement metrics middleware and instrument pipeline stages** (TDD)
   - `4d6c53c` — `test(05-01): add failing tests for middleware and pipeline instrumentation` (RED)
   - `a128c65` — `feat(05-01): implement MetricsMiddleware and pipeline instrumentation` (GREEN)

3. **Task 3: Wire /metrics endpoint and create k6 load test**
   - `5eb3c1c` — `feat(05-01): wire /metrics endpoint and MetricsMiddleware in FastAPI`
   - `acf2602` — `test(05-01): add integration test for /metrics endpoint and k6 load test script`

**Plan metadata:** (committed in final docs commit)

## Files Created/Modified

### Created
- `src/anonreq/monitoring/__init__.py` — Package init
- `src/anonreq/monitoring/metrics.py` — 8 Prometheus metric definitions (Counter, Histogram, Gauge)
- `src/anonreq/monitoring/middleware.py` — MetricsMiddleware (BaseHTTPMiddleware subclass)
- `tests/unit/monitoring/__init__.py` — Test package init
- `tests/unit/monitoring/test_metrics.py` — 34 tests for metric types, labels, buckets, docstrings, AG-15 compliance
- `tests/unit/monitoring/test_middleware.py` — 18 tests for middleware, pipeline instrumentation, and fail-secure paths
- `tests/integration/test_metrics_endpoint.py` — 6 integration tests for /metrics endpoint
- `tests/load/benchmark.js` — k6 load test script for P95 overhead validation
- `tests/load/README.md` — Load test documentation and interpretation guide

### Modified
- `src/anonreq/models/processing_context.py` — Added `request_receipt_time`, `provider_dispatch_time`, `processing_overhead_ms` fields
- `src/anonreq/pipeline/detection.py` — Instrumented with detection_latency histogram, entities_detected counter, fail_secure_events counter
- `src/anonreq/pipeline/forwarding_guard.py` — Instrumented with provider_dispatch_time, fail_secure_events counter
- `src/anonreq/pipeline/restoration.py` — Instrumented with processing_overhead histogram, unrestored_tokens counter, fail_secure_events counter
- `src/anonreq/main.py` — Added MetricsMiddleware via `app.add_middleware()`, added GET /metrics endpoint

## TDD Gate Compliance

- **RED gates present:** Yes (`test(05-01): add failing tests for Prometheus metrics module`, `test(05-01): add failing tests for middleware and pipeline instrumentation`)
- **GREEN gates present:** Yes (`feat(05-01): implement Prometheus metrics module...`, `feat(05-01): implement MetricsMiddleware and pipeline instrumentation`)
- **REFACTOR gates:** Not needed — no post-GREEN cleanup was required

## Decisions Made

- **unrestored_tokens label changed to entity_type** — The plan specified `endpoint` label per D-139, but unrestored tokens are tracked per entity type (the specific residual token type post-restoration), not per endpoint. Using `entity_type` provides more actionable monitoring.
- **ForwardingGuard timing set before early PASS** — `provider_dispatch_time` must be set before the PASS/ANONYMIZE branch decisions, because the PASS branch early-returns and would skip the provider dispatch entirely. Setting it early ensures overhead calculation always has the reftime.
- **BaseHTTPMiddleware for metrics middleware** — Used instead of pure ASGI middleware for simpler FastAPI integration, proper `Request` parameter handling, and clean `dispatch/response` lifecycle.
- **No auth on /metrics endpoint** — Prometheus scrapers connect on internal networks; bearer token auth would complicate scraper configuration. Documented in threat model (T-05-01-01) with future recommendation for mTLS or network policy.
- **k6 measures total round-trip, overhead from Prometheus** — Per D-156, k6 measures total latency (including provider time). Gateway overhead is derived from `anonreq_processing_overhead_ms` histogram, not k6 response duration.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `from __future__ import annotations` breaks FastAPI Request injection in test route handlers**
- **Found during:** Task 2 (middleware testing — route handlers returning 422)
- **Issue:** `from __future__ import annotations` converts all annotations to strings, making `request: Request` in route handlers a string annotation that FastAPI cannot use for dependency injection. FastAPI treats `request` as a query parameter instead, returning 422 Validation Error.
- **Fix:** Removed `from __future__ import annotations` from the test file. The middleware file retains it (safe — BaseHTTPMiddleware `dispatch` method is overridden, not injected).
- **Files modified:** `tests/unit/monitoring/test_middleware.py`
- **Verification:** All 18 middleware tests pass after fix
- **Committed in:** `a128c65` (Task 2 GREEN commit)

**2. [Rule 1 - Data Integrity] `unrestored_tokens` label corrected from `endpoint` to `entity_type`**
- **Found during:** Task 1 (metric design review during implementation)
- **Issue:** Plan specified `endpoint` label for `unrestored_tokens` counter per D-139. However, `unrestored_tokens` tracks residual tokens by entity type (PERSON, EMAIL, PHONE, etc.) post-restoration, not by endpoint. Using `endpoint` would create misleading high-cardinality labels and provide no actionable entity-type-level insight.
- **Fix:** Changed label to `entity_type` in metric definition, instrumentation (RestorationStage), and tests.
- **Files modified:** `src/anonreq/monitoring/metrics.py`, `src/anonreq/pipeline/restoration.py`, `tests/unit/monitoring/test_metrics.py`, `tests/unit/monitoring/test_middleware.py`
- **Verification:** All metric label assertions updated; tests confirm entity_type label is correct
- **Committed in:** `a128c65` (Task 2 GREEN commit)

**3. [Rule 2 - Missing Critical] ForwardingGuard must set provider_dispatch_time before early PASS return**
- **Found during:** Task 2 (ForwardingGuard instrumentation review)
- **Issue:** The PASS verification path at the top of `ForwardingGuard.execute()` returns early with `GuardResult.PASS` before reaching the instrumentation that sets `ctx.provider_dispatch_time`. When the provider_dispatch_time is never set, `processing_overhead_ms` calculation in RestorationStage gets `None` and produces no overhead metric for PASS-through requests (no PII detected).
- **Fix:** Moved `ctx.provider_dispatch_time = time.monotonic()` to the beginning of `ForwardingGuard.execute()`, before both the PASS check and the ANONYMIZE check.
- **Files modified:** `src/anonreq/pipeline/forwarding_guard.py`
- **Verification:** Test `test_records_provider_dispatch_time` passes (verifies dispatch_time is set even on PASS branch)
- **Committed in:** `a128c65` (Task 2 GREEN commit)

**4. [Rule 3 - Blocking] `tests/integration/__init__.py` and `tests/load/` already existed from prior phases**
- **Found during:** Task 3 (file creation)
- **Issue:** Plan specified creating `tests/integration/__init__.py` and implied creating `tests/load/` directory. Both already existed from Phase 4/Phase 3 work.
- **Fix:** Skipped creating these files/directories. Content added to existing locations.
- **Verification:** Integration test imports work correctly
- **Committed in:** `acf2602` (Task 3 commit)

---

**Total deviations:** 4 auto-fixed (2 Rule 1 bugs, 1 Rule 2 missing critical, 1 Rule 3 blocking)
**Impact on plan:** All auto-fixes necessary for correctness and data integrity. No scope creep.

## Issues Encountered

- **prometheus_client 0.25+ parent-child metric pattern:** Accessing child counter values via `_value.get()` works on labeled children but REGISTRY stores parent objects. The workaround for integration tests is to use `collect()` to iterate samples. Unit tests use direct `.inc()` + `_value.get()` for fresh (empty-parent) metrics — this works because the test-created parent has no registered children.
- **BaseHTTPMiddleware dispatch and FastAPI Request type annotation:** The `dispatch()` method in `BaseHTTPMiddleware` receives `request: Request` as a parameter from Starlette, not from FastAPI injection. Therefore `from __future__ import annotations` is safe in middleware.py but breaks route handler test functions where FastAPI uses the type hint for injection.

## Threat Surface Scan

| Threat ID | Component | Mitigation |
|-----------|-----------|------------|
| T-05-01-01 | GET /metrics (no auth) | Documented as internal-network-only deployment requirement. No auth in MVP. Future: mTLS or network policy. |
| T-05-01-02 | Metric labels | AG-15 enforced: no PII, entity values, request content, or per-request identifiers in any label. Verified by no_sensitive_keys_in_label_names test. |
| T-05-01-03 | Counter overflow | Accept — float64 sufficient for ≤ 1M req/day MVP scale. Monitor at Phase 11. |
| T-05-01-04 | Load test hitting production | Accept — documented in README.md to run against isolated test instance. |
| T-05-01-SC | prometheus_client package | Phase 1 audit verdict: OK. 10yr history, 50M+ downloads, official Prometheus client. |

## Known Stubs

None — all metrics are fully wired with instrumentation in all pipeline stages. The `active_config_version` gauge starts at 0 (no hot-reload yet; will increment in Plan 05-02 when Admin API hot-reload is implemented).

## Next Phase Readiness

- Plan 05-01 complete — metrics foundation ready for all subsequent observability work
- Plan 05-02 (Post-restoration token verification + custom rules Admin API) can start immediately
- k6 load test requires user to install k6 and run against a test gateway instance
- No blockers for Phase 6

---

*Phase: 05-configuration-observability*
*Plan: 01*
*Completed: 2026-07-02*
