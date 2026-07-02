"""Shared fixtures for property-based tests.

Provides:
- ``test_app`` — FastAPI app with mocked pipeline for property tests
- ``property_client`` — AsyncClient bound to ``test_app``
- ``inject_failure`` — async context manager for injecting pipeline failures
- ``metrics_snapshot`` — reads current Prometheus counter values
- ``audit_capture`` — captures structlog audit output
- ``log_capture`` — captures all Python logging output
- ``provider_spy`` — spy tracking ProviderStage call count
- ``cache_manager`` — fakeredis-backed CacheManager for property tests
"""

from __future__ import annotations

import contextlib
import io
import logging
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest
import pytest_asyncio
import structlog
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from anonreq.cache.manager import CacheManager
from anonreq.config import settings
from anonreq.dependencies import auth_context
from anonreq.locale.checksum import ChecksumValidatorRegistry
from anonreq.locale.merger import RecognizerMerger
from anonreq.locale.negotiator import LocaleNegotiator
from anonreq.locale.registry import LocaleRegistry
from anonreq.monitoring.metrics import fail_secure_events, requests_total
from anonreq.routing.chat import router as chat_router, build_pipeline

from tests.property.strategies import FailureMode, PipelinePath


# ── Configure structlog for tests ───────────────────────────────────────────
# Use stdlib LoggerFactory so log output can be captured via stdlib handlers
# in the log_capture fixture. Without this, structlog defaults to PrintLogger
# which writes directly to stdout — invisible to logging handlers.
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _find_stage_by_name(pipeline: Any, name: str) -> Any:
    """Find a pipeline stage by its ``.name`` attribute."""
    for stage in pipeline._stages:
        if stage.name == name:
            return stage
    msg = f"Stage {name!r} not found in pipeline"
    raise ValueError(msg)


def _reset_prometheus() -> None:
    """Reset Prometheus counters for clean test state."""
    fail_secure_events.clear()
    requests_total.clear()


