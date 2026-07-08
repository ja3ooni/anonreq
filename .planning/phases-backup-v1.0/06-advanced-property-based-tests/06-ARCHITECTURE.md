# Phase 6 Architecture: Advanced Property-Based Tests

## Test Architecture

```
tests/property/
├── strategies.py           # Shared Hypothesis strategies (PII generation, session contexts)
├── conftest.py             # Fixtures: injected failures, metrics snapshot, audit capture
├── test_fail_secure.py     # TEST-04 — all 5 failure modes × both paths
├── test_no_pii_in_logs.py  # TEST-06 — all log pathways × all entity types
├── test_cross_request_randomization.py  # TEST-08 — 1000+ session pairs
└── test_disconnect.py      # TEST-07E through TEST-07H — adversarial disconnects
```

## Failure Injection Model

```
inject_failure(mode: FailureMode, path: PipelinePath) → AsyncIterator[None]
    ↓
Sets up mocks/spies at injection points based on mode:

FailureMode.DETECTION:
    DetectionProvider.analyze() → raises DetectionError

FailureMode.CACHE:
    ValkeyClient.hset() → raises CacheError
    ValkeyClient.hgetall() → raises CacheError

FailureMode.FORWARDING_GUARD:
    ForwardingGuard.check() → returns GuardResult.DENIED

FailureMode.PROVIDER_TIMEOUT:
    ProviderAdapter.execute() → raises asyncio.TimeoutError
    ProviderAdapter.stream_events() → raises asyncio.TimeoutError

FailureMode.CIRCUIT_BREAKER:
    Configure low threshold → fire N failures → next fails immediately
```

## Metrics Verification

```python
# Snapshot before
before = {
    "fail_secure": registry.get_sample_value("anonreq_fail_secure_events_total"),
    "requests_500": registry.get_sample_value(
        "anonreq_requests_total",
        labels={"status": "500"}
    ),
}

# Run request under failure injection
await process_request(mock_request)

# Snapshot after
after = { ... }

# Assert
assert after["fail_secure"] == before["fail_secure"] + 1
assert after["requests_500"] == before["requests_500"] + 1
```

## No-PII-in-Logs Verification

```python
# Fixture: capture all log output
log_buffer = io.StringIO()
handler = logging.StreamHandler(log_buffer)
root_logger.addHandler(handler)

# Run request with synthetic PII
await process_request(pii_text)

# Scan captured output
log_output = log_buffer.getvalue()
for entity_value in pii_entities:
    assert entity_value not in log_output, (
        f"PII leak: {entity_value} found in log output"
    )

# Also check stderr, audit log, metrics labels
```

## Cross-Request Randomization Flow

```python
# Generate N session contexts
sessions = [create_session(seed=uuid7()) for _ in range(1000)]
entity = "john@corp.com"

tokens = set()
for session in sessions:
    mappings = run_pipeline(session, text_with_entity(entity))
    token = mappings[entity]
    assert token not in tokens, f"Collision: {token} seen in two sessions"
    tokens.add(token)

# Verify: with 1000 sessions and 2^32 possible offsets,
# P(collision) ≈ 1000² / (2 × 2³²) ≈ 0.00012
# Expect 0 collisions in practice
```

## Disconnect Test Model

```python
# ASGI disconnect simulation
class DisconnectEvent:
    """Sentinel that triggers disconnect at a specific pipeline point."""

Injection points for disconnect:
    TEST-07E: in TokenizationStage.hset()
    TEST-07F: in RestorationStage.replace()
    TEST-07G: in stream loop during ProviderAdapter.stream_events()
    TEST-07H: both TIMEOUT and DISCONNECT fire within 1ms

Verification:
    cleanup_called = SessionCleanup._cleaned     # True
    orphaned_mappings = count_valkey_keys()       # 0
    forwarded_calls = ProviderStage.call_count     # 0 (after disconnect)
    terminal_states = len(terminal_events)        # 1
```

## Security Acceptance Gate

```
Phase 6 closes → run all property tests → if all pass → sign SECURITY-ACCEPTANCE.md
    ↓
SECURITY ACCEPTED
    ↓
Phase 6.5: Production Readiness Review
    ↓
Phase 7: Developer Experience & Documentation
```
