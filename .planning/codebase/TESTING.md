# Testing Patterns

**Analysis Date:** 2026-07-06

## Test Framework

**Runner:**
- **pytest** (v9.1.1 pinned in `requirements-dev.txt`)
- Config: `pyproject.toml` under `[tool.pytest.ini_options]`

**Assertion Library:**
- Built-in `assert` — no extra assertion library (no `assertpy`, `hamcrest`, etc.)
- `pytest.raises()` for exception assertions

**Run Commands:**
```bash
uv run pytest                                    # Full test suite
uv run pytest tests/test_cache.py                # Single file
uv run pytest tests/test_cache.py::test_name     # Single test
uv run pytest tests/property/                    # Hypothesis property tests only
uv run pytest tests/unit/                        # Unit tests only
uv run pytest -m load                            # Load/concurrency tests (custom marker)
uv run pytest -k "streaming or fail"             # Keyword match
uv run pytest --hypothesis-show-statistics       # Show Hypothesis coverage stats
uv run pytest --co                              # Coverage report (when configured)
```

**Configuration (`pyproject.toml`):**
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]
markers = [
    "load: load and concurrency tests",
]
```

- `asyncio_mode = "auto"` means async test functions are automatically detected as `asyncio`-marked — no `@pytest.mark.asyncio` decorator needed on individual tests
- `pythonpath = ["src"]` ensures `anonreq.*` imports resolve without `PYTHONPATH` manipulation
- The `load` marker is the only custom marker defined — used for load/concurrency tests

## Test File Organization

**Location:**
- All tests live under `/Users/aljaunia/Documents/Develop/annon/tests/`
- Tests are NOT co-located with source — separate test directory mirrors source structure

**Directory structure:**
```
tests/
├── conftest.py                    # Shared fixtures (env vars, cache_manager, sample data)
├── hypothesis_strategies.py       # Shared Hypothesis strategies (avoid ~40s conftest import overhead)
├── __init__.py                    # Package marker
├── property/                      # Hypothesis property-based tests (Tier 3)
│   ├── conftest.py                # Property test fixtures (test_app, inject_failure, metrics_snapshot)
│   ├── strategies.py              # FailureMode/PipelinePath enums, PII strategies
│   └── test_*.py                  # Invariant tests (fail_secure, streaming, locale, etc.)
├── unit/                          # Pure unit tests (no external deps)
│   ├── streaming/test_tail_buffer.py
│   ├── providers/test_adapters.py
│   ├── locale/test_bundle.py
│   └── ...
├── policy/                        # Policy engine tests
│   ├── test_pdp.py
│   ├── test_pep.py
│   └── ...
├── load/                          # Load/concurrency tests (marked @pytest.mark.load)
│   └── test_disconnect.py
├── integration/                   # Integration tests
├── restore/                       # Restoration engine tests
├── casb/                          # CASB tests
├── endpoint/                      # Endpoint/agent tests
├── discovery/                     # Discovery tests
├── firewall/                      # Firewall pipeline tests
├── multimodal/                    # Multimodal tests
├── admin/                         # Admin API tests
├── rag/                           # RAG tests
└── test_*.py                      # Top-level unit/integration tests (~120+ files)
```

**Naming:**
- Test files: `test_{module_name}.py` (e.g., `test_detection.py`, `test_tokenization.py`)
- Property-based test files: `test_{domain}_invariants.py` or `test_{feature}.py` under `tests/property/`
- Test classes: `Test{ComponentName}` (e.g., `TestRegexPatterns`, `TestLuhnChecksum`, `TestDeduplication`)
- Test functions: `test_{behavior}()` (e.g., `test_valid_credit_card()`, `test_empty_text_returns_empty_list()`)
- Nested test groups by class name with clear section comments

## Test Structure

**Suite Organization:**
Tests are organized using classes for grouping related test cases:

```python
class TestLuhnChecksum:
    """Test suite for Luhn checksum validation."""

    def test_valid_credit_card(self):
        """Valid Visa card number passes Luhn checksum."""
        assert luhn_checksum("4111111111111111") is True

    def test_invalid_credit_card(self):
        """Invalid card number fails Luhn checksum."""
        assert luhn_checksum("1234567890123456") is False