# ── App fixture ─────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def test_app() -> AsyncGenerator[FastAPI, None]:
    """Create a FastAPI app with the chat route, auth, and a real pipeline.

    The pipeline uses a fakeredis-backed CacheManager and a mocked
    PresidioClient so it runs without external dependencies.  The
    ProviderStage HTTP call is mocked to return a canned response.
    """
    _reset_prometheus()

    # ── Create app with chat route ──────────────────────────────────────────
    app = FastAPI()
    app.include_router(chat_router, dependencies=[Depends(auth_context)])

    # Add MetricsMiddleware (same as create_app does)
    from anonreq.monitoring.middleware import MetricsMiddleware
    app.add_middleware(MetricsMiddleware)

    # ── Create fakeredis-backed CacheManager ────────────────────────────────
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cache_mgr = CacheManager.__new__(CacheManager)
    cache_mgr._redis = fake_redis
    cache_mgr._ttl = 300

    # ── Mock PresidioClient ─────────────────────────────────────────────────
    presidio_mock = MagicMock(spec=["analyze_text_nodes", "close"])
    presidio_mock.analyze_text_nodes = AsyncMock(return_value=[[]])
    presidio_mock.close = AsyncMock()

    # ── Mock AliasRegistry ──────────────────────────────────────────────────
    alias_mock = MagicMock()
    alias_mock.resolve = MagicMock(return_value=MagicMock(provider="openai", model="gpt-4o"))

    # ── Mock ProviderRegistry (for streaming path) ─────────────────────────
    provider_registry_mock = MagicMock()
    stream_adapter = MagicMock()
    stream_adapter.capabilities.streaming = True
    # translate_request returns the processed request dict
    stream_adapter.translate_request = MagicMock(return_value={"model": "gpt-4o", "messages": [], "stream": True})

    async def _mock_stream_events(req: object) -> AsyncGenerator[object, None]:
        """Yield a single TEXT_DELTA event then FINISH."""
        from anonreq.streaming.stream_event import (EventType, FinishReason,
                                                     StreamEvent)

        yield StreamEvent(
            event_type=EventType.TEXT_DELTA,
            provider="openai",
            delta_text="Mock streaming response.",
        )
        yield StreamEvent(
            event_type=EventType.FINISH,
            provider="openai",
            finish_reason=FinishReason.STOP,
        )

    stream_adapter.stream_events = _mock_stream_events
    provider_registry_mock.get_adapter = MagicMock(return_value=stream_adapter)

    # ── Mock locale dependencies ───────────────────────────────────────────
    checksum_registry = ChecksumValidatorRegistry()
    locale_registry = LocaleRegistry(checksum_registry=checksum_registry)
    universal_bundle = locale_registry.get("en")
    locale_negotiator = LocaleNegotiator(locale_registry)
    recognizer_merger = RecognizerMerger(universal_bundle)

    # ── Build the full pipeline ─────────────────────────────────────────────
    pipeline = build_pipeline(
        cache_manager=cache_mgr,
        presidio_client=presidio_mock,
        alias_registry=alias_mock,
    )

    # ── Mock the ProviderStage HTTP client so it returns a canned response ──
    # Replace the httpx client on the ProviderStage to avoid real HTTP calls
    provider_stage = _find_stage_by_name(pipeline, "ProviderStage")
    provider_stage._http_client = MagicMock()
    provider_stage._http_client.post = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            is_error=False,
            json=lambda: {
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "created": 1677652288,
                "model": "gpt-4o",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Mock response.",
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )
    )

    # ── Store on app state ──────────────────────────────────────────────────
    app.state.pipeline = pipeline
    app.state.cache_manager = cache_mgr
    app.state.presidio_client = presidio_mock
    app.state.alias_registry = alias_mock
    app.state.provider_registry = provider_registry_mock
    app.state.locale_negotiator = locale_negotiator
    app.state.recognizer_merger = recognizer_merger
    app.state.checksum_registry = checksum_registry
    app.state.active_compliance_presets = []

    yield app

    await fake_redis.aclose()


@pytest_asyncio.fixture
async def property_client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Return an authenticated HTTP client bound to the test app."""
    transport = ASGITransport(app=test_app)
    api_key = settings.API_KEY
    async with AsyncClient(
        transport=transport, base_url="http://test",
    ) as client:
        client.headers["Authorization"] = f"Bearer {api_key}"
        yield client


# ── Pipeline failure injection ──────────────────────────────────────────────


def _get_stage(app: FastAPI, name: str) -> Any:
    """Get a pipeline stage by name from the test app's pipeline."""
    return _find_stage_by_name(app.state.pipeline, name)


@contextlib.asynccontextmanager
async def _inject_detection_failure(app: FastAPI) -> AsyncIterator[None]:
    """Make the DetectionStage raise a PipelineAbortError."""
    stage = _get_stage(app, "DetectionStage")
    original = stage.execute

    async def fail_execute(ctx: Any) -> Any:
        from anonreq.exceptions import PipelineAbortError
        from anonreq.monitoring.metrics import fail_secure_events

        fail_secure_events.labels(failure_type="detection_error").inc()
        ctx.fail_secure(
            PipelineAbortError(
                status_code=500,
                message="Detection stage failed",
                request_id=ctx.request_id,
            )
        )
        return ctx

    stage.execute = fail_execute
    try:
        yield
    finally:
        stage.execute = original


