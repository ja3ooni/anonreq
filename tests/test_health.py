"""Tests for the health endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from anonreq.health import router as health_router


@pytest.fixture
def health_app():
    """Create a minimal app with the health router and cache state."""
    app = FastAPI()
    app.include_router(health_router)
    app.state.cache_manager = MagicMock()
    return app


@pytest.fixture
async def client(health_app: FastAPI):
    transport = ASGITransport(app=health_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthEndpoint:
    """Tests for the GET /health endpoint."""

    @patch("anonreq.health.check_cache_health", new_callable=AsyncMock)
    @patch("anonreq.health.check_presidio", new_callable=AsyncMock)
    async def test_health_returns_200_without_dependency_checks(
        self,
        mock_presidio,
        mock_cache_health,
        client: AsyncClient,
    ):
        """GET /health returns 200 and does not probe Valkey or Presidio."""
        response = await client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["components"] == {"gateway": {"status": "healthy"}}
        mock_cache_health.assert_not_awaited()
        mock_presidio.assert_not_awaited()


class TestHealthReadyEndpoint:
    """Tests for the GET /health/ready endpoint."""

    @patch("anonreq.health.check_cache_health", new_callable=AsyncMock)
    @patch("anonreq.health.check_presidio", new_callable=AsyncMock)
    async def test_health_ready_returns_200_when_ready(
        self,
        mock_presidio,
        mock_cache_health,
        health_app: FastAPI,
        client: AsyncClient,
    ):
        """GET /health/ready returns 200 when cache and Presidio are healthy."""
        mock_cache_health.return_value = {
            "reachable": True,
            "persistence_disabled": True,
            "healthy": True,
            "status": "healthy",
        }
        mock_presidio.return_value = True

        response = await client.get("/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["components"]["gateway"]["status"] == "healthy"
        assert body["components"]["valkey"]["status"] == "healthy"
        assert body["components"]["presidio"]["status"] == "healthy"
        mock_cache_health.assert_awaited_once_with(health_app.state.cache_manager)
        mock_presidio.assert_awaited_once()

    @patch("anonreq.health.check_cache_health", new_callable=AsyncMock)
    @patch("anonreq.health.check_presidio", new_callable=AsyncMock)
    async def test_health_ready_returns_503_when_cache_unhealthy(
        self,
        mock_presidio,
        mock_cache_health,
        health_app: FastAPI,
        client: AsyncClient,
    ):
        """GET /health/ready returns 503 when cache health fails."""
        mock_cache_health.return_value = {
            "reachable": False,
            "persistence_disabled": False,
            "healthy": False,
            "status": "unhealthy",
        }
        mock_presidio.return_value = True

        response = await client.get("/health/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["components"]["valkey"]["status"] == "unhealthy"
        assert body["components"]["presidio"]["status"] == "healthy"
        mock_cache_health.assert_awaited_once_with(health_app.state.cache_manager)
        mock_presidio.assert_awaited_once()

    @patch("anonreq.health.check_cache_health", new_callable=AsyncMock)
    @patch("anonreq.health.check_presidio", new_callable=AsyncMock)
    async def test_health_ready_returns_503_when_presidio_unhealthy(
        self,
        mock_presidio,
        mock_cache_health,
        health_app: FastAPI,
        client: AsyncClient,
    ):
        """GET /health/ready returns 503 when Presidio health fails."""
        mock_cache_health.return_value = {
            "reachable": True,
            "persistence_disabled": True,
            "healthy": True,
            "status": "healthy",
        }
        mock_presidio.return_value = False

        response = await client.get("/health/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["components"]["valkey"]["status"] == "healthy"
        assert body["components"]["presidio"]["status"] == "unhealthy"
        mock_cache_health.assert_awaited_once_with(health_app.state.cache_manager)
        mock_presidio.assert_awaited_once()
