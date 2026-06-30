"""Shared test fixtures for AnonReq.

Provides:
- Module-level env vars set for Settings singleton import
- settings_override fixture for per-test env customization
- app and test_client fixtures for future integration tests
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