@contextlib.asynccontextmanager
async def _inject_cache_failure(app: FastAPI) -> AsyncIterator[None]:
    """Make the TokenizationStage fail (simulates cache/tokenization error).

    Patches ``TokenizationStage.execute`` directly rather than
    ``CacheManager.store_mapping`` because the cache path within
    TokenizationStage is only reached when classification returns ANONYMIZE
    AND detections are non-empty — a condition that doesn't hold with the
    default mocked pipeline.  Patching the stage directly is simpler and
    ensures the failure injection is independent of pipeline state.
    """
    from anonreq.exceptions import PipelineAbortError

    stage = _get_stage(app, "TokenizationStage")
    original = stage.execute

    async def fail_execute(ctx: Any) -> Any:
        ctx.fail_secure(
            PipelineAbortError(
                status_code=500,
                message="Cache/tokenization stage failed",
                request_id=ctx.request_id,
            )
        )
        return ctx

    stage.execute = fail_execute
    try:
        yield
    finally:
        stage.execute = original


@contextlib.asynccontextmanager
async def _inject_forwarding_guard_failure(app: FastAPI) -> AsyncIterator[None]:
    """Make the ForwardingGuard deny the request.

    The guard denies forwarding when classification is ANONYMIZE but
    required fields (detections, token_mappings) are missing.
    We achieve this by patching the execution to produce a denial through
    the guard's own logic — classification runs first, so we make the
    ClassificationStage return ANONYMIZE and then the guard will DENY
    because there's no detection data.

    Actually, simpler: just replace the ForwardingGuard's execute method
    to directly call ctx.fail_secure with forwarding_denied.
    """
    stage = _get_stage(app, "ForwardingGuard")

    async def fail_guard(ctx: Any) -> Any:
        from anonreq.exceptions import PipelineAbortError
        from anonreq.monitoring.metrics import fail_secure_events

        fail_secure_events.labels(failure_type="forwarding_denied").inc()
        ctx.fail_secure(
            PipelineAbortError(
                status_code=503,
                message="Forwarding guard denied",
                request_id=ctx.request_id,
            )
        )
        return ctx

    original = stage.execute
    stage.execute = fail_guard
    try:
        yield
    finally:
        stage.execute = original


@contextlib.asynccontextmanager
async def _inject_provider_timeout(app: FastAPI) -> AsyncIterator[None]:
    """Make the ProviderStage HTTP call raise `httpx.TimeoutException`.

    ProviderStage catches ``httpx.TimeoutException`` specifically to return
    a 504 status.  Using the correct exception type ensures the production
    error path is exercised.
    """
    import httpx

    stage = _get_stage(app, "ProviderStage")
    original_client = stage._http_client
    mock_client = MagicMock()
    mock_client.post = AsyncMock(
        side_effect=httpx.TimeoutException("Simulated provider timeout"),
    )
    stage._http_client = mock_client
    try:
        yield
    finally:
        stage._http_client = original_client


@contextlib.asynccontextmanager
async def _inject_circuit_breaker(app: FastAPI) -> AsyncIterator[None]:
    """Simulate circuit breaker: provider timeout failure.

    The circuit breaker pattern in the MVP is implicit — repeated failures
    from ProviderStage (timeouts) cascade through the pipeline.  We inject
    a provider timeout to simulate the Nth failure.
    """
    async with _inject_provider_timeout(app):
        yield


# Map failure modes to injectors
_FAILURE_INJECTORS: dict[FailureMode, Any] = {
    FailureMode.DETECTION: _inject_detection_failure,
    FailureMode.CACHE: _inject_cache_failure,
    FailureMode.FORWARDING_GUARD: _inject_forwarding_guard_failure,
    FailureMode.PROVIDER_TIMEOUT: _inject_provider_timeout,
    FailureMode.CIRCUIT_BREAKER: _inject_circuit_breaker,
}


