"""Tests for the health endpoint.

Tests verify:
- GET /health returns 200 with component status when all healthy
- GET /health returns 503 when a component is unhealthy
- Response includes valkey, presidio, and gateway status fields
- GET /health/ready also works
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from anonreq.health import router as health_router


@pytest.fixture
def health_app():
    """Create a minimal app with only the health router."""
    app = FastAPI()
    app.include_router(health_router)
    return app


@pytest.fixture
async def client(health_app: FastAPI):
    transport = ASGITransport(app=health_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthEndpoint:
    """Tests for the GET /health endpoint."""

    @patch("anonreq.health.check_valkey", return_value=True)
    @patch("anonreq.health.check_presidio", return_value=True)
    async def test_health_returns_200_when_healthy(
        self, _mock_presidio, _mock_valkey, client: AsyncClient  # noqa: PT019
    ):
        """Test 1: GET /health returns 200 when all components healthy."""
        response = await client.get("/health")
        assert response.status_code == 200

    @patch("anonreq.health.check_valkey", return_value=True)
    @patch("anonreq.health.check_presidio", return_value=True)
    async def test_health_response_includes_component_status(
        self, _mock_presidio, _mock_valkey, client: AsyncClient  # noqa: PT019
    ):
        """Test 2: /health response includes component status fields."""
        response = await client.get("/health")
        body = response.json()
        assert "status" in body
        assert "version" in body
        assert "components" in body
        assert "valkey" in body["components"]
        assert "presidio" in body["components"]
        assert "gateway" in body["components"]

    @patch("anonreq.health.check_valkey", return_value=True)
    @patch("anonreq.health.check_presidio", return_value=True)
    async def test_health_healthy_status(
        self, _mock_presidio, _mock_valkey, client: AsyncClient  # noqa: PT019
    ):
        """All components healthy → overall status 'healthy'."""
        response = await client.get("/health")
        body = response.json()
        assert body["status"] == "healthy"
        assert body["components"]["valkey"]["status"] == "healthy"
        assert body["components"]["presidio"]["status"] == "healthy"
        assert body["components"]["gateway"]["status"] == "healthy"

    @patch("anonreq.health.check_valkey", return_value=False)
    @patch("anonreq.health.check_presidio", return_value=True)
    async def test_health_503_when_valkey_unhealthy(
        self, _mock_presidio, _mock_valkey, client: AsyncClient  # noqa: PT019
    ):
        """Valkey unhealthy → 503 with degraded status."""
        response = await client.get("/health")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["components"]["valkey"]["status"] == "unhealthy"
        assert body["components"]["presidio"]["status"] == "healthy"

    @patch("anonreq.health.check_valkey", return_value=True)
    @patch("anonreq.health.check_presidio", return_value=False)
    async def test_health_503_when_presidio_unhealthy(
        self, _mock_presidio, _mock_valkey, client: AsyncClient  # noqa: PT019
    ):
        """Presidio unhealthy → 503 with degraded status."""
        response = await client.get("/health")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["components"]["presidio"]["status"] == "unhealthy"
        assert body["components"]["valkey"]["status"] == "healthy"

    @patch("anonreq.health.check_valkey", return_value=False)
    @patch("anonreq.health.check_presidio", return_value=False)
    async def test_health_503_when_all_unhealthy(
        self, _mock_presidio, _mock_valkey, client: AsyncClient  # noqa: PT019
    ):
        """All components unhealthy → 503 with degraded status."""
        response = await client.get("/health")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["components"]["valkey"]["status"] == "unhealthy"
        assert body["components"]["presidio"]["status"] == "unhealthy"


class TestHealthReadyEndpoint:
    """Tests for the GET /health/ready endpoint."""

    @patch("anonreq.health.check_valkey", return_value=True)
    @patch("anonreq.health.check_presidio", return_value=True)
    async def test_health_ready_returns_200(
        self, _mock_presidio, _mock_valkey, client: AsyncClient  # noqa: PT019
    ):
        """GET /health/ready returns 200 when healthy."""
        response = await client.get("/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
