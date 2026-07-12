"""Tests for OpenAPI specification.

Validates that openapi.yaml contains all required admin routes,
correct security requirements, and RBAC metadata.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_spec_structure():
    """Verify that the OpenAPI spec has the correct paths and metadata."""
    spec_path = Path("openapi/openapi.yaml")
    assert spec_path.exists()

    with open(spec_path) as f:
        spec = yaml.safe_load(f)

    # OpenAPI version 3.1.0
    assert spec["openapi"] == "3.1.0"

    paths = spec["paths"]

    # Verify Phase 8 endpoints exist
    assert "/v1/admin/policies" in paths
    assert "/v1/admin/policies/{policy_id}" in paths
    assert "/v1/admin/tenants/{tenant_id}/usage" in paths

    # Verify methods
    assert "get" in paths["/v1/admin/policies"]
    assert "put" in paths["/v1/admin/policies/{policy_id}"]
    assert "get" in paths["/v1/admin/tenants/{tenant_id}/usage"]

    # Verify security and x-rbac metadata
    admin_paths = [
        "/v1/admin/policies",
        "/v1/admin/policies/{policy_id}",
        "/v1/admin/tenants/{tenant_id}/usage",
    ]
    for path in admin_paths:
        for method in paths[path]:
            op = paths[path][method]
            assert "security" in op, f"Missing security requirement in {method} {path}"
            assert any("BearerAuth" in scheme for scheme in op["security"]), f"BearerAuth missing in {method} {path}"  # noqa: E501
            assert "x-rbac" in op, f"Missing x-rbac metadata in {method} {path}"
            assert "minimum_role" in op["x-rbac"], f"x-rbac must specify minimum_role in {method} {path}"  # noqa: E501

    # Verify component schemas
    components = spec.get("components", {})
    schemas = components.get("schemas", {})
    assert "PolicyRule" in schemas
    assert "PolicyDecision" in schemas
    assert "UsageRecord" in schemas
    assert "PolicyAction" in schemas
