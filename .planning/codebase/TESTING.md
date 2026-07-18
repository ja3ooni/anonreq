# Testing Patterns

**Analysis Date:** 2026-07-18

## Test Framework

**Runner:**
- pytest 9.0+ with `pytest-asyncio` 1.4.0+
- Config: `pyproject.toml [tool.pytest.ini_options]`
- `asyncio_mode = "auto"` — async tests run automatically without markers
- `testpaths = ["tests"]`
- `pythonpath = ["src"]` — allows `from anonreq.*` imports in tests

**Assertion Library:**
- pytest built-in `assert` (no separate assertion library)
- Hypothesis `assume()` for filtering in property tests

**Run Commands:**
```bash
uv run pytest                          # All tests
uv run pytest tests/unit/              # Unit tests only
uv run pytest tests/integration/       # Integration tests only
uv run pytest tests/property/          # Property-based tests only
uv run pytest -m load                  # Load tests only
uv run pytest tests/test_cache.py      # Single module
uv run pytest tests/test_cache.py::test_name  # Single test
```

**Coverage:**
- `coverage` plugin configured in `pyproject.toml`
- `source = ["anonreq"]`
- `fail_under = 60` (minimum threshold)
- `show_missing = true`, `skip_covered = true`
- Run coverage: `uv run pytest --cov --cov-report=term-missing`

## Test File Organization

**Location:**
- Root `tests/` directory with mixed flat and subdirectory structure
- Flat files at root for legacy/early tests: `tests/test_roundtrip.py`, `tests/test_exceptions.py`
- Subdirectories for domain-organized tests: `tests/unit/`, `tests/integration/`, `tests/property/`, `tests/load/`

**Naming:**
- `test_<feature_or_module>.py` consistently
- Test classes: `Test<Feature>` (PascalCase): `TestCollectingState`, `TestPermissionDeterminism`
- Test functions: `test_<what_is_tested>` (snake_case): `test_roundtrip_correctness`, `test_fail_secure_returns_5xx`
- Property test IDs embedded in docstrings: `TEST-01`, `TEST-04a–04e`, `COMP-01`, `LOCALE-01`

**Structure:**
```
tests/
├── conftest.py                    # Global fixtures, env setup, Hypothesis strategies
├── hypothesis_strategies.py       # Shared Hypothesis strategies (separate to avoid import overhead)
├── test_*.py                      # Flat test files (legacy + unit)
├── unit/                          # Structured unit tests
│   ├── admin/
│   ├── auth/
│   ├── compliance/
│   ├── detection/
│   ├── locale/
│   ├── middleware/
│   ├── monitoring/
│   ├── providers/
│   ├── routing/
│   ├── secrets/
│   ├── services/
│   ├── streaming/
│   └── verification/
├── integration/                   # Integration tests (pipeline, e2e, runtime wiring)
│   ├── conftest.py (none — uses root conftest)
│   └── test_*.py
├── property/                      # Property-based tests (Hypothesis)
│   ├── conftest.py                # Property-test-specific fixtures (test_app, inject_failure)
│   ├── strategies.py              # Shared strategies for property tests
│   └── test_*.py
├── load/                          # Load/concurrency tests
│   └── test_disconnect.py
├── firewall/                      # AI firewall domain tests
├── policy/                        # Policy engine tests
├── multimodal/                    # Multimodal scanning tests
├── endpoint/                      # Endpoint agent tests
├── admin/                         # Admin route tests
├── casb/                          # CASB integration tests
├── discovery/                     # Discovery inventory tests
├── rag/                           # RAG governance tests
└── restore/                       # Token restoration tests
```

## Test Structure

**Suite Organization:**
```python
"""Module docstring with TEST-XX reference and what it proves."""

from __future__ import annotations

# imports...

# ── Constants ──────────────────────────────────────────────────────
MAX_EXAMPLES = 200

# ── Fixtures ──────────────────────────────────────────────────────
@pytest.fixture
def my_fixture():
    ...

# ── Test Section ──────────────────────────────────────────────────
class TestFeature:
    """Docstring explaining the invariant."""

    async def test_specific_behavior(self, fixture) -> None:
        """Docstring with test ID and what it verifies."""
        ...
```

**Patterns:**
- Module-level docstrings reference requirement IDs: `Per D-22 through D-28`
- Section dividers: `# ── Section Name ──────────────────────────`
- Test classes group related invariant tests
- Every test function has a docstring explaining the invariant being proved
- Type annotations on all test function parameters

## Mocking

**Framework:** `unittest.mock` (stdlib) — no third-party mock library

