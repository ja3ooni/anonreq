# Phase 6 Test Plan

## Test Strategy

Phase 6 _is_ a test phase. The "implementation" is the test suite itself. There are no tiers — every test is a property-based Hypothesis test.

## Property Tests

| Test ID | Requirement | File | Strategy |
|---------|------------|------|----------|
| TEST-04a | Non-streaming fail-secure — detection failure | `test_fail_secure.py` | Inject DetectionError, verify forwarded=0, cleanup=True, metric+AUDT |
| TEST-04b | Non-streaming fail-secure — cache failure | `test_fail_secure.py` | Inject CacheError, same invariant |
| TEST-04c | Non-streaming fail-secure — ForwardingGuard | `test_fail_secure.py` | Guard returns DENIED, verify blocked |
| TEST-04d | Non-streaming fail-secure — provider timeout | `test_fail_secure.py` | Inject asyncio.TimeoutError, verify blocked |
| TEST-04e | Non-streaming fail-secure — circuit breaker | `test_fail_secure.py` | N failures → next fails-fast, verify counter |
| TEST-04f | Streaming fail-secure — all 5 modes | `test_fail_secure.py` | Same 5 modes in streaming path |
| TEST-04g | Metrics verification — every failure mode | `test_fail_secure.py` | Snapshot before/after, verify counters |
| TEST-04h | Audit verification — every failure mode | `test_fail_secure.py` | Capture AUDT-04 entries |
| TEST-05 | Locale checksum — invalid IDs not flagged | `test_locale_checksum.py` | Generate invalid checksum IDs, verify dropped |
| TEST-06a | No-PII — application logs | `test_no_pii_in_logs.py` | Synthetic PII → scan stdout |
| TEST-06b | No-PII — structured JSON logs | `test_no_pii_in_logs.py` | Synthetic PII → scan JSON log output |
| TEST-06c | No-PII — audit logs | `test_no_pii_in_logs.py` | Synthetic PII → scan audit entries |
| TEST-06d | No-PII — exception logs / tracebacks | `test_no_pii_in_logs.py` | Trigger error with PII in request, scan stderr |
| TEST-06e | No-PII — metrics labels | `test_no_pii_in_logs.py` | Verify no entity values in metric label values |
| TEST-08 | Cross-request randomization | `test_cross_request_randomization.py` | 1000+ sessions, same value → different tokens |
| TEST-07E | Disconnect during tokenization | `test_disconnect.py` | Drop connection mid-hset, verify cleanup |
| TEST-07F | Disconnect during restoration | `test_disconnect.py` | Drop connection mid-restore, verify no partial emit |
| TEST-07G | Disconnect during provider stream | `test_disconnect.py` | Drop connection mid-stream, verify upstream cancelled |
| TEST-07H | Disconnect + timeout race | `test_disconnect.py` | Both fire near-simultaneously, verify 1 terminal state |

## Hypothesis Settings

```python
# All Phase 6 tests
MAX_EXAMPLES = 200           # Enough for statistical confidence
DEADLINE = 60000              # 60s per example (some involve real I/O mock)
DERANDOMIZE = True            # Deterministic seed for CI reproducibility
SUPPRESS_HEALTH_CHECK = [     # Suppress slow-data health check
    HealthCheck.too_slow,
    HealthCheck.data_too_large,
]
```

## Invariants (all must pass before Phase 6 closes)

1. Every failure mode → 0 bytes forwarded (AG-19)
2. Every failure mode → cleanup executed exactly once (AG-19)
3. Every failure mode → fail_secure_events_total incremented (AG-20)
4. Every failure mode → AUDT-04 entry written
5. No entity value appears in any log sink under any pipeline path
6. Same entity value across 1000+ sessions → all different tokens, zero collisions
7. Disconnect at any pipeline point → cleanup exactly once, 0 orphaned mappings
8. Disconnect + timeout race → exactly one terminal state
9. Invalid checksum IDs never flagged as valid detections
10. Circuit breaker opens after N failures, fails-fast on next request
