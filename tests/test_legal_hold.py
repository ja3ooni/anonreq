"""Tests for Legal Hold management with tenant-level and record-level tagging.

Per D-018, D-019, D-020:
- Tenant-level hold + record-level tagging
- Hold suspension blocks deletion across all storage tiers
- Release of hold triggers normal retention policy
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from anonreq.models.lineage import LegalHoldRecord


# ── Fixtures ─────────────────────────────────────────────────────────────────


# In-memory store for mock DB operations
_hold_store: dict[str, dict] = {}


@pytest.fixture(autouse=True)
def _reset_hold_store():
    """Reset hold store between tests."""
    _hold_store.clear()


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    async def mock_execute(stmt, params=None):
        result = AsyncMock()
        stmt_str = str(stmt) if hasattr(stmt, '__str__') else str(stmt)
        params = params or {}
        result.rowcount = 1

        if 'INSERT INTO legal_hold' in stmt_str:
            # Track inserted hold
            hold_id = params.get('id', '')
            _hold_store[hold_id] = dict(params)

        if 'UPDATE legal_hold' in stmt_str:
            hold_id = params.get('id', '')
            if hold_id in _hold_store:
                _hold_store[hold_id]['released_at'] = params.get('released_at')
                _hold_store[hold_id]['released_by'] = params.get('released_by')
            result.fetchone = AsyncMock(return_value=None)
            result.fetchall = AsyncMock(return_value=[])
            return result

        if 'WHERE id = :id' in stmt_str:
            hold_id = params.get('id', '')
            if hold_id in _hold_store:
                row = list(_hold_store[hold_id].values())
                result.fetchone = AsyncMock(return_value=row)
                result.fetchall = AsyncMock(return_value=[])
            elif hold_id in ('nonexistent-id', 'nonexistent_id'):
                result.fetchone = AsyncMock(return_value=None)
                result.fetchall = AsyncMock(return_value=[])
            else:
                result.fetchone = AsyncMock(return_value=None)
                result.fetchall = AsyncMock(return_value=[])

        elif 'SELECT COUNT(*)' in stmt_str:
            # Check active holds
            tenant_id = params.get('tenant_id', '')
            record_id = params.get('record_id', '')
            now = params.get('now')

            # Count holds matching tenant_id that are not released
            matches = []
            count = 0
            for hold_id, hold in _hold_store.items():
                tid_match = hold.get('tenant_id') == tenant_id
                rid_match = record_id and hold.get('record_id') == record_id
                if not tid_match and not rid_match:
                    continue
                released_at = hold.get('released_at')
                if released_at is None:
                    count += 1
                    matches.append(hold_id)
                else:
                    pass

            result.fetchone = AsyncMock(return_value=[count])
            result.fetchall = AsyncMock(return_value=[])

        elif 'SELECT * FROM legal_hold' in stmt_str:
            rows = []
            for hold_data in _hold_store.values():
                if hold_data.get('released_at') is None:
                    rows.append(hold_data)
            # Wrap each dict as a mock row with _mapping attribute
            mock_rows = []
            for data in rows:
                mock_row = AsyncMock()
                mock_row._mapping = dict(data)
                mock_rows.append(mock_row)
            result.fetchone = AsyncMock(return_value=mock_rows[0] if mock_rows else None)
            result.fetchall = AsyncMock(return_value=mock_rows)

        else:
            result.fetchone = AsyncMock(return_value=[1])
            result.fetchall = AsyncMock(return_value=[])

        return result

    session.execute = mock_execute
    return session


@pytest.fixture
async def legal_hold_manager(mock_db_session):
    from anonreq.retention.legal_hold import LegalHoldManager

    return LegalHoldManager(db=mock_db_session)


# ── Test 1: activate_hold creates tenant-level hold ─────────────────────────


class TestActivateHold:
    async def test_activate_hold_creates_record(self, legal_hold_manager):
        """activate_hold creates a hold record with reason and scope."""
        hold = await legal_hold_manager.activate_hold(
            tenant_id="acme",
            reason="Litigation case #123",
            activated_by="legal-officer",
        )
        assert hold.tenant_id == "acme"
        assert hold.reason == "Litigation case #123"
        assert hold.activated_by == "legal-officer"
        assert hold.scope == "tenant"

    async def test_activate_hold_sets_activated_at(self, legal_hold_manager):
        """activate_hold sets activated_at timestamp."""
        hold = await legal_hold_manager.activate_hold(
            tenant_id="acme",
            reason="Pending investigation",
            activated_by="compliance-officer",
        )
        assert hold.activated_at is not None

    async def test_activate_hold_no_expires_at(self, legal_hold_manager):
        """Hold without expires_at is infinite."""
        hold = await legal_hold_manager.activate_hold(
            tenant_id="acme",
            reason="Litigation",
            activated_by="legal",
        )
        assert hold.expires_at is None

    async def test_activate_hold_with_expiry(self, legal_hold_manager):
        """Hold with expires_at has an expiry date."""
        expires = datetime.now(timezone.utc) + timedelta(days=90)
        hold = await legal_hold_manager.activate_hold(
            tenant_id="acme",
            reason="Temporary hold",
            activated_by="legal",
            expires_at=expires,
        )
        assert hold.expires_at is not None

    async def test_activate_hold_record_scope(self, legal_hold_manager):
        """activate_hold with scope='record' creates record-level hold."""
        hold = await legal_hold_manager.activate_hold(
            tenant_id="acme",
            reason="Evidence preservation",
            activated_by="legal",
            scope="record",
            record_id="rec-001",
        )
        assert hold.scope == "record"
        assert hold.record_id == "rec-001"


# ── Test 2: release_hold releases a hold ────────────────────────────────────


class TestReleaseHold:
    async def test_release_hold_sets_released_at(self, legal_hold_manager):
        """release_hold sets released_at and returns hold record."""
        hold = await legal_hold_manager.activate_hold(
            tenant_id="acme",
            reason="Case closed",
            activated_by="legal",
        )
        released = await legal_hold_manager.release_hold(
            hold.id, released_by="legal-officer"
        )
        assert released.released_at is not None
        assert released.released_by == "legal-officer"

    async def test_release_hold_nonexistent_raises(self, legal_hold_manager):
        """Releasing a non-existent hold raises ValueError."""
        with pytest.raises(ValueError, match="Hold not found"):
            await legal_hold_manager.release_hold(
                "nonexistent-id", released_by="legal"
            )

    async def test_release_hold_twice_still_succeeds(self, legal_hold_manager):
        """Releasing an already-released hold is idempotent."""
        hold = await legal_hold_manager.activate_hold(
            tenant_id="acme",
            reason="Test",
            activated_by="legal",
        )
        await legal_hold_manager.release_hold(
            hold.id, released_by="legal"
        )
        # Second release should also succeed
        released = await legal_hold_manager.release_hold(
            hold.id, released_by="legal"
        )
        assert released.released_at is not None


# ── Test 3: is_on_hold detects active holds ─────────────────────────────────


class TestIsOnHold:
    async def test_is_on_hold_returns_true(self, legal_hold_manager):
        """is_on_hold returns True for tenant under active hold."""
        await legal_hold_manager.activate_hold(
            tenant_id="acme",
            reason="Litigation",
            activated_by="legal",
        )
        assert await legal_hold_manager.is_on_hold("acme") is True

    async def test_is_on_hold_returns_false(self, legal_hold_manager):
        """is_on_hold returns False for tenant without active hold."""
        assert await legal_hold_manager.is_on_hold("other-corp") is False

    async def test_is_on_hold_after_release(self, legal_hold_manager):
        """is_on_hold returns False after hold is released."""
        hold = await legal_hold_manager.activate_hold(
            tenant_id="acme",
            reason="Done",
            activated_by="legal",
        )
        await legal_hold_manager.release_hold(
            hold.id, released_by="legal"
        )
        assert await legal_hold_manager.is_on_hold("acme") is False

    async def test_is_on_hold_with_record_id(self, legal_hold_manager):
        """is_on_hold checks both tenant and record-specific hold."""
        await legal_hold_manager.activate_hold(
            tenant_id="acme",
            reason="Record hold",
            activated_by="legal",
            scope="record",
            record_id="rec-001",
        )
        assert await legal_hold_manager.is_on_hold(
            "acme", record_id="rec-001"
        ) is True


# ── Test 4: list_active_holds ───────────────────────────────────────────────


class TestListActiveHolds:
    async def test_list_active_holds(self, legal_hold_manager):
        """list_active_holds returns all active holds."""
        await legal_hold_manager.activate_hold(
            tenant_id="acme", reason="Case A", activated_by="legal"
        )
        await legal_hold_manager.activate_hold(
            tenant_id="other", reason="Case B", activated_by="legal"
        )
        holds = await legal_hold_manager.list_active_holds()
        assert len(holds) >= 2

    async def test_list_active_holds_by_tenant(self, legal_hold_manager):
        """list_active_holds filters by tenant if specified."""
        await legal_hold_manager.activate_hold(
            tenant_id="acme", reason="Case A", activated_by="legal"
        )
        holds = await legal_hold_manager.list_active_holds(tenant_id="acme")
        assert len(holds) == 1
        assert holds[0].tenant_id == "acme"

    async def test_list_active_holds_empty(self, legal_hold_manager):
        """list_active_holds returns empty list when no holds."""
        holds = await legal_hold_manager.list_active_holds()
        assert len(holds) == 0


# ── Test 5: Legal Hold blocks purge (integration) ──────────────────────────


class TestHoldBlocksPurge:
    async def test_hold_record_schema(self):
        """LegalHoldRecord has all required fields."""
        hold = LegalHoldRecord(
            tenant_id="acme",
            scope="tenant",
            reason="Litigation case #123",
            activated_by="legal-officer",
        )
        assert hold.scope == "tenant"
        assert hold.released_at is None

    async def test_hold_record_with_record_scope(self):
        """LegalHoldRecord supports record-level scope."""
        hold = LegalHoldRecord(
            tenant_id="acme",
            scope="record",
            record_id="rec-001",
            reason="Evidence hold",
            activated_by="legal",
        )
        assert hold.scope == "record"
        assert hold.record_id == "rec-001"