**Patterns:**
```python
from unittest.mock import AsyncMock, MagicMock

# Mock with spec for type safety
presidio_mock = MagicMock(spec=["analyze_text_nodes", "close"])
presidio_mock.analyze_text_nodes = AsyncMock(return_value=[[]])

# Mock for HTTP calls (httpx)
provider_stage._http_client = MagicMock()
provider_stage._http_client.post = AsyncMock(return_value=MagicMock(
    status_code=200,
    is_error=False,
    json=lambda: {...},
))

# Mock for app state
app.state.policy_store = AsyncMock(spec=PolicyStore)
app.state.spend_controller = AsyncMock(spec=SpendController)

# Patch context managers for failure injection
@contextlib.asynccontextmanager
async def _inject_detection_failure(app: FastAPI) -> AsyncIterator[None]:
    stage = _find_stage_by_name(app.state.pipeline, "DetectionStage")
    original = stage.execute

    async def fail_execute(ctx: Any) -> Any:
        ctx.fail_secure(PipelineAbortError(...))
        return ctx

    stage.execute = fail_execute
    try:
        yield
    finally:
        stage.execute = original
```

**What to Mock:**
- External HTTP calls (provider API): `httpx.Client.post`
- Redis/Valkey cache: use `fakeredis.aioredis.FakeRedis` (NOT a mock)
- Presidio Analyzer: `MagicMock(spec=["analyze_text_nodes", "close"])`
- Pipeline stages: replace `.execute` method for failure injection
- App state dependencies: `AsyncMock(spec=SomeClass)`

**What NOT to Mock:**
- `CacheManager` — use `fakeredis.aioredis.FakeRedis` for realistic async behavior
- Pipeline stage logic — test with real stages + mocked external deps
- Tokenizer/Restorer — use real implementations for round-trip tests
- SQLAlchemy — use in-memory SQLite for database tests

**respx for HTTP mocking:**
```python
import respx

# Mock provider HTTP calls in integration tests
with respx.mock:
    respx.post(f"{PROVIDER_BASE_URL}/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={...})
    )
    # ... test code
```

## Fixtures and Factories

**Root `tests/conftest.py`:**
```python
# Module-level env vars (BEFORE any Settings import)
os.environ.setdefault("ANONREQ_API_KEY", "a" * 32)
os.environ.setdefault("ANONREQ_VALKEY_URL", "redis://localhost:6379/0")
os.environ.setdefault("ANONREQ_PRESIDIO_URL", "http://localhost:5001")

@pytest.fixture
def settings_override(monkeypatch): ...
@pytest.fixture
def app(): ...
@pytest.fixture
async def test_client(app): ...
@pytest.fixture
async def cache_manager(): ...          # fakeredis-backed
@pytest.fixture
def sample_text_nodes(): ...
@pytest.fixture
def sample_chat_request(): ...
@pytest.fixture
def processing_context(): ...
@pytest.fixture
def admin_app(): ...
```

**Property Test `tests/property/conftest.py`:**
```python
@pytest_asyncio.fixture
async def test_app(): ...           # Full FastAPI app with mocked pipeline
@pytest_asyncio.fixture
async def property_client(test_app): ...  # Authenticated AsyncClient
@pytest.fixture
def provider_spy(test_app): ...     # Tracks ProviderStage call count
@pytest.fixture
def metrics_snapshot(): ...         # Reads Prometheus counter values
@pytest.fixture
def log_capture(): ...              # Captures log output for PII scanning
@pytest.fixture
def audit_capture(): ...            # Captures structlog audit output
@pytest.fixture
def property_cache_manager(test_app): ...
```

**Hypothesis Strategies (in conftest or separate module):**
```python
@st.composite
def token_mapping_strategy(draw): ...
@st.composite
def chunked_stream_strategy(draw): ...
@st.composite
def reasoning_stream_strategy(draw): ...
```

**Key Fixture Patterns:**
- Lazy imports in fixtures to avoid slow test collection (`from fastapi import FastAPI` inside fixture body)
- `fakeredis.aioredis.FakeRedis(decode_responses=True)` for all Redis-backed tests
- `CacheManager._from_client(fake_redis, ttl=300)` or `CacheManager.__new__(CacheManager)` for direct construction
- `async with` for all async client/resource lifecycle
- Module-level `os.environ.setdefault()` for env vars required at import time

**Files:**
- `tests/conftest.py`
- `tests/property/conftest.py`
- `tests/unit/providers/conftest.py`

## Hypothesis Strategies

