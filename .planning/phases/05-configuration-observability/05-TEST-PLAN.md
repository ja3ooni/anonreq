# Phase 5 Test Plan

## Test Tiers

### Tier 1: Unit Tests

| Test | Scope | Plan |
|------|-------|------|
| Metrics initialization | All 8 metrics created with correct labels and docstrings | 05-01 |
| Metric increments (requests) | `anonreq_requests_total` incremented per request with correct labels | 05-01 |
| Metric increments (detection) | `anonreq_detection_latency_ms` recorded per TextNode | 05-01 |
| Metric increments (fail-secure) | `anonreq_fail_secure_events_total` incremented for each failure type | 05-01 |
| Metric increments (audit) | `anonreq_audit_failures_total` incremented on write failure | 05-01 |
| Processing overhead recording | `anonreq_processing_overhead_ms` = provider_dispatch - request_receipt | 05-01 |
| ResponseScanner regex | Correctly finds `[NAME_1]`, `[CREDIT_CARD_2]`, mixed content | 05-02 |
| ResponseScanner edge cases | No tokens, single token, multiple tokens, tokens in JSON structure | 05-02 |
| ResponseScanner streaming | Scan on assembled pre-restoration text | 05-02 |
| Config validation (valid) | YAML parse → schema validate → regex compile → pass | 05-02 |
| Config validation (invalid YAML) | Malformed YAML → HTTP 422 with line number | 05-02 |
| Config validation (bad regex) | Invalid pattern → HTTP 422 with compile error | 05-02 |
| AtomicConfigRegistry swap | Pointer swap under concurrent load, version increment | 05-02 |
| AtomicConfigRegistry last-good | Invalid config rejected, old config remains active | 05-02 |
| Admin API auth | Missing/incorrect ANONREQ_ADMIN_API_KEY → 401 | 05-02 |
| Admin API auth (separate key) | Gateway API key does not authorize admin endpoints | 05-02 |

### Tier 2: Integration Tests

| Test | Scenario | Verification |
|------|----------|-------------|
| Metrics endpoint | `GET /metrics` returns expected metric names | All 8 metric families present |
| Metrics after request | Process a request, check metrics | request counter incremented, detection latency recorded |
| Metrics after fail-secure | Trigger fail-secure condition | fail_secure_events counter incremented |
| Scan stage non-streaming | Response with residual token + without | Unrestored counter incremented only for residual case |
| Scan stage streaming | Stream with residual token + without | Counter incremented only for residual, stream never blocked |
| Hot-reload e2e | POST valid config → recognizer available | 200, next detection uses new rules |
| Hot-reload reject invalid | POST invalid config → old config active | 422, detection unchanged |
| Hot-reload audit log | POST config → audit entry written | Entry with version, count, entity types |
| Admin auth | Wrong admin key → 401, no key → 401 | Admin endpoints protected |

### Tier 3: Load Tests (k6)

| Test | Scenario | Target |
|------|----------|--------|
| Baseline overhead | 1 user, 100-word prompt | Measure baseline |
| Sustained load | 50 concurrent, 1000-word prompt, 60s | P95 overhead ≤ 100ms |
| Burst test | 100 concurrent burst, 30s | No connection drops, P99 ≤ 200ms |
| Fail-secure under load | Mock Presidio unavailable at 50 concurrent | 100% 503, zero forwarded, metrics correct |

## Coverage Targets

- Monitoring module (metrics, middleware): 95%+
- Verification module (scanner, stages): 95%+
- Admin module (routes, auth, config registry): 90%+
- Pipeline instrumentation points: 100% of paths increment correct metric
- Overall Phase 5: 85%+

## Invariants (must pass before Phase 5 closes)

1. No PII in Prometheus metric labels or values (AG-15)
2. Invalid config never replaces active config (AG-16)
3. Post-restoration scan never modifies or blocks the response (AG-17)
4. Metrics and audit logging continue during fail-secure events (AG-18)
5. Admin API key is separate from gateway API key
6. Hot-reload is atomic — concurrent requests see either old or new config, never partial
7. Processing overhead measurement excludes provider response time