```

**Patterns:**
- **Setup**: Simple per-test instantiation (test objects created inline); shared fixtures via `conftest.py`
- **Teardown**: Fixture-based cleanup via `yield` in `@pytest_asyncio.fixture` or `try/finally` blocks
- **Assertion pattern**: Simple `assert` with optional description string:
  ```python
  assert result is not None
  assert result.provider == result2.provider
  assert 0.0 <= result.confidence <= 1.0
  ```
- **Section comments**: Horizontal rule separators (`# ----`) dividing test class groups

**Section separator pattern:**
```python
# ---------------------------------------------------------------------------
# Luhn checksum tests
# ---------------------------------------------------------------------------
```

## Async Testing

**Pattern:**
```python
async def test_tls_interception_failure_returns_500_and_never_forwards():
    """Docstring describing behavior."""
    dispatcher = CountingDispatcher()
    proxy = TransparentProxy(ExplodingTLS(), AITrafficDetector(), dispatcher)
    response = await proxy.handle_request(_ai_request(RAW_PII))
    assert response.status_code == 500
    assert dispatcher.calls == 0
```

Due to `asyncio_mode = "auto"`, async test functions are automatically handled by `pytest-asyncio` — no decorator needed. Async fixtures use `@pytest_asyncio.fixture`.

## Mocking

**Framework:** `unittest.mock` (`MagicMock`, `AsyncMock`, `patch`) — no external mocking libraries

**Patterns:**

1. **Class-based mocks for fixtures** (in test files):
```python
class CountingDispatcher:
    def __init__(self) -> None:
        self.calls = 0

    async def dispatch(self, content_type: str, body: bytes, ctx: object):
        self.calls += 1
        return b"forwarded"
```

2. **AsyncMock for async components** (in conftest/property conftest):
```python
presidio_mock = MagicMock(spec=["analyze_text_nodes", "close"])
presidio_mock.analyze_text_nodes = AsyncMock(return_value=[[]])
presidio_mock.close = AsyncMock()
```

3. **Monkeypatch patching**:
```python
monkeypatch.setenv("DEPLOYMENT_MODE", "reverse")

# Or direct override with cleanup:
original = asyncio.start_server
asyncio.start_server = fail_start_server
try:
    with pytest.raises(OSError, match="bind failed"):
        await proxy.start("127.0.0.1", 0)
finally:
    asyncio.start_server = original
```

4. **`@patch` decorator** — not used in this codebase; monkeypatch and direct assignment preferred

5. **`respx`** — declared in `requirements-dev.txt` for HTTP mocking (used in some integration tests)

**What to Mock:**
- External services: Presidio Analyzer HTTP calls, provider API calls
- Cache: `fakeredis.aioredis.FakeRedis` for Valkey/Redis simulation
- Pipeline stages: via stage injection pattern in `property/conftest.py`

**What NOT to Mock:**
- Core detection logic (RegexDetector, Luhn checksum) — tested with real implementations
- Tokenization engine — tested with real Tokenizer
- Locale/checksum operations — real implementations with test data

## Fixtures and Factories

**Test Data Pattern:**
```python
RAW_PII = "alice@example.com"  # Module-level constant for reuse

def _ai_request(text: str) -> ProxyRequest:
    return ProxyRequest(
        method="POST", host="api.openai.com", path="/v1/chat/completions",
        headers={"content-type": "application/json"},
        body=f'{{"messages":[{{"role":"user","content":"{text}"}}]}}'.encode(),
        client_hello=b"api.openai.com",
    )

def _tool_result(value: str) -> ToolResult:
    return ToolResult(tool_name="lookup", content={"email": value}, id="call_1", type="openai")
```

**Shared Fixtures** (`tests/conftest.py`):
- `settings_override` — monkeypatch env vars for config tests
- `app` — minimal FastAPI instance (lazy import avoids ~180s overhead)
- `test_client` — async HTTP client bound to test app
- `cache_manager` — `fakeredis.aioredis.FakeRedis` backed CacheManager
- `sample_text_nodes` — reusable dict-based text nodes with PII
- `sample_chat_request` — minimal OpenAI-compatible request dict
- `processing_context` — ProcessingContext with test request_id

