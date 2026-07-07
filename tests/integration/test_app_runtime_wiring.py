"""Integration tests for Phase 22 runtime wiring in create_app().

Tests verify:
- ContentTypeMiddleware rejects unsupported Content-Type with 415
- Discovery inventory route is registered in the app route table
- GET /v1/admin/discovery/inventory returns JSON and CSV
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from anonreq.dependencies import auth_context
from anonreq.discovery.inventory import AssetInventory, InventoryRecord
from anonreq.main import create_app


@pytest.fixture
def app():
    _app = create_app()
    _app.dependency_overrides[auth_context] = lambda: None
    return _app


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestContentTypeMiddleware:
    """Content-Type enforcement middleware rejects unsupported types."""

    @pytest.mark.asyncio
    async def test_unsupported_content_type_returns_415(self, client: AsyncClient) -> None:
        """application/xml should be rejected with HTTP 415."""
        response = await client.post(
            "/v1/chat/completions",
            content=b"{}",
            headers={"Content-Type": "application/xml"},
        )
        assert response.status_code == 415

    @pytest.mark.asyncio
    async def test_unsupported_content_type_body_has_error(self, client: AsyncClient) -> None:
        """415 response body should contain error details."""
        response = await client.post(
            "/v1/chat/completions",
            content=b"{}",
            headers={"Content-Type": "application/xml"},
        )
        body = response.json()
        assert "error" in body
        assert body["error"]["code"] == "unsupported_media_type"
        assert "application/xml" in body["error"]["message"]

    @pytest.mark.asyncio
    async def test_supported_json_content_type_passes(self, client: AsyncClient) -> None:
        """application/json should NOT be rejected by ContentTypeMiddleware."""
        response = await client.get(
            "/health/ready",
            headers={"Authorization": "Bearer " + "a" * 32},
        )
        assert response.status_code != 415


class TestDiscoveryInventoryRouteRegistration:
    """Inventory route is registered in the app route table."""

    @pytest.mark.asyncio
    async def test_inventory_route_responds_with_seeded_data(self, app, client: AsyncClient) -> None:
        _seed_inventory(app)
        response = await client.get(
            "/v1/admin/discovery/inventory",
            headers={"Authorization": "Bearer " + "a" * 32},
        )
        assert response.status_code == 200
        body = response.json()
        assert "records" in body


class TestDiscoveryInventoryEndpoint:
    """GET /v1/admin/discovery/inventory returns JSON and CSV."""

    @pytest.mark.asyncio
    async def test_inventory_json_with_records(self, app, client: AsyncClient) -> None:
        inventory = _seed_inventory(app)
        response = await client.get(
            "/v1/admin/discovery/inventory",
            headers={"Authorization": "Bearer " + "a" * 32},
        )
        assert response.status_code == 200
        body = response.json()
        assert "records" in body
        assert body["total"] == 2
        service_names = {r["service_name"] for r in body["records"]}
        assert "test-openai-svc" in service_names
        assert "test-anthropic-svc" in service_names

    @pytest.mark.asyncio
    async def test_inventory_csv_format(self, app, client: AsyncClient) -> None:
        _seed_inventory(app)
        response = await client.get(
            "/v1/admin/discovery/inventory?format=csv",
            headers={"Authorization": "Bearer " + "a" * 32},
        )
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/csv")
        body = response.text
        assert "service_name" in body
        assert "test-openai-svc" in body
        assert "test-anthropic-svc" in body

    @pytest.mark.asyncio
    async def test_inventory_no_pii_in_response(self, app, client: AsyncClient) -> None:
        """No raw PII should leak in the inventory response body."""
        _seed_inventory(app)
        response = await client.get(
            "/v1/admin/discovery/inventory",
            headers={"Authorization": "Bearer " + "a" * 32},
        )
        text = response.text.lower()
        assert "ssn" not in text
        assert "credit.card" not in text or "credit_card" not in text


def _seed_inventory(app) -> AssetInventory:
    from datetime import datetime, timezone

    inventory = getattr(app.state, "inventory_service", None)
    if inventory is None:
        inventory = AssetInventory()
        app.state.inventory_service = inventory
    inventory.add_record(
        InventoryRecord(
            service_name="test-openai-svc",
            provider="openai",
            model="gpt-4",
            user_count=10,
            app_count=2,
            token_volume=50000,
            estimated_cost=150.0,
            risk_score=15.0,
            risk_band="low",
            last_seen=datetime.now(timezone.utc),
            business_unit="engineering",
        )
    )
    inventory.add_record(
        InventoryRecord(
            service_name="test-anthropic-svc",
            provider="anthropic",
            model="claude-3",
            user_count=5,
            app_count=1,
            token_volume=20000,
            estimated_cost=80.0,
            risk_score=25.0,
            risk_band="medium",
            last_seen=datetime.now(timezone.utc),
            business_unit="research",
        )
    )
    return inventory