**Separate Module Pattern:**
- Shared strategies live in `tests/hypothesis_strategies.py` (not `conftest.py`) to avoid ~40s FastAPI import overhead
- Property-specific strategies in `tests/property/strategies.py`
- `tests/conftest.py` also defines `@st.composite` strategies for streaming tests

**Common Strategies:**
```python
# Entity types for PII generation
ENTITY_TYPES = ["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "IBAN_CODE",
                "IP_ADDRESS", "URL", "US_SSN", "PERSON", "LOCATION", "ORGANIZATION"]
entity_types_st = st.sampled_from(ENTITY_TYPES)

# PII text generation
email_strategy = st.emails()
phone_strategy = st.from_regex(r"\+?1?\d{7,15}", fullmatch=True)
credit_card_strategy = st.from_regex(r"\d{4}-\d{4}-\d{4}-\d{4}", fullmatch=True)
iban_strategy = st.from_regex(r"[A-Z]{2}\d{2}[A-Z0-9]{1,30}", fullmatch=True)
ip_strategy = st.from_regex(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", fullmatch=True)
url_strategy = st.from_regex(r"https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", fullmatch=True)

# Composite: text with embedded PII
@st.composite
def pii_text_strategy(draw): ...  # Returns (text, entity_value, entity_type)

# Detection spans
@st.composite
def detection_span(draw, text=""): ...
@st.composite
def detection_list(draw, text=""): ...

# Failure injection
failure_mode_strategy = st.sampled_from(list(FailureMode))
pipeline_path_strategy = st.sampled_from(list(PipelinePath))
```

**Standard Settings:**
```python
MAX_EXAMPLES = 200
_COMMON_HC = [HealthCheck.too_slow, HealthCheck.data_too_large, HealthCheck.function_scoped_fixture]

@settings(
    max_examples=MAX_EXAMPLES,
    deadline=60000,
    derandomize=True,
    suppress_health_check=_COMMON_HC,
)
```

**Files:**
- `tests/hypothesis_strategies.py`
- `tests/property/strategies.py`
- `tests/conftest.py` (streaming strategies)

## Coverage

**Requirements:**
- `fail_under = 60` in `pyproject.toml [tool.coverage.report]`
- `source = ["anonreq"]`
- `show_missing = true`, `skip_covered = true`

**View Coverage:**
```bash
uv run pytest --cov --cov-report=term-missing
uv run pytest --cov --cov-report=html  # HTML report
```

## Test Types

**Unit Tests (`tests/unit/`, `tests/test_*.py`):**
- Single module/class/function isolation
- Mocked external dependencies
- Focus: correctness of individual components
- Examples: `test_tail_buffer.py`, `test_exceptions.py`, `test_config.py`

**Integration Tests (`tests/integration/`):**
- Multiple components wired together
- Real pipeline stages with mocked external services (Presidio, provider HTTP)
- Focus: end-to-end flow correctness
- Examples: `test_e2e_round_trip.py`, `test_scan_stages.py`, `test_streaming_chat_route.py`

**Property-Based Tests (`tests/property/`):**
- Hypothesis `@given` with generated inputs
- Prove invariants hold for all inputs in the strategy space
- Focus: security/correctness invariants that must never break
- Examples: `test_fail_secure.py`, `test_no_pii_in_logs.py`, `test_cross_request_randomization.py`

**Load Tests (`tests/load/`):**
- Marked with `@pytest.mark.load`
- Concurrent operations on shared resources
- Focus: cleanup idempotency, concurrent disconnect handling
- Example: `test_disconnect.py` — 100 concurrent disconnects

**Domain Tests (`tests/firewall/`, `tests/policy/`, `tests/multimodal/`, etc.):**
- Feature-specific test suites organized by domain
- Mix of unit and integration approaches
- Focus: domain-specific behavior and edge cases

## Common Patterns

**Async Testing:**
```python
# Property tests with Hypothesis + async
@settings(max_examples=200, deadline=60000)
@given(failure_mode=failure_mode_strategy)
async def test_fail_secure_returns_5xx(test_app, property_client, failure_mode):
    async with inject_failure(failure_mode, PipelinePath.NON_STREAMING, test_app):
        response = await property_client.post("/v1/chat/completions", json={...})
    assert response.status_code >= 500

# Unit tests with asyncio.run() for sync Hypothesis + async code
@given(chunked_stream_strategy())
@settings(max_examples=100)
def test_arbitrary_chunk_split(args):
    full_text, chunks, mapping = args
    restored = _restore_with_mapping(asyncio.run(_collect_text(TailBuffer(), chunks)), mapping)
    assert restored == expected
```

