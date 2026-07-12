"""Tests for policy CRUD admin endpoints.

Tests cover:
- GET /v1/admin/policies — list policies for authenticated tenant
- PUT /v1/admin/policies/{policy_id} — upsert policy rule
- RBAC enforcement (operator can read, admin can write)
- Validation (422 for invalid input)
- Version bump on update
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from anonreq.admin.router import admin_router
from anonreq.policy.models import PolicyAction, PolicyRule

# The admin router requires Authorization: Bearer <ADMIN_API_KEY> at the
# router level via require_auth / verify_admin_api_key. All tests that
# need authenticated access must send this header.
_ADMIN_AUTH_KEY = os.environ.get(
    "ANONREQ_ADMIN_API_KEY", "adminkey12345678901234567890"
)


def _auth_header() -> dict[str, str]:
    """Return Authorization header for admin API key auth."""
    return {"Authorization": f"Bearer {_ADMIN_AUTH_KEY}"}


def _sample_policy_rules() -> list[PolicyRule]:
    """Return sample PolicyRule instances for testing."""
    return [
        PolicyRule(
            rule_id="rule_001",
            action=PolicyAction.BLOCK,
            priority=10,
            enabled=True,
            conditions={"model": "gpt-4"},
            tenant_id="test_tenant",
        ),
        PolicyRule(
            rule_id="rule_002",
            action=PolicyAction.ALLOW,
            priority=5,
            enabled=False,
            conditions={"model": "claude-3"},
            tenant_id="test_tenant",
        ),
        PolicyRule(
            rule_id="rule_003",
            action=PolicyAction.MONITOR,
            priority=1,
            enabled=True,
            conditions={"model": "gpt-3.5-turbo"},
            tenant_id="test_tenant",
        ),
    ]


def _make_test_app(role: str = "administrator") -> FastAPI:
    """Create a FastAPI app with the admin router and role principal set.

    Also wires a mock PolicyStore onto app.state so route handlers
    that depend on the policy store can operate.

    Args:
        role: The role to assign to the authenticated principal.

    Returns:
        A configured FastAPI app ready for TestClient.
    """
    app = FastAPI()

    # Wire a mock PolicyStore
    mock_store = AsyncMock()
    sample_rules = _sample_policy_rules()
    mock_store.load_policies.return_value = list(sample_rules)
    mock_store.get_policy.return_value = None  # default: no existing rule
    mock_store.set_tenant_policy = AsyncMock()

    # Track stored rules for upsert behavior
    stored_rules: dict[str, list[PolicyRule]] = {
        "test_tenant": list(sample_rules),
    }

    async def mock_load_policies(tenant_id: str) -> list[PolicyRule]:
        return list(stored_rules.get(tenant_id, []))

    async def mock_get_policy(rule_id: str, tenant_id: str | None = None) -> PolicyRule | None:
        rules = stored_rules.get(tenant_id or "test_tenant", [])
        for r in rules:
            if r.rule_id == rule_id:
                return r
        return None

    async def mock_set_tenant_policy(tenant_id: str, rules: list[PolicyRule]) -> None:
        stored_rules[tenant_id] = list(rules)

    mock_store.load_policies.side_effect = mock_load_policies
    mock_store.get_policy.side_effect = mock_get_policy
    mock_store.set_tenant_policy.side_effect = mock_set_tenant_policy

    app.state.policy_store = mock_store

    @app.middleware("http")
    async def inject_principal(request, call_next):
        request.state.role_principal = {
            "principal_id": "test_admin",
            "role": role,
            "tenant_id": "test_tenant",
        }
        return await call_next(request)

    app.include_router(admin_router)
    return app


class TestPolicyList:
    """Tests for GET /v1/admin/policies."""

    def test_list_returns_all_policies_for_tenant(self):
        """GET returns all policies for the authenticated tenant."""
        app = _make_test_app("operator")
        client = TestClient(app)
        headers = _auth_header()
        response = client.get("/v1/admin/policies", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert "policies" in body
        assert "total" in body
        assert "version" in body
        # Stub returns empty — replace with real implementation

    def test_list_filters_by_enabled_status(self):
        """GET /policies?enabled=true returns only enabled policies."""
        app = _make_test_app("operator")
        client = TestClient(app)
        headers = _auth_header()
        response = client.get("/v1/admin/policies?enabled=true", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert all(p.get("enabled", False) for p in body["policies"])

    def test_list_returns_401_without_auth(self):
        """Request without admin API key returns 401."""
        app = _make_test_app("operator")
        client = TestClient(app)
        response = client.get("/v1/admin/policies", headers={})
        assert response.status_code == 401

    def test_operator_can_list_policies(self):
        """OPERATOR role can list policies."""
        app = _make_test_app("operator")
        client = TestClient(app)
        headers = _auth_header()
        response = client.get("/v1/admin/policies", headers=headers)
        assert response.status_code == 200

    def test_read_only_cannot_list_policies(self):
        """READ_ONLY role cannot list policies (needs OPERATOR)."""
        app = _make_test_app("read_only")
        client = TestClient(app)
        headers = _auth_header()
        response = client.get("/v1/admin/policies", headers=headers)
        # Stub doesn't enforce RBAC — should return 403 with real impl
        assert response.status_code == 403

    def test_unauthenticated_access_returns_401_for_list(self):
        """Request without admin API key returns 401."""
        app = FastAPI()
        app.include_router(admin_router)
        client = TestClient(app)
        response = client.get("/v1/admin/policies")
        assert response.status_code == 401


class TestPolicyUpdate:
    """Tests for PUT /v1/admin/policies/{policy_id}."""

    def test_put_creates_new_policy_rule(self):
        """PUT with new rule_id creates a policy (upsert)."""
        app = _make_test_app("administrator")
        client = TestClient(app)
        headers = _auth_header()
        payload = {
            "rule_id": "new_rule_001",
            "action": "BLOCK",
            "priority": 10,
            "enabled": True,
            "conditions": {"model": "gpt-4"},
        }
        response = client.put(
            "/v1/admin/policies/new_rule_001", json=payload, headers=headers
        )
        # Stub returns policy=None — with real impl should return the created policy
        assert response.status_code == 200
        body = response.json()
        assert "policy" in body
        assert body["policy"] is not None

    def test_put_updates_existing_policy_with_version_bump(self):
        """PUT on existing rule_id updates policy and bumps version."""
        app = _make_test_app("administrator")
        client = TestClient(app)
        headers = _auth_header()
        payload = {
            "rule_id": "existing_rule",
            "action": "BLOCK",
            "priority": 20,
            "enabled": True,
        }
        first = client.put(
            "/v1/admin/policies/existing_rule", json=payload, headers=headers
        )
        assert first.status_code == 200
        payload["priority"] = 30
        second = client.put(
            "/v1/admin/policies/existing_rule", json=payload, headers=headers
        )
        assert second.status_code == 200
        v1 = first.json()["version"]
        v2 = second.json()["version"]
        # Version should bump on update
        assert v2 != v1

    def test_put_with_invalid_body_returns_422(self):
        """PUT with invalid policy body returns 422 with validation errors."""
        app = _make_test_app("administrator")
        client = TestClient(app)
        headers = _auth_header()
        # Missing required 'action' field
        response = client.put(
            "/v1/admin/policies/invalid_rule",
            json={"rule_id": "invalid"},
            headers=headers,
        )
        # Stub might accept — real implementation should reject
        assert response.status_code == 422

    def test_put_requires_administrator_role(self):
        """READ_ONLY role cannot PUT (needs ADMINISTRATOR)."""
        app = _make_test_app("read_only")
        client = TestClient(app)
        headers = _auth_header()
        payload = {"rule_id": "test", "action": "BLOCK", "priority": 1}
        response = client.put(
            "/v1/admin/policies/test", json=payload, headers=headers
        )
        # Stub doesn't enforce RBAC — should return 403 with real impl
        assert response.status_code == 403

    def test_operator_cannot_put_policy(self):
        """OPERATOR role cannot PUT (needs ADMINISTRATOR)."""
        app = _make_test_app("operator")
        client = TestClient(app)
        headers = _auth_header()
        payload = {"rule_id": "test", "action": "BLOCK", "priority": 1}
        response = client.put(
            "/v1/admin/policies/test", json=payload, headers=headers
        )
        assert response.status_code == 403

    def test_unauthenticated_put_returns_401(self):
        """Request without admin API key returns 401."""
        app = FastAPI()
        app.include_router(admin_router)
        client = TestClient(app)
        payload = {"rule_id": "test", "action": "BLOCK", "priority": 1}
        response = client.put("/v1/admin/policies/test", json=payload)
        assert response.status_code == 401


class TestPolicyUpdateValidation:
    """Tests for request body validation on PUT."""

    def test_rejects_empty_policy_id(self):
        """Empty policy_id is rejected."""
        app = _make_test_app("administrator")
        client = TestClient(app)
        headers = _auth_header()
        response = client.put("/v1/admin/policies/", json={}, headers=headers)
        assert response.status_code in (405, 404)

    def test_rejects_unknown_action(self):
        """Unknown PolicyAction value returns 422."""
        app = _make_test_app("administrator")
        client = TestClient(app)
        headers = _auth_header()
        payload = {
            "rule_id": "bad_action_rule",
            "action": "INVALID_ACTION",
            "priority": 1,
        }
        response = client.put(
            "/v1/admin/policies/bad_action_rule",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 422

    def test_rejects_negative_priority(self):
        """Negative priority is rejected."""
        app = _make_test_app("administrator")
        client = TestClient(app)
        headers = _auth_header()
        payload = {
            "rule_id": "neg_priority",
            "action": "BLOCK",
            "priority": -1,
        }
        response = client.put(
            "/v1/admin/policies/neg_priority",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 422

    def test_rejects_extra_fields(self):
        """Extra fields not in schema are rejected (model_config extra=forbid)."""
        app = _make_test_app("administrator")
        client = TestClient(app)
        headers = _auth_header()
        payload = {
            "rule_id": "extra_fields",
            "action": "ALLOW",
            "priority": 5,
            "unknown_field": "should_not_be_allowed",
        }
        response = client.put(
            "/v1/admin/policies/extra_fields",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 422
