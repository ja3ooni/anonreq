"""Tests for retention tier management with configurable schedules.

Per D-017:
- PostgreSQL 90 days (operational queries)
- MinIO WORM 7 years (compliance archive)
- Valkey TTL (token mappings)
- Legal Hold infinite until release
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    # Mock execute to return a result with rowcount
    result_mock = AsyncMock()
    result_mock.rowcount = 5
    result_mock.fetchone = AsyncMock(return_value=[5])
    session.execute = AsyncMock(return_value=result_mock)
    return session


@pytest.fixture
def mock_legal_hold_manager():
    mgr = AsyncMock()
    mgr.is_on_hold = AsyncMock(return_value=False)
    return mgr


@pytest.fixture
async def retention_manager(mock_db_session, mock_legal_hold_manager):
    from anonreq.retention.tiers import RetentionManager

    return RetentionManager(
        db=mock_db_session,
        legal_hold_manager=mock_legal_hold_manager,
    )


# ── Test 1: Retention config loaded with correct defaults ────────────────────


class TestRetentionConfig:
    async def test_default_postgresql_retention(self):
        """PostgreSQL tier defaults to 90 days."""
        from anonreq.retention.tiers import RETENTION_TIERS

        assert RETENTION_TIERS["postgresql"]["duration_days"] == 90
        assert RETENTION_TIERS["postgresql"]["description"] == "Operational queries"

    async def test_default_minio_retention(self):
        """MinIO WORM tier defaults to 7 years (2555 days)."""
        from anonreq.retention.tiers import RETENTION_TIERS

        assert RETENTION_TIERS["minio_worm"]["duration_days"] == 2555
        assert "Compliance archive" in RETENTION_TIERS["minio_worm"]["description"]

    async def test_default_valkey_retention(self):
        """Valkey tier is TTL-based (ephemeral)."""
        from anonreq.retention.tiers import RETENTION_TIERS

        assert RETENTION_TIERS["valkey"]["duration_days"] is None

    async def test_default_legal_hold_retention(self):
        """Legal Hold tier is infinite until release."""
        from anonreq.retention.tiers import RETENTION_TIERS

        assert RETENTION_TIERS["legal_hold"]["duration_days"] is None

    async def test_get_retention_config(self, retention_manager):
        """get_retention_config returns current configuration."""
        config = await retention_manager.get_retention_config()
        assert isinstance(config, dict)
        assert "postgresql" in config
        assert "minio_worm" in config
        assert config["postgresql"]["duration_days"] == 90


# ── Test 2: purge_expired deletes records past retention period ──────────────


class TestPurgeExpired:
    async def test_purge_expired_postgresql(self, retention_manager):
        """purge_expired deletes PostgreSQL records past retention."""
        result = await retention_manager.purge_expired("postgresql")
        assert isinstance(result, dict)
        assert "deleted_count" in result
        assert "tier" in result
        assert result["tier"] == "postgresql"

    async def test_purge_expired_minio(self, retention_manager):
        """purge_expired processes MinIO tier."""
        result = await retention_manager.purge_expired("minio_worm")
        assert isinstance(result, dict)
        assert "deleted_count" in result
        assert result["tier"] == "minio_worm"

    async def test_purge_expired_valkey_noop(self, retention_manager):
        """purge_expired for Valkey is a no-op."""
        result = await retention_manager.purge_expired("valkey")
        assert result["tier"] == "valkey"
        assert result["deleted_count"] == 0

    async def test_purge_expired_returns_count(self, retention_manager):
        """purge_expired returns deleted count."""
        result = await retention_manager.purge_expired("postgresql")
        assert isinstance(result["deleted_count"], int)

    async def test_purge_expired_logs_count(self, retention_manager):
        """purge_expired returns loggable result."""
        result = await retention_manager.purge_expired("postgresql")
        assert "dry_run" in result

    async def test_run_scheduled_purge(self, retention_manager):
        """run_scheduled_purge processes all applicable tiers."""
        results = await retention_manager.run_scheduled_purge()
        assert isinstance(results, list)
        assert len(results) > 0


# ── Test 3: Records under Legal Hold excluded from purge ────────────────────


class TestLegalHoldExclusion:
    async def test_purge_expired_respects_legal_hold(
        self, retention_manager, mock_legal_hold_manager
    ):
        """Records under Legal Hold are excluded from purge."""
        mock_legal_hold_manager.is_on_hold.return_value = True
        result = await retention_manager.purge_expired("postgresql")
        assert "skipped_legal_hold" in result

    async def test_purge_skips_legal_hold_count(
        self, retention_manager, mock_legal_hold_manager
    ):
        """purge_expired reports records skipped due to Legal Hold."""
        mock_legal_hold_manager.is_on_hold.return_value = True
        result = await retention_manager.purge_expired("postgresql")
        assert isinstance(result["skipped_legal_hold"], int)

    async def test_purge_without_legal_hold(
        self, retention_manager, mock_legal_hold_manager
    ):
        """Without Legal Hold, skip count is zero."""
        mock_legal_hold_manager.is_on_hold.return_value = False
        result = await retention_manager.purge_expired("postgresql")
        assert result["skipped_legal_hold"] == 0


# ── Test 4: Retention schedule configurable per tier ────────────────────────


class TestUpdateRetention:
    async def test_update_retention_config(self, retention_manager):
        """update_retention_config updates tier duration."""
        result = await retention_manager.update_retention_config(
            "postgresql", 180
        )
        assert result["tier"] == "postgresql"
        assert result["duration_days"] == 180

    async def test_update_retention_config_returns_config(
        self, retention_manager
    ):
        """update_retention_config returns the updated tier config."""
        result = await retention_manager.update_retention_config(
            "minio_worm", 3650
        )
        assert result["duration_days"] == 3650

    async def test_update_nonexistent_tier_raises(self, retention_manager):
        """Updating a non-existent tier raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="Unknown tier"):
            await retention_manager.update_retention_config("invalid_tier", 30)


# ── Test 5: Dry run mode ─────────────────────────────────────────────────────


class TestDryRun:
    async def test_dry_run_no_deletion(self, retention_manager):
        """dry_run mode does not delete records."""
        result = await retention_manager.purge_expired(
            "postgresql", dry_run=True
        )
        assert result["dry_run"] is True

    async def test_dry_run_reports_estimates(self, retention_manager):
        """dry_run mode reports estimated deletion count."""
        result = await retention_manager.purge_expired(
            "postgresql", dry_run=True
        )
        assert isinstance(result["deleted_count"], int)