**Property Test Fixtures** (`tests/property/conftest.py`):
- `test_app` — FastAPI app with full pipeline, fakeredis CacheManager, mocked PresidioClient
- `property_client` — authenticated `AsyncClient` bound to test_app
- `inject_failure` — async context manager for injecting pipeline failures at any stage
- `metrics_snapshot` — captures current Prometheus metric sample values
- `audit_capture` — captures structlog output in StringIO buffer
- `log_capture` — captures all Python logging for PII scanning
- `provider_spy` — tracks ProviderStage call count
- `property_cache_manager` — returns CacheManager from test app state
- `app_cleanup` — fixture-based cleanup after property tests

**Context Manager Pattern for Failure Injection:**
```python
@contextlib.asynccontextmanager
async def _inject_detection_failure(app: FastAPI) -> AsyncIterator[None]:
    stage = _get_stage(app, "DetectionStage")
    original = stage.execute
    async def fail_execute(ctx: Any) -> Any:
        ctx.fail_secure(PipelineAbortError(status_code=500, ...))
        return ctx
    stage.execute = fail_execute
    try:
        yield
    finally:
        stage.execute = original
```

## Coverage

**Requirements:** Not enforced programmatically (no coverage target in `pyproject.toml`)

**View Coverage:**
```bash
uv run pytest --cov=anonreq --cov-report=term-missing
```

Coverage config in `pyproject.toml`:
```toml
[tool.coverage.run]
source = ["anonreq"]
```

Coverage artifacts (.coverage, htmlcov/coverage.xml) are gitignored.

## Hypothesis Property-Based Testing

**Extensive use of Hypothesis** for Tier 3 invariant testing — one of the defining characteristics of this codebase. Located in `tests/property/`.

**Configuration:**
- `MAX_EXAMPLES = 200` for fail-secure tests
- `max_examples=50-100` for most property tests
- `derandomize=True` for deterministic, reproducible runs
- `deadline=60000` (60s) for async property tests (generous deadline for fixture-heavy tests)
- `suppress_health_check` standard list: `[HealthCheck.too_slow, HealthCheck.data_too_large, HealthCheck.function_scoped_fixture]`

**Pattern:**
```python
@settings(
    max_examples=200,
    deadline=60000,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large, _FIXTURE_HC],
)
@given(failure_mode=failure_mode_strategy)
async def test_fail_secure_returns_5xx(test_app, property_client, failure_mode):
    """Docstring: TEST-04a–04e: Every failure mode returns HTTP >= 500."""
    async with inject_failure(failure_mode, PipelinePath.NON_STREAMING, test_app):
        response = await property_client.post("/v1/chat/completions", ...)
    assert response.status_code >= 500, f"Fail-secure violated: ..."
```

**Key invariant areas tested:**
- **Fail-secure**: All 5 failure modes × both paths = HTTP >= 500, provider not called, metrics recorded
- **Streaming**: Arbitrary chunk split reconstruction, buffer overflow protection, flush timing invariance, reasoning block
- **Locale**: Determinism (same input → same output), union property (adding locale never reduces coverage), universal always present
- **Cross-request randomization**: Token uniqueness across sessions
- **No-PII-in-logs**: PII entity values never appear in log output
- **Compliance invariants**: GDPR, POPIA, LGPD, PIPEDA, Privacy Act compliance rules
- **Financial crime**: MNPI detector invariants
- **Fairness**: Fairness evaluation invariants
- **Gateway**: Detector consistency, route table idempotency, MCP parsing round-trip

**Shared strategies** (`tests/hypothesis_strategies.py`):
- `detection_span()` — generates valid detection span dicts
- `detection_list()` — generates non-overlapping detection span lists
- `pii_text_with_spans()` — generates text with embedded PII and known spans

**Shared strategies** (`tests/property/strategies.py`):
- `FailureMode` / `PipelinePath` enums
- `pii_text_strategy()` — generates text with synthetic PII
- Per-entity-type strategies: `email_strategy`, `phone_strategy`, `credit_card_strategy`, etc.
- `failure_mode_strategy` / `pipeline_path_strategy` — sampled_from enums

## Test Types

