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
from hypothesis import strategies as st

# Set default required env vars BEFORE any test module imports Settings.
# The module-level `settings = Settings()` singleton in config.py is
# instantiated at import time — these defaults ensure it succeeds.
os.environ.setdefault("ANONREQ_API_KEY", "a" * 32)
os.environ.setdefault("ANONREQ_VALKEY_URL", "redis://localhost:6379/0")
os.environ.setdefault("ANONREQ_PRESIDIO_URL", "http://localhost:5001")
os.environ.setdefault("ANONREQ_ADMIN_API_KEY", "adminkey12345678901234567890")



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
def app():
    """Return a minimal FastAPI application instance for testing.

    FastAPI is imported lazily to avoid ~180s import overhead on
    test collection for tests that don't need the app fixture.
    """
    from fastapi import FastAPI

    return FastAPI()


@pytest.fixture
async def test_client(app):
    """Yield an async HTTP client bound to the test app.

    httpx is imported lazily to avoid import overhead on test
    collection for tests that don't need this fixture.
    """
    from httpx import ASGITransport, AsyncClient

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


@st.composite
def token_mapping_strategy(draw):
    """Generate realistic token mappings for streaming property tests."""
    entities = ["EMAIL", "PHONE", "SSN", "IP", "URL", "PERSON", "ORG"]
    selected = draw(st.lists(st.sampled_from(entities), min_size=1, max_size=5, unique=True))
    mapping: dict[str, str] = {}
    alphabet = st.characters(
        whitelist_categories=("L", "N"),
        whitelist_characters="@._-+#",
    )
    for index, entity in enumerate(selected):
        mapping[f"[{entity}_{index}]"] = draw(st.text(min_size=3, max_size=20, alphabet=alphabet))
    return mapping


@st.composite
def chunked_stream_strategy(draw):
    """Generate token-bearing text plus arbitrary chunk boundaries."""
    mapping = draw(token_mapping_strategy())
    parts: list[str] = []
    text_alphabet = st.characters(whitelist_categories=("L",), whitelist_characters=" ")
    for token in mapping:
        parts.append(draw(st.text(min_size=0, max_size=10, alphabet=text_alphabet)))
        parts.append(token)
        parts.append(draw(st.text(min_size=0, max_size=10, alphabet=text_alphabet)))
    full_text = "".join(parts)
    if len(full_text) < 2:
        return full_text, [full_text], mapping
    split_positions = sorted(
        draw(
            st.lists(
                st.integers(min_value=1, max_value=len(full_text) - 1),
                min_size=0,
                max_size=min(20, len(full_text) - 1),
                unique=True,
            )
        )
    )
    chunks: list[str] = []
    last = 0
    for position in split_positions:
        chunks.append(full_text[last:position])
        last = position
    chunks.append(full_text[last:])
    return full_text, [chunk for chunk in chunks if chunk], mapping


@st.composite
def reasoning_stream_strategy(draw):
    """Generate text/reasoning payloads for reasoning leak checks."""
    text = draw(st.text(min_size=5, max_size=50))
    reasoning = draw(st.text(min_size=5, max_size=50))
    positions = draw(
        st.lists(st.integers(min_value=0, max_value=max(len(text) - 1, 0)), min_size=1, max_size=5)
    )
    return text, reasoning, positions


@pytest.fixture
def admin_app():
    from fastapi import FastAPI
    from fastapi.exceptions import HTTPException
    from unittest.mock import AsyncMock
    from anonreq.admin.router import admin_router
    from anonreq.policy.store import PolicyStore
    from anonreq.policy.spend_controller import SpendController
    from anonreq.policy.usage_limiter import UsageLimiter
    from anonreq.exceptions import global_exception_handler, http_exception_handler

    app = FastAPI()
    app.state.policy_store = AsyncMock(spec=PolicyStore)
    app.state.spend_controller = AsyncMock(spec=SpendController)
    app.state.usage_limiter = AsyncMock(spec=UsageLimiter)

    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    @app.middleware("http")
    async def inject_principal(request, call_next):
        # Allow tests to set role and tenant via request headers
        role = request.headers.get("X-AnonReq-Role", "administrator")
        tenant_id = request.headers.get("X-AnonReq-Tenant-ID", "test_tenant")
        request.state.role_principal = {
            "principal_id": "test_admin",
            "role": role,
            "tenant_id": tenant_id,
        }
        return await call_next(request)

    app.include_router(admin_router)
    return app
