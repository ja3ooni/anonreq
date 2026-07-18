"""Unit tests for TenantRegistry and TenantProfile models.

Per D-05/D-06, verifies YAML seed loading, profile lookup, and
serialization roundtrip.
"""

import pytest

from anonreq.tenant.models import TenantProfile, TenantRegistryModel
from anonreq.tenant.registry import TenantRegistry


@pytest.mark.unit
class TestTenantRegistry:
    """Tests for the TenantRegistry class."""

    def test_loads_from_yaml_seed(self) -> None:
        """TenantRegistry loads seed tenants from config/tenants.yaml."""
        registry = TenantRegistry(yaml_path="config/tenants.yaml")
        profile = registry.get("default")
        assert profile is not None
        assert profile.tenant_id == "default"
        assert profile.enabled is True
        assert profile.display_name == "Default Tenant"

    def test_get_returns_none_for_unknown_tenant(self) -> None:
        """get() returns None for unknown tenant_id."""
        registry = TenantRegistry(yaml_path="config/tenants.yaml")
        assert registry.get("nonexistent") is None

    def test_list_all_returns_all_seeded_tenants(self) -> None:
        """list_all() returns all tenants loaded from YAML."""
        registry = TenantRegistry(yaml_path="config/tenants.yaml")
        tenants = registry.list_all()
        assert len(tenants) >= 1
        tenant_ids = [t.tenant_id for t in tenants]
        assert "default" in tenant_ids

    def test_register_adds_new_tenant(self) -> None:
        """register() adds a new tenant to the in-memory store."""
        registry = TenantRegistry(yaml_path="config/tenants.yaml")
        new_profile = TenantProfile(
            tenant_id="acme-corp",
            display_name="ACME Corporation",
            enabled=True,
        )
        registry.register(new_profile)
        found = registry.get("acme-corp")
        assert found is not None
        assert found.tenant_id == "acme-corp"
        assert found.display_name == "ACME Corporation"

    def test_register_overwrites_existing_tenant(self) -> None:
        """register() replaces an existing tenant with the same ID."""
        registry = TenantRegistry(yaml_path="config/tenants.yaml")
        profile_v1 = TenantProfile(
            tenant_id="test-tenant",
            display_name="Test v1",
        )
        registry.register(profile_v1)
        profile_v2 = TenantProfile(
            tenant_id="test-tenant",
            display_name="Test v2",
        )
        registry.register(profile_v2)
        found = registry.get("test-tenant")
        assert found is not None
        assert found.display_name == "Test v2"


@pytest.mark.unit
class TestTenantProfile:
    """Tests for TenantProfile dataclass."""

    def test_default_values(self) -> None:
        """TenantProfile has sensible defaults."""
        profile = TenantProfile(
            tenant_id="test",
            display_name="Test",
        )
        assert profile.enabled is True
        assert profile.kms_key_arn is None
        assert profile.spend_limits == {}
        assert profile.rate_limits == {}
        assert profile.allowed_providers == []
        assert profile.allowed_models == []


@pytest.mark.unit
class TestTenantRegistryModel:
    """Tests for TenantRegistryModel SQLAlchemy model."""

    def test_from_model_and_to_profile_roundtrip(self) -> None:
        """TenantRegistryModel roundtrip preserves all fields."""
        profile = TenantProfile(
            tenant_id="roundtrip-test",
            display_name="Roundtrip Test",
            enabled=True,
            kms_key_arn="arn:aws:kms:us-east-1:123456:key/test",
            spend_limits={"daily": 1000},
            rate_limits={"rpm": 60},
            allowed_providers=["openai", "anthropic"],
            allowed_models=["gpt-4", "claude-3"],
        )
        model = TenantRegistryModel.from_model(profile)
        restored = model.to_profile()
        assert restored.tenant_id == profile.tenant_id
        assert restored.display_name == profile.display_name
        assert restored.enabled == profile.enabled
        assert restored.kms_key_arn == profile.kms_key_arn
        assert restored.spend_limits == profile.spend_limits
        assert restored.rate_limits == profile.rate_limits
        assert restored.allowed_providers == profile.allowed_providers
        assert restored.allowed_models == profile.allowed_models
