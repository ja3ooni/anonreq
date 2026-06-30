"""Shared test fixtures for AnonReq.

Provides:
- settings_override: fixture to set required env vars before Settings instantiation
- Settings class import for test_config
"""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def settings_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set default required env vars for config tests.

    All required ANONREQ_* variables are pre-configured so that
    the Settings class can be instantiated without reading the
    process environment.
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
