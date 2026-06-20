# Phase 6 Task Breakdown

## Plan 06-01: Fail-Secure + No-PII-in-Logs Property Tests

### Tasks
1. **Create shared test infrastructure** — `tests/property/strategies.py` (PII generators, session contexts, failure injection helpers), `tests/property/conftest.py` (fixtures for metrics snapshot, audit capture, log capture)
2. **Implement failure injection framework** — `inject_failure(FailureMode, PipelinePath)` set up mocks at injection points
3. **Implement TEST-04 non-streaming** — inject all 5 failure modes, verify forwarded=0, cleanup=True, metric incremented, audit written
4. **Implement TEST-04 streaming** — inject failure mid-stream, verify stream terminates, cleanup called, 0 forwarded after failure
5. **Implement TEST-04 circuit breaker** — configure low threshold, N failures, next request fails-fast
6. **Implement TEST-04 metrics verification** — snapshot before/after, verify fail_secure_events_total incremented
7. **Implement TEST-04 audit verification** — capture AUDT-04 entries, verify format and content
8. **Implement TEST-06** — generate synthetic PII across all entity types, run through all pipeline paths, scan all log sinks for entity substrings
9. **Run tests locally** — verify hypothesis exits without error on default examples

### Files created
- `tests/property/strategies.py`
- `tests/property/conftest.py`
- `tests/property/test_fail_secure.py`
- `tests/property/test_no_pii_in_logs.py`

---

## Plan 06-02: Cross-Request Randomization Property Test

### Tasks
1. **Implement deterministic session seed generation** — UUIDv7 per session
2. **Implement TEST-08** — generate 1000+ session pairs with same entity values, verify all tokens differ
3. **Verify collision bound** — P(collision) ≤ 2⁻³² with 1000 sessions
4. **Implement token diversity assertion** — no two sessions produce same token for same entity value

### Files created
- `tests/property/test_cross_request_randomization.py`

---

## Plan 06-03: Streaming Disconnect + Checksum Property Tests

### Tasks
1. **Implement ASGI disconnect simulation fixture** — trigger disconnect at pipeline injection point
2. **Implement TEST-07E** — disconnect during tokenization, verify cleanup + 0 orphaned mappings
3. **Implement TEST-07F** — disconnect during restoration, verify partial restoration never emitted
4. **Implement TEST-07G** — disconnect during provider stream, verify upstream cancelled
5. **Implement TEST-07H** — disconnect + timeout race, verify exactly one terminal state
6. **Implement TEST-05 (locale checksum)** — invalid checksum IDs never flagged as valid detections
7. **Verify cleanup idempotency** — N simultaneous disconnect signals → exactly 1 cleanup call

### Files created
- `tests/property/test_disconnect.py` (may extend Phase 3 file)
- `tests/property/test_locale_checksum.py` (moved from Phase 4 scope)

---

## File Manifest

```
tests/
├── property/
│   ├── __init__.py
│   ├── strategies.py
│   ├── conftest.py
│   ├── test_fail_secure.py
│   ├── test_no_pii_in_logs.py
│   ├── test_cross_request_randomization.py
│   ├── test_disconnect.py
│   └── test_locale_checksum.py
└── (no production code changes — pure test phase)
```

## Dependency Graph

```
06-01 (fail-secure + no-PII)
    ↓
06-02 (cross-request randomization — depends on 06-01 patterns)
    ↓
06-03 (disconnect + checksum — depends on 06-01 fixtures)
    ↓
Security Acceptance Gate (07-SECURITY-ACCEPTANCE.md signed)
```
