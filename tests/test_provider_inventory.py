"""Tests for third-party provider inventory with DORA ICT risk.

Tests provider CRUD, suspend/unsuspend, concentration risk flagging,
and DORA ICT critical designation per D-009 through D-012.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from anonreq.models.governance import ProviderRecord


# ── ProviderRecord Validation ─────────────────────────────────────────────


class TestProviderRecordValidation:
    """Test ProviderRecord pydantic model validation and defaults."""

    def test_create_minimal_provider_record(self):
        """Test 1: create_provider_record stores provider with DORA ICT fields."""
        record = ProviderRecord(
            name="OpenAI",
            provider_type="llm",
            dora_ict_critical=True,
        )
        assert record.name == "OpenAI"
        assert record.provider_type == "llm"
        assert record.dora_ict_critical is True
        assert record.status == "active"
        assert record.concentration_risk is False
        assert record.review_cycle_days == 365

    def test_provider_record_with_all_fields(self):
        """Test provider record with all fields populated."""
        now = datetime.now(timezone.utc)
        record = ProviderRecord(
            id="prov_001",
            name="Anthropic",
            provider_type="llm",
            status="active",
            lifecycle_object_id="life_001",
            dora_ict_critical=True,
            concentration_risk=True,
            concentration_risk_justification="High usage concentration",
            concentration_risk_justification_date=now,
            contract_end_date=now,
            review_cycle_days=180,
            last_review_date=now,
            next_review_date=now,
            created_at=now,
            updated_at=now,
        )
        assert record.id == "prov_001"
        assert record.name == "Anthropic"
        assert record.dora_ict_critical is True
        assert record.concentration_risk is True
        assert record.concentration_risk_justification == "High usage concentration"

    def test_default_status_active(self):
        """Default status should be 'active'."""
        record = ProviderRecord(name="OpenAI", provider_type="llm")
        assert record.status == "active"

    def test_default_review_cycle_365(self):
        """Default review cycle should be 365 days."""
        record = ProviderRecord(name="OpenAI", provider_type="llm")
        assert record.review_cycle_days == 365

    def test_default_dora_ict_critical_false(self):
        """Default dora_ict_critical should be False."""
        record = ProviderRecord(name="OpenAI", provider_type="llm")
        assert record.dora_ict_critical is False

    def test_default_concentration_risk_false(self):
        """Default concentration_risk should be False."""
        record = ProviderRecord(name="OpenAI", provider_type="llm")
        assert record.concentration_risk is False

    def test_empty_name_allowed_no_validation(self):
        """Empty name is allowed (no custom validator)."""
        record = ProviderRecord(name="", provider_type="llm")
        assert record.name == ""


def _make_mock_provider_orm(**overrides):
    """Create a MagicMock with ProviderAnonReqModel-like attributes."""
    now = datetime.now(timezone.utc)
    attrs = {
        "provider_id": "prov_001",
        "name": "OpenAI",
        "provider_type": "llm",
        "status": "active",
        "lifecycle_object_id": "life_001",
        "dora_ict_critical": False,
        "concentration_risk": False,
        "concentration_risk_justification": None,
        "concentration_risk_justification_date": None,
        "contract_end_date": None,
        "review_cycle_days": 365,
        "last_review_date": None,
        "next_review_date": None,
        "created_at": now,
        "updated_at": now,
    }
    attrs.update(overrides)
    m = MagicMock()
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


class TestProviderInventory:
    """Test ProviderInventory class with mock DB and lifecycle manager."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_lifecycle(self):
        return AsyncMock()

    @pytest.fixture
    def inventory(self, mock_db, mock_lifecycle):
        from anonreq.governance.provider_inventory import ProviderInventory

        return ProviderInventory(db=mock_db, lifecycle_manager=mock_lifecycle)

    async def test_create_provider_record(self, inventory, mock_lifecycle):
        """Test 1: create_provider_record stores provider with DORA ICT fields."""
        mock_stage = MagicMock()
        mock_stage.value = "DESIGN"
        mock_lifecycle.get_current_stage.return_value = mock_stage

        result = await inventory.create_provider_record(
            name="OpenAI",
            provider_type="llm",
            dora_ict_critical=True,
        )

        assert result.name == "OpenAI"
        assert result.provider_type == "llm"
        assert result.dora_ict_critical is True
        assert result.status == "active"

    async def test_get_provider_record_returns_none_for_missing(self, inventory, mock_db):
        """Test 2: get_provider_record retrieves by id."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await inventory.get_provider_record("nonexistent")
        assert result is None

    async def test_get_provider_record_found(self, inventory, mock_db):
        """Test 2: get_provider_record returns record when found."""
        mock_orm = _make_mock_provider_orm(provider_id="prov_001")
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.one_or_none.return_value = mock_orm
        mock_db.execute.return_value = mock_result

        result = await inventory.get_provider_record("prov_001")
        assert result is not None
        assert result.id == "prov_001"
        assert result.name == "OpenAI"

    async def test_suspend_provider_sets_status_suspended(self, inventory, mock_db):
        """Test 3: suspend_provider sets status='suspended'."""
        mock_orm = _make_mock_provider_orm(provider_id="prov_001", status="active")
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.one_or_none.return_value = mock_orm
        mock_db.execute.return_value = mock_result
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await inventory.suspend_provider(
            provider_id="prov_001",
            reason="Security incident",
            suspended_by="admin",
        )
        assert result.status == "suspended"
        mock_db.flush.assert_awaited_once()

    async def test_suspend_provider_raises_for_missing(self, inventory, mock_db):
        """Test: suspend_provider raises ValueError for unknown provider."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="not found"):
            await inventory.suspend_provider(
                provider_id="nonexistent",
                reason="test",
                suspended_by="admin",
            )

    async def test_unsuspend_provider_sets_status_active(self, inventory, mock_db):
        """Test 4: unsuspend_provider sets status='active'."""
        mock_orm = _make_mock_provider_orm(provider_id="prov_001", status="suspended")
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.one_or_none.return_value = mock_orm
        mock_db.execute.return_value = mock_result
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await inventory.unsuspend_provider(
            provider_id="prov_001",
            unsuspended_by="admin",
        )
        assert result.status == "active"
        mock_db.flush.assert_awaited_once()

    async def test_flag_concentration_risk_sets_flag(self, inventory, mock_db):
        """Test 5: flag_concentration_risk sets concentration_risk=True."""
        now = datetime.now(timezone.utc)
        mock_orm = _make_mock_provider_orm(
            provider_id="prov_001",
            concentration_risk=False,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.one_or_none.return_value = mock_orm
        mock_db.execute.return_value = mock_result
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await inventory.flag_concentration_risk(
            provider_id="prov_001",
            justification="Provider handles >30% of traffic",
        )
        assert result.concentration_risk is True
        assert result.concentration_risk_justification == "Provider handles >30% of traffic"
        assert result.next_review_date is not None
        mock_db.flush.assert_awaited_once()

    async def test_list_providers_returns_empty_list(self, inventory, mock_db):
        """Test 6: list_providers returns empty list."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await inventory.list_providers(skip=0, limit=50)
        assert result == []

    async def test_list_providers_filters_by_status(self, inventory, mock_db):
        """Test 6: list_providers filters by status."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await inventory.list_providers(status="active")
        assert result == []

    async def test_list_providers_filters_by_concentration_risk(self, inventory, mock_db):
        """Test 6: list_providers filters by concentration_risk."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await inventory.list_providers(concentration_risk=True)
        assert result == []

    async def test_is_provider_active_true_for_active(self, inventory):
        """Test: is_provider_active returns True for active status."""
        record = ProviderRecord(name="OpenAI", provider_type="llm", status="active")
        inventory.get_provider_record = AsyncMock(return_value=record)

        result = await inventory.is_provider_active("prov_001")
        assert result is True

    async def test_is_provider_active_false_for_suspended(self, inventory):
        """Test: is_provider_active returns False for suspended status."""
        record = ProviderRecord(name="OpenAI", provider_type="llm", status="suspended")
        inventory.get_provider_record = AsyncMock(return_value=record)

        result = await inventory.is_provider_active("prov_001")
        assert result is False

    async def test_is_provider_active_false_for_unknown(self, inventory):
        """Test: Unknown provider returns False (fail-secure)."""
        inventory.get_provider_record = AsyncMock(return_value=None)

        result = await inventory.is_provider_active("unknown")
        assert result is False

    async def test_check_provider_active_raises_for_suspended(self, inventory):
        """Test: check_provider_active raises ValueError for suspended."""
        inventory.is_provider_active = AsyncMock(return_value=False)

        with pytest.raises(ValueError, match="not active"):
            await inventory.check_provider_active("prov_001")