**Error Testing:**
```python
# Verify fail-secure: no data forwarded, correct HTTP status
assert response.status_code == 503
assert provider_spy.called is False

# Verify no PII in logs
log_output = log_capture.getvalue()
assert entity_value not in log_output

# Verify error envelope format
body = response.json()
assert "error" in body
assert body["error"]["type"] == "service_unavailable"
assert body["error"]["request_id"] != "unknown"
```

**Failure Injection Pattern:**
```python
@contextlib.asynccontextmanager
async def inject_failure(failure_mode: FailureMode, pipeline_path: PipelinePath, app: FastAPI):
    injector = _FAILURE_INJECTORS[failure_mode]
    async with injector(app):
        yield

# Usage in tests:
async with inject_failure(FailureMode.DETECTION, PipelinePath.NON_STREAMING, test_app):
    response = await property_client.post(...)
```

**Property Test Pattern:**
```python
# 1. Define the invariant in the docstring
# 2. Use @given with appropriate strategies
# 3. Configure @settings with max_examples and deadline
# 4. Assert the invariant holds for all generated inputs
# 5. Include descriptive assertion messages

@settings(max_examples=200, deadline=60000, derandomize=True,
          suppress_health_check=[HealthCheck.too_slow, _FIXTURE_HC])
@given(entity_value=st.emails())
def test_within_session_deduplication(entity_value):
    """Property 7: Same entity value in same session → same token."""
    # ... test code ...
    assert len(mapping) == 1
```

## Key Test Invariants

**Property-based tests prove these invariants:**

| Invariant | File | What It Proves |
|-----------|------|----------------|
| Round-trip correctness | `tests/test_roundtrip.py` | `anonymize → restore` is byte-for-byte identical |
| Token uniqueness | `tests/test_roundtrip.py` | N distinct values → N distinct tokens |
| Token deduplication | `tests/test_roundtrip.py` | Same value K times → same token |
| Session isolation | `tests/test_roundtrip.py` | Different sessions → different token indices |
| Fail-secure | `tests/property/test_fail_secure.py` | All 5 failure modes → HTTP 5xx, zero data forwarded |
| No PII in logs | `tests/property/test_no_pii_in_logs.py` | PII values never appear in any log output |
| Cross-request randomization | `tests/property/test_cross_request_randomization.py` | Same value across 1000 sessions → zero collisions |
| Streaming restoration | `tests/property/test_streaming.py` | Arbitrary chunk splits → correct restoration |
| Buffer overflow protection | `tests/property/test_streaming.py` | `TailBuffer` never exceeds `MAX_BUFFER_CHARS` |
| Locale determinism | `tests/property/test_locale_invariants.py` | Same input + same locale → same detection output |
| Locale union monotonicity | `tests/property/test_locale_invariants.py` | Adding locale never reduces detection coverage |
| Compliance non-weakening | `tests/property/test_compliance_invariants.py` | Preset merge never removes entity types |
| Compliance associativity | `tests/property/test_compliance_invariants.py` | `merge(merge(A,B),C) == merge(A,merge(B,C))` |
| Locale checksum | `tests/property/test_locale_checksum.py` | Invalid-checksum IDs never flagged as valid |
| Data lineage immutability | `tests/property/test_data_lineage_invariants.py` | No update/delete operations exposed |
| Data lineage count | `tests/property/test_data_lineage_invariants.py` | Inserted N records → query returns N |
| Fairness determinism | `tests/property/test_fairness_invariants.py` | Same inputs → same outputs |
| Fairness recall bounds | `tests/property/test_fairness_invariants.py` | `recall_disparity ∈ [0, 1]` |
| Financial crime boost bounds | `tests/property/test_financial_crime_invariants.py` | Boosted score ∈ [0.0, 1.0] |
| MNPI no-leak | `tests/property/test_mnpi_invariants.py` | MNPI values never in audit logs |
| Tool permission determinism | `tests/property/test_tool_governance.py` | Same tool+provider+domain → same permission |
| Tool format bypass resistance | `tests/property/test_tool_governance.py` | OpenAI vs Anthropic format → same permission |
| Tool cross-domain isolation | `tests/property/test_tool_governance.py` | Cross-domain always BLOCK |
| Tool credential isolation | `tests/property/test_tool_governance.py` | Mismatched delegation always BLOCK |
| Tool audit no raw values | `tests/property/test_tool_governance.py` | Audit events never contain PII/tokens |
| Disconnect cleanup | `tests/property/test_disconnect.py` | Disconnect → cleanup called, 0 orphaned keys |
| Disconnect idempotency | `tests/property/test_disconnect.py` | N signals → exactly 1 cleanup call |

---

*Testing analysis: 2026-07-18*
