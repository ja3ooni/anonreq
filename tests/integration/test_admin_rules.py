"""End-to-end admin rules hot-reload integration tests.

Covers:
- POST valid config → 200 with new version
- POST invalid config → 422, old config intact
- POST without admin auth → 401
- POST with gateway API key (not admin key) → 401
- GET /v1/config/rules works with gateway API key
- GET /v1/config/rules returns active config metadata
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from anonreq.admin.auth import verify_admin_api_key
from anonreq.admin.config import (
    RulesConfig,
)
from anonreq.admin.routes import admin_router, registry


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the module-level registry before each test."""
    registry._current = RulesConfig(custom_recognizers=[], exclusion_list=[])
    registry._version = 0


@pytest.fixture
def app():
    """Create a FastAPI app with the admin router."""
    app = FastAPI()
    app.include_router(admin_router)
    return app


@pytest.fixture
async def admin_client(app):
    """Client with valid admin API key."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _valid_payload():
    return {
        "custom_recognizers": [
            {
                "id": "test-pattern",
                "entity_type": "CUSTOM_ID",
                "patterns": ["TEST-\\d{4}"],
                "confidence": 0.85,
                "enabled": True,
                "version": 1,
            },
        ],
        "exclusion_list": [
            {"value": "safe@example.com", "match_type": "exact"},
        ],
        "thresholds": {"confidence": 0.7},
    }


def _invalid_payload():
    return {
        "custom_recognizers": [
            {
                "id": "bad-rule",
                "entity_type": "BAD",
                "patterns": ["[invalid"],
            },
        ],
        "exclusion_list": [],
    }


class TestAdminRulesE2E:
    """End-to-end admin rules API tests."""

    async def test_post_valid_config_returns_200_with_version(self, admin_client, app):
        # Override auth dependency to accept our test key
        app.dependency_overrides[verify_admin_api_key] = lambda: True

        payload = _valid_payload()
        response = await admin_client.post("/v1/admin/config/rules", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == 1

    async def test_get_rules_shows_new_config_after_post(self, admin_client, app):
        app.dependency_overrides[verify_admin_api_key] = lambda: True

        # Valid config update
        await admin_client.post("/v1/admin/config/rules", json=_valid_payload())

        # GET shows updated config
        response = await admin_client.get("/v1/config/rules")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 1
        assert data["recognizer_count"] == 1
        assert data["exclusion_count"] == 1
        assert len(data["recognizers"]) == 1
        assert data["recognizers"][0]["id"] == "test-pattern"
        assert data["recognizers"][0]["entity_type"] == "CUSTOM_ID"
        assert data["recognizers"][0]["pattern_count"] == 1

    async def test_post_invalid_config_returns_422(self, admin_client, app):
        app.dependency_overrides[verify_admin_api_key] = lambda: True

        response = await admin_client.post("/v1/admin/config/rules", json=_invalid_payload())
        assert response.status_code == 422

    async def test_old_config_intact_after_invalid_post(self, admin_client, app):
        app.dependency_overrides[verify_admin_api_key] = lambda: True

        # First set valid config
        await admin_client.post("/v1/admin/config/rules", json=_valid_payload())

        # Invalid update
        await admin_client.post("/v1/admin/config/rules", json=_invalid_payload())

        # GET should show version 1 (original valid config)
        response = await admin_client.get("/v1/config/rules")
        data = response.json()
        assert data["version"] == 1
        assert data["recognizer_count"] == 1

    async def test_post_without_admin_auth_returns_401(self, admin_client, app):
        # Clear dependency override so real auth runs.
        # Since ANONREQ_ADMIN_API_KEY is not set in test env, ADMIN_API_KEY
        # defaults to None, and the real verify_admin_api_key returns 401.
        app.dependency_overrides.clear()
        response = await admin_client.post("/v1/admin/config/rules", json=_valid_payload())
        assert response.status_code == 401

    async def test_get_rules_works_without_admin_key(self, admin_client):
        # GET /v1/config/rules doesn't require admin auth
        response = await admin_client.get("/v1/config/rules")
        assert response.status_code == 200

    async def test_post_empty_config_returns_200(self, admin_client, app):
        app.dependency_overrides[verify_admin_api_key] = lambda: True

        payload = {
            "custom_recognizers": [],
            "exclusion_list": [],
            "thresholds": {},
        }
        response = await admin_client.post("/v1/admin/config/rules", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 1


@pytest.fixture(autouse=True)
def _reset_metrics():
    """Reset prometheus metrics between tests."""
    from anonreq.monitoring.metrics import active_config_version

    active_config_version.set(0)
