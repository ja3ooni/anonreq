# Phase 5 Task Breakdown

## Plan 05-01: Prometheus Metrics + k6 Load Test

### Tasks
1. **Set up Prometheus client** — add `prometheus_client` dependency, initialize metrics registry
2. **Define metric counters/histograms** — `anonreq_requests_total`, `anonreq_detection_latency_ms`, `anonreq_entities_detected_total`, `anonreq_unrestored_tokens_total`, `anonreq_fail_secure_events_total`, `anonreq_audit_failures_total`, `anonreq_processing_overhead_ms`, `anonreq_active_config_version`
3. **Implement FastAPI middleware** — request counting, timer start/stop, label population
4. **Instrument DetectionStage** — record `anonreq_detection_latency_ms` histogram per TextNode
5. **Instrument ForwardingGuard** — record pre-provider timestamp for overhead calculation
6. **Instrument RestorationStage** — record processing overhead on completion
7. **Instrument fail-secure paths** — increment `anonreq_fail_secure_events_total` for every failure type
8. **Instrument audit logger** — increment `anonreq_audit_failures_total` on write failure
9. **Expose `GET /metrics`** — Prometheus text format, no auth (internal network)
10. **Create k6 load test script** — `tests/load/benchmark.js`
    - Configurable concurrency (default 50), prompt size (1000 words), duration (60s)
    - Non-streaming scenario only (MVP)
    - Measure gateway overhead (not provider latency)
11. **Document load test procedure** — how to run, how to interpret results, reference P95 target
12. **Unit tests**: metric increments in correct pipeline stages, label consistency
13. **Integration test**: `GET /metrics` returns expected metric names

### Files created/modified
- `src/gateway/monitoring/metrics.py` — Prometheus metric definitions
- `src/gateway/monitoring/middleware.py` — FastAPI middleware for timing/counting
- `src/gateway/pipeline/stages.py` — instrumentation points (Detection, ForwardingGuard, Restoration)
- `src/gateway/pipeline/context.py` — add processing_overhead_ms field
- `src/gateway/main.py` — register middleware + metrics endpoint
- `tests/load/benchmark.js` — k6 load test script
- `tests/load/README.md` — how to run load tests
- `tests/unit/monitoring/test_metrics.py`
- `tests/integration/test_metrics_endpoint.py`

---

## Plan 05-02: Post-Restoration Token Verification + Custom Rules Admin API

### Tasks
1. **Implement ResponseScanner** — regex scan for `\[[A-Z]+_\d+\]` in response body
2. **Implement ScanStage (non-streaming)** — execute after RestorationStage, before response send
3. **Implement StreamScanStage** — execute on full assembled text after stream FINISH
4. **Wire both scan stages** — increment `anonreq_unrestored_tokens_total`, log warning
5. **Define Admin API models** — CustomRecognizerRule, ExclusionEntry, RulesConfig schemas
6. **Implement config validation** — YAML parse, schema validation, regex compilation check, sample text test
7. **Implement AtomicConfigRegistry** — thread-safe pointer swap, version tracking, last-known-good
8. **Implement `GET /v1/config/rules`** — return active custom recognizers + exclusion count
9. **Implement `POST /v1/admin/config/rules`** — validate → atomic swap → audit log → increment version
10. **Implement admin auth middleware** — check `ANONREQ_ADMIN_API_KEY` env var
11. **Wire admin routes** — register under FastAPI app, separate from main API routes
12. **Integrate AtomicConfigRegistry with DetectionProvider** — hot-reloaded rules available for next request
13. **Unit tests**: ResponseScanner patterns, config validation, atomic swap, version increment
14. **Integration test**: hot-reload e2e — submit valid config → recognizer available; submit invalid → HTTP 422, old config intact

### Files created/modified
- `src/gateway/verification/scanner.py` — ResponseScanner regex logic
- `src/gateway/verification/stages.py` — ScanStage (non-streaming) + StreamScanStage
- `src/gateway/admin/routes.py` — Admin API endpoints
- `src/gateway/admin/auth.py` — Admin API key middleware
- `src/gateway/admin/config.py` — AtomicConfigRegistry, RulesConfig models
- `src/gateway/detection/provider.py` — accept hot-reloaded recognizers
- `src/gateway/main.py` — register admin routes
- `tests/unit/verification/test_scanner.py`
- `tests/unit/admin/test_config_registry.py`
- `tests/unit/admin/test_validation.py`
- `tests/integration/test_admin_rules.py`
- `tests/integration/test_scan_stages.py`

---

## File Manifest

```
src/gateway/
├── monitoring/
│   ├── __init__.py
│   ├── metrics.py
│   └── middleware.py
├── verification/
│   ├── __init__.py
│   ├── scanner.py
│   └── stages.py
├── admin/
│   ├── __init__.py
│   ├── routes.py
│   ├── auth.py
│   └── config.py
├── detection/
│   └── provider.py        (modified — accept hot-reloaded registry)
├── pipeline/
│   ├── stages.py          (modified — instrumentation points)
│   └── context.py         (modified — overhead_ms field)
└── main.py                (modified — register metrics, admin routes)

tests/
├── unit/
│   ├── monitoring/
│   │   └── test_metrics.py
│   ├── verification/
│   │   └── test_scanner.py
│   └── admin/
│       ├── test_config_registry.py
│       └── test_validation.py
├── integration/
│   ├── test_metrics_endpoint.py
│   ├── test_admin_rules.py
│   └── test_scan_stages.py
└── load/
    ├── benchmark.js
    └── README.md
```