@contextlib.asynccontextmanager
async def inject_failure(
    failure_mode: FailureMode,
    pipeline_path: PipelinePath,
    app: FastAPI,
) -> AsyncIterator[None]:
    """Inject a failure at the specified pipeline point.

    Sets up mocks at the appropriate injection point for the given
    ``failure_mode`` and ``pipeline_path``, yields, and tears down.

    Args:
        failure_mode: The failure mode to simulate.
        pipeline_path: NON_STREAMING or STREAMING (currently the injector
            is the same for both; streaming-specific injection can be
            added when the streaming pipeline is exercised end-to-end).
        app: The test FastAPI app with the pipeline on ``app.state``.
    """
    injector = _FAILURE_INJECTORS.get(failure_mode)
    if injector is None:
        msg = f"No injector for failure mode: {failure_mode}"
        raise ValueError(msg)
    async with injector(app):
        yield


# ── Metrics snapshot ────────────────────────────────────────────────────────


@pytest.fixture
def metrics_snapshot() -> Any:
    """Return a function that captures current Prometheus metric sample values.

    Returns a flat dict keyed by ``<metric_name>[<label_kv>]`` (or
    ``<metric_name>`` for unlabeled metrics) with float values.  Tests
    can check for specific keys to verify increments.

    Usage::

        snap = metrics_snapshot()
        ...  # run request that increments
        after = metrics_snapshot()
        assert after.get("anonreq_fail_secure_events_total[failure_type=detection_error]",
        ) is not None
    """
    from prometheus_client import registry

    def _snapshot() -> dict[str, float]:
        samples: dict[str, float] = {}
        for metric_family in registry.REGISTRY.collect():
            for sample in metric_family.samples:
                if sample.labels:
                    label_kvs = ",".join(
                        f"{k}={v}" for k, v in sample.labels.items()
                    )
                    key = f"{sample.name}[{label_kvs}]"
                else:
                    key = sample.name
                samples[key] = sample.value
        return samples

    return _snapshot


# ── Audit capture fixture ───────────────────────────────────────────────────


@pytest.fixture
def audit_capture() -> Any:
    """Capture structured audit log output in-memory.

    Returns an ``io.StringIO`` buffer with all structlog output.
    Tests can parse the buffer content to find audit entries.
    """
    buffer = io.StringIO()

    # We capture via the structlog/standard logging root handler
    handler = logging.StreamHandler(buffer)
    handler.setLevel(logging.INFO)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    yield buffer

    root_logger.removeHandler(handler)


# ── Log capture fixture ─────────────────────────────────────────────────────


@pytest.fixture
def log_capture() -> Any:
    """Capture all log output in-memory for PII scanning.

    Uses ``structlog.stdlib.ProcessorFormatter`` with ``JSONRenderer`` so
    the captured output includes structured fields in JSON format (matching
    the production log format).  Returns an ``io.StringIO`` buffer whose
    content tests can scan for PII entity value substrings.
    """
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
        )
    )
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    yield buffer

    root_logger.removeHandler(handler)


# ── Provider spy ────────────────────────────────────────────────────────────


@pytest.fixture
def provider_spy(test_app: FastAPI) -> Any:
    """Track whether ProviderStage was called.

    Returns a ``MagicMock`` whose ``called`` attribute indicates whether
    the provider was invoked.  This is reset before each test.
    """
    spy = MagicMock()
    spy.called = False
    spy.call_count = 0

    stage = _get_stage(test_app, "ProviderStage")
    original = stage.execute

    async def tracking_execute(ctx: Any) -> Any:
        spy.called = True
        spy.call_count += 1
        return await original(ctx)

    stage.execute = tracking_execute
    yield spy
    stage.execute = original


# ── Cache manager fixture (for cleanup / key inspection) ────────────────────


@pytest_asyncio.fixture
async def property_cache_manager(test_app: FastAPI) -> CacheManager:
    """Return the CacheManager instance used by the test app's pipeline."""
    return test_app.state.cache_manager


@pytest_asyncio.fixture
async def app_cleanup(property_client: AsyncClient) -> AsyncGenerator[None, None]:
    """Fixture that cleans up after each property test.

    Removes any session mappings left in the fake cache.
    """
    yield
    # Cleanup happens via fixture scope teardown of test_app
