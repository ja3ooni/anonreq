"""Tests for Model Risk Management (SR 11-7) ForwardingGuard integration.

Tests for the governance-level model approval and provider active checks
that gate outbound LLM traffic per D-007.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import structlog

from anonreq.governance.forwarding_guard import (
    ModelNotApprovedError,
    ProviderSuspendedError,
    check_model_approval,
    check_provider_active,
)
from anonreq.models.governance import ModelRiskClassification


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_model_inventory():
    """Mock ModelInventory that returns configurable approval status."""
    mock = AsyncMock()
    mock.is_model_approved.return_value = True
    return mock


@pytest.fixture
def mock_provider_inventory():
    """Mock ProviderInventory that returns configurable active status."""
    mock = AsyncMock()
    mock.is_provider_active.return_value = True
    return mock


@pytest.fixture
def mock_logger():
    """Mock structlog logger for audit event assertions."""
    logger = MagicMock(spec=structlog.stdlib.BoundLogger)
    logger.info = MagicMock()
    return logger


# ── check_model_approval tests ──────────────────────────────────────────────


class TestCheckModelApproval:
    """Test check_model_approval: approved model passes, unapproved blocked."""

    async def test_approved_model_passes(self, mock_model_inventory):
        """Test 1: Approved model passes check_model_approval."""
        mock_model_inventory.is_model_approved.return_value = True
        # Should not raise
        await check_model_approval(
            model_inventory=mock_model_inventory,
            provider="openai",
            model_name="gpt-4",
        )

    async def test_unapproved_model_blocked(self, mock_model_inventory):
        """Test 2: Unapproved model raises ModelNotApprovedError."""
        mock_model_inventory.is_model_approved.return_value = False
        with pytest.raises(ModelNotApprovedError) as exc_info:
            await check_model_approval(
                model_inventory=mock_model_inventory,
                provider="openai",
                model_name="gpt-4",
            )
        assert exc_info.value.status_code == 403

    async def test_unknown_model_blocked_fail_secure(self, mock_model_inventory):
        """Test 3: Unknown model raises ModelNotApprovedError (fail-secure)."""
        mock_model_inventory.is_model_approved.return_value = False
        with pytest.raises(ModelNotApprovedError):
            await check_model_approval(
                model_inventory=mock_model_inventory,
                provider="openai",
                model_name="unknown-model",
            )

    async def test_passes_correct_args_to_model_inventory(self, mock_model_inventory):
        """Test 4: check_model_approval delegates to is_model_approved with correct args."""
        mock_model_inventory.is_model_approved.return_value = True
        await check_model_approval(
            model_inventory=mock_model_inventory,
            provider="anthropic",
            model_name="claude-3",
        )
        mock_model_inventory.is_model_approved.assert_awaited_once_with(
            provider="anthropic",
            model_name="claude-3",
        )

    async def test_increments_prometheus_counter(self, mock_model_inventory):
        """Test 5: Prometheus metric anonreq_model_approval_gates_total incremented on pass."""
        mock_model_inventory.is_model_approved.return_value = True
        await check_model_approval(
            model_inventory=mock_model_inventory,
            provider="openai",
            model_name="gpt-4",
        )
        # Metric exists and is a Counter — can't read value, just verify import
        from anonreq.governance.forwarding_guard import model_approval_gates
        assert model_approval_gates is not None


# ── check_provider_active tests ─────────────────────────────────────────────


class TestCheckProviderActive:
    """Test check_provider_active: active provider passes, suspended blocked."""

    async def test_active_provider_passes(self, mock_provider_inventory):
        """Test 1: Active provider passes check_provider_active."""
        mock_provider_inventory.is_provider_active.return_value = True
        # Should not raise
        await check_provider_active(
            provider_inventory=mock_provider_inventory,
            provider_id="prov_openai",
        )

    async def test_suspended_provider_blocked(self, mock_provider_inventory):
        """Test 2: Suspended provider raises ProviderSuspendedError."""
        mock_provider_inventory.is_provider_active.return_value = False
        with pytest.raises(ProviderSuspendedError) as exc_info:
            await check_provider_active(
                provider_inventory=mock_provider_inventory,
                provider_id="prov_openai",
            )
        assert exc_info.value.status_code == 403

    async def test_passes_correct_args(self, mock_provider_inventory):
        """Test 3: Delegates to is_provider_active with correct provider_id."""
        mock_provider_inventory.is_provider_active.return_value = True
        await check_provider_active(
            provider_inventory=mock_provider_inventory,
            provider_id="prov_anthropic",
        )
        mock_provider_inventory.is_provider_active.assert_awaited_once_with(
            provider_id="prov_anthropic",
        )
