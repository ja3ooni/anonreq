"""Shared test fixtures for AnonReq.

Provides:
- Module-level env vars set for Settings singleton import
- settings_override fixture for per-test env customization
- app and test_client fixtures for future integration tests
- cache_manager fixture backed by fakeredis for Phase 2 cache tests
- sample_text_nodes fixture for detection/pipeline tests
- sample_chat_request fixture for route/pipeline tests
- processing_context fixture for pipeline stage tests
"""

import os
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Set default required env vars BEFORE any test module imports Settings.
# The module-level `settings = Settings()` singleton in config.py is
# instantiated at import time — these defaults ensure it succeeds.
os.environ.setdefault("ANONREQ_API_KEY", "a" * 32)
os.environ.setdefault("ANONREQ_VALKEY_URL", "redis://localhost:6379/0")
os.environ.setdefault("ANONREQ_PRESIDIO_URL", "http://localhost:5001")


@pytest.fixture
def settings_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set default required env vars for config tests.

    This fixture is used by tests that need fresh Settings instances
    with all required vars. Individual tests can then override specific
    vars via additional monkeypatch calls before calling Settings().
    """
    monkeypatch.setenv("ANONREQ_API_KEY", "a" * 32)
    monkeypatch.setenv("ANONREQ_VALKEY_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("ANONREQ_PRESIDIO_URL", "http://localhost:5001")


@pytest.fixture
def app() -> FastAPI:
    """Return a minimal FastAPI application instance for testing."""
    return FastAPI()


@pytest.fixture
async def test_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Yield an async HTTP client bound to the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Phase 2 Shared Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def cache_manager():
    """Create a CacheManager backed by fakeredis for testing.

    Uses ``fakeredis.aioredis.FakeRedis`` to simulate Valkey without
    requiring a running Valkey container.  The fixture yields a
    ``CacheManager`` instance and cleans up the fake redis connection
    on teardown.

    Imports are lazy to avoid slow redis-py startup on test collection.
    """
    import fakeredis.aioredis
    from anonreq.cache.manager import CacheManager

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    manager = CacheManager.__new__(CacheManager)
    manager._redis = fake_redis
    manager._ttl = 300
    yield manager
    await fake_redis.aclose()


@pytest.fixture
def sample_text_nodes() -> list[dict[str, str]]:
    """Return a list of TextNode dicts for test reuse across Phase 2.

    Provides two text nodes — one user message with detectable PII and
    one assistant response without PII — suitable for detection,
    classification, and pipeline tests.
    """
    return [
        {
            "path": "messages[0].content",
            "role": "user",
            "value": "My email is john@example.com and phone is +1-555-123-4567",
        },
        {
            "path": "messages[1].content",
            "role": "assistant",
            "value": "I'll contact you at that number.",
        },
    ]


@pytest.fixture
def sample_chat_request() -> dict[str, Any]:
    """Return a valid ChatRequest dict for pipeline and route tests.

    Mimics a minimal OpenAI-compatible non-streaming chat completion
    request with one user message containing PII.
    """
    return {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "My email is john@example.com"}],
        "stream": False,
    }


@pytest.fixture
def processing_context():
    """Return a ProcessingContext with defaults for pipeline stage tests.

    Provides a minimal context with ``request_id`` and ``tenant_id``
    set.  Individual tests can assign additional fields as needed.
    """
    from anonreq.models.processing_context import ProcessingContext

    return ProcessingContext(request_id="test_req_001", tenant_id="default")