**Unit Tests (`tests/unit/` + top-level `test_*.py`):**
- Test individual classes/functions in isolation
- Pure function tests for detection, tokenization, Luhn checksum, patterns
- Class-based test organization (TestLuhnChecksum, TestRegexPatterns, etc.)
- No external dependencies required
- Fast execution (no fixtures for most)

**Integration Tests (`tests/test_*integration*.py`, `tests/test_proxy_integration.py`):**
- Test component interactions (e.g., pipeline + cache + provider)
- Use fakeredis and mocked HTTP rather than real services
- Some use `docker-compose` services for full-stack testing

**Property-Based Tests (`tests/property/`):**
- Hypothesis-driven invariant verification
- 200+ examples per test for statistical confidence
- Full pipeline injection framework for failure mode testing
- Coverage: ~15 test files covering all major invariants

**E2E Tests:**
- Not present in this codebase
- No Playwright, Selenium, or other E2E framework dependency

**Load Tests (`tests/load/`):**
- Marked with `@pytest.mark.load`
- Run separately: `uv run pytest -m load`

## Fixture Import Strategy

A notable pattern: `hypothesis_strategies.py` exists outside `conftest.py` specifically to avoid ~40s import overhead:

```python
# tests/hypothesis_strategies.py
"""Shared Hypothesis strategies for property-based testing.

These strategies are provided in a separate module (not conftest.py) to
avoid the ~40s FastAPI/pydantic import overhead that conftest.py incurs.
"""
```

Similarly, `conftest.py` uses lazy imports inside fixtures to avoid overhead on test collection:
```python
@pytest.fixture
def app():
    from fastapi import FastAPI  # lazy import
    return FastAPI()
```

## Environment Configuration

`tests/conftest.py` sets required env vars at module level before any test imports:

```python
os.environ.setdefault("ANONREQ_API_KEY", "a" * 32)
os.environ.setdefault("ANONREQ_VALKEY_URL", "redis://localhost:6379/0")
os.environ.setdefault("ANONREQ_PRESIDIO_URL", "http://localhost:5001")
os.environ.setdefault("ANONREQ_ADMIN_API_KEY", "adminkey12345678901234567890")
```

This ensures `settings = Settings()` singleton in `config.py` has defaults at import time. Tests that need specific env var values use the `monkeypatch` fixture directly.

## Common Patterns

**Exception Testing:**
```python
with pytest.raises(asyncio.TimeoutError):
    await sanitizer.sanitize_result(_tool_result(RAW_PII))

with pytest.raises(ValueError, match="Unknown DEPLOYMENT_MODE"):
    get_deployment_config("sideways")
```

**Parametrized Tests:**
```python
@pytest.mark.parametrize("topology", [
    TopologyCase("reverse"),
    TopologyCase("transparent"),
    TopologyCase("virtual"),
    TopologyCase("physical"),
])
async def test_fail_closed_enforced_for_all_deployment_topologies(topology):
    ...
```

**Async Iterator Collection:**
```python
async def collect(iterator: AsyncIterator[str]) -> list[str]:
    """Collect all items from an async iterator into a list."""
    return [item async for item in iterator]
```

**Performance/Latency Assertions:**
```python
async def test_provider_forwarding_latency_below_200ms():
    ...
    assert elapsed_ms < 200, f"Latency {elapsed_ms}ms exceeds 200ms threshold"
```

**Structlog Capture for Audit Verification:**
```python
@pytest.fixture
def log_capture():
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
    ))
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    yield buffer
    root_logger.removeHandler(handler)
```

**Prometheus Metrics Snapshot:**
```python
@pytest.fixture
def metrics_snapshot():
    def _snapshot() -> dict[str, float]:
        samples: dict[str, float] = {}
        for metric_family in registry.REGISTRY.collect():
            for sample in metric_family.samples:
                if sample.labels:
                    label_kvs = ",".join(f"{k}={v}" for k, v in sample.labels.items())
                    key = f"{sample.name}[{label_kvs}]"
                else:
                    key = sample.name
                samples[key] = sample.value
        return samples
    return _snapshot
```

**Resetting State Between Tests:**
```python
def _reset_prometheus():
    fail_secure_events.clear()
    requests_total.clear()
```

---

*Testing analysis: 2026-07-06*
