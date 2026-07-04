"""Tests for model inventory with Phase 14 lifecycle integration.

Tests SR 11-7 compliant model inventory: risk classification, approval
status, lifecycle integration, and fail-secure defaults (unknown models
default to not-approved).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from anonreq.models.governance import ModelRecord, ModelRiskClassification


class TestModelRiskClassification:
    """Test SR 11-7 risk classification enum values."""

    def test_low_value(self):
        assert ModelRiskClassification.LOW.value == "LOW"

    def test_moderate_value(self):
        assert ModelRiskClassification.MODERATE.value == "MODERATE"

    def test_high_value(self):
        assert ModelRiskClassification.HIGH.value == "HIGH"

    def test_all_values_present(self):
        values = {m.value for m in ModelRiskClassification}
        assert values == {"LOW", "MODERATE", "HIGH"}


class TestModelRecordValidation:
    """Test ModelRecord pydantic model validation and defaults."""

    def test_create_minimal_model_record(self):
        """Test 1: create_model_record stores model with risk classification."""
        record = ModelRecord(
            provider="openai",
            model_name="gpt-4",
            risk_classification=ModelRiskClassification.HIGH,
        )
        assert record.provider == "openai"
        assert record.model_name == "gpt-4"
        assert record.risk_classification == ModelRiskClassification.HIGH
        assert record.approval_status == "pending"
        assert record.current_stage == "DRAFT"
        assert record.review_cycle_days == 365

    def test_model_record_with_all_fields(self):
        now = datetime.now(timezone.utc)
        record = ModelRecord(
            id="model_001",
            provider="anthropic",
            model_name="claude-3-opus",
            risk_classification=ModelRiskClassification.MODERATE,
            approval_status="approved",
            current_stage="PRODUCTION",
            lifecycle_object_id="life_001",
            version="1.0.0",
            documentation_url="https://docs.example.com/model",
            validation_status="validated",
            validation_date=now,
            review_cycle_days=180,
            last_review_date=now,
            next_review_date=now,
            created_at=now,
            updated_at=now,
        )
        assert record.id == "model_001"
        assert record.provider == "anthropic"
        assert record.documentation_url == "https://docs.example.com/model"
        assert record.validation_status == "validated"
        assert record.review_cycle_days == 180

    def test_model_record_default_approval_status(self):
        """Default approval_status should be 'pending'."""
        record = ModelRecord(
            provider="openai",
            model_name="gpt-3.5",
            risk_classification=ModelRiskClassification.LOW,
        )
        assert record.approval_status == "pending"

    def test_model_record_default_current_stage(self):
        """Default current_stage should be 'DRAFT'."""
        record = ModelRecord(
            provider="openai",
            model_name="gpt-4",
            risk_classification=ModelRiskClassification.HIGH,
        )
        assert record.current_stage == "DRAFT"

    def test_model_record_default_review_cycle(self):
        """Default review cycle should be 365 days per SR 11-7."""
        record = ModelRecord(
            provider="openai",
            model_name="gpt-4",
            risk_classification=ModelRiskClassification.HIGH,
        )
        assert record.review_cycle_days == 365

    def test_model_record_risk_classification_enum_validation(self):
        """Test that risk_classification validates correctly."""
        with pytest.raises(ValidationError):
            ModelRecord(
                provider="openai",
                model_name="gpt-4",
                risk_classification="INVALID",  # type: ignore
            )


def _make_mock_orm(**overrides):
    """Create a MagicMock with ModelAnonReqModel-like attributes."""
    now = datetime.now(timezone.utc)
    attrs = {
        "model_id": "model_001",
        "provider": "openai",
        "model_name": "gpt-4",
        "risk_classification": "MODERATE",
        "approval_status": "approved",
        "current_stage": "APPROVED",
        "lifecycle_object_id": "life_001",
        "version": "1.0.0",
        "documentation_url": None,
        "validation_status": None,
        "validation_date": None,
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


class TestModelInventory:
    """Test ModelInventory class with mock DB and lifecycle manager."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_lifecycle(self):
        return AsyncMock()

    @pytest.fixture
    def inventory(self, mock_db, mock_lifecycle):
        from anonreq.governance.model_inventory import ModelInventory

        return ModelInventory(db=mock_db, lifecycle_manager=mock_lifecycle)

    async def test_create_model_record(self, inventory, mock_lifecycle):
        """Test 1: create_model_record stores model with risk classification."""
        mock_stage = MagicMock()
        mock_stage.value = "DESIGN"
        mock_lifecycle.get_current_stage.return_value = mock_stage

        result = await inventory.create_model_record(
            provider="openai",
            model_name="gpt-4",
            risk_classification=ModelRiskClassification.HIGH,
        )

        assert result.provider == "openai"
        assert result.model_name == "gpt-4"
        assert result.risk_classification == ModelRiskClassification.HIGH
        assert result.approval_status == "pending"

    async def test_get_model_record_by_id_returns_none_for_missing(self, inventory, mock_db):
        """Test 2: get_model_record retrieves model by id."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await inventory.get_model_record("nonexistent")
        assert result is None

    async def test_get_model_record_by_name_returns_none_for_missing(self, inventory, mock_db):
        """Test 2: get_model_record retrieves by provider+model_name."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await inventory.get_model_record_by_name("openai", "gpt-4")
        assert result is None

    async def test_is_model_approved_true_for_approved_stage(self, inventory):
        """Test 3: is_model_approved returns True for APPROVED stage."""
        record = ModelRecord(
            provider="openai",
            model_name="gpt-4",
            risk_classification=ModelRiskClassification.MODERATE,
            current_stage="APPROVED",
        )
        inventory.get_model_record_by_name = AsyncMock(return_value=record)

        result = await inventory.is_model_approved("openai", "gpt-4")
        assert result is True

    async def test_is_model_approved_true_for_production_stage(self, inventory):
        """Test 3: is_model_approved returns True for PRODUCTION stage."""
        record = ModelRecord(
            provider="openai",
            model_name="gpt-4",
            risk_classification=ModelRiskClassification.MODERATE,
            current_stage="PRODUCTION",
        )
        inventory.get_model_record_by_name = AsyncMock(return_value=record)

        result = await inventory.is_model_approved("openai", "gpt-4")
        assert result is True

    async def test_is_model_approved_false_for_draft_stage(self, inventory):
        """Test 3: is_model_approved returns False for DRAFT stage."""
        record = ModelRecord(
            provider="openai",
            model_name="gpt-4",
            risk_classification=ModelRiskClassification.MODERATE,
            current_stage="DRAFT",
        )
        inventory.get_model_record_by_name = AsyncMock(return_value=record)

        result = await inventory.is_model_approved("openai", "gpt-4")
        assert result is False

    async def test_is_model_approved_false_for_unknown_model(self, inventory):
        """Test: Unknown model returns False (fail-secure)."""
        inventory.get_model_record_by_name = AsyncMock(return_value=None)

        result = await inventory.is_model_approved("unknown", "model")
        assert result is False

    async def test_list_models_returns_empty_list(self, inventory, mock_db):
        """Test 6: list_models paginates."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await inventory.list_models(skip=0, limit=50)
        assert result == []

    async def test_update_model_review(self, inventory, mock_db):
        """Test: update_model_review updates review fields."""
        now = datetime.now(timezone.utc)
        mock_orm = _make_mock_orm()
        mock_orm.model_id = "model_001"

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.one_or_none.return_value = mock_orm
        mock_db.execute.return_value = mock_result
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await inventory.update_model_review(
            model_id="model_001",
            validation_status="validated",
            validation_date=now,
        )
        mock_db.flush.assert_awaited_once()
        assert result is not None
        assert result.validation_status == "validated"

    async def test_sr_11_7_alignment(self, inventory):
        """Test SR 11-7 alignment documentation."""
        alignment = inventory.get_sr_11_7_alignment()
        assert isinstance(alignment, dict)
        assert "model_risk_classification" in alignment
        assert "approval_gating" in alignment

    async def test_update_model_review_sets_next_review_date(self, inventory, mock_db):
        """Test: update_model_review sets next_review_date based on interval."""
        now = datetime.now(timezone.utc)
        mock_orm = _make_mock_orm(
            risk_classification="HIGH",
            last_review_date=now,
            next_review_date=None,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.one_or_none.return_value = mock_orm
        mock_db.execute.return_value = mock_result
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await inventory.update_model_review(
            model_id="model_001",
            validation_status="validated",
            validation_date=now,
        )
        mock_db.flush.assert_awaited_once()
        assert result.next_review_date is not None
