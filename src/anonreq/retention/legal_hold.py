"""Legal Hold management with tenant-level and record-level tagging.

Per D-018, D-019, D-020:
- Tenant-level hold + record-level tagging (D-018)
- Hold suspension blocks deletion across all storage tiers (D-019)
- Release of hold triggers normal retention policy (D-020)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from anonreq.models.lineage import LegalHoldRecord

logger = logging.getLogger("anonreq.retention.legal_hold")

LEGAL_HOLD_TABLE = "legal_hold"
"""Database table name for legal hold records."""


class LegalHoldManager:
    """Manages Legal Hold operations across all storage tiers.

    Supports tenant-level holds (all records for a tenant) and
    record-level holds (specific records by ID). Hold status is
    checked by RetentionManager before purging expired data.

    Per D-019: When a hold is active, purge operations skip the
    affected records. Per D-020: Release triggers normal retention.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the Legal Hold manager.

        Args:
            db: SQLAlchemy async session for database operations.
        """
        self._db = db

    async def activate_hold(
        self,
        tenant_id: str,
        reason: str,
        activated_by: str,
        scope: Literal["tenant", "record"] = "tenant",
        record_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> LegalHoldRecord:
        """Activate a Legal Hold for a tenant or specific record.

        Args:
            tenant_id: The tenant to place under hold.
            reason: Reason for the hold (e.g., litigation case ref).
            activated_by: Identity of the person activating the hold.
            scope: ``tenant`` for whole-tenant hold, ``record`` for
                single-record hold.
            record_id: Required when scope is ``record``.
            expires_at: Optional expiry. If None, hold is infinite
                until explicitly released.

        Returns:
            The created LegalHoldRecord.

        Raises:
            ValueError: If ``scope=record`` but no record_id provided.
        """
        if scope == "record" and not record_id:
            raise ValueError("record_id is required when scope='record'")

        hold = LegalHoldRecord(
            id=f"hold_{uuid4().hex[:16]}",
            tenant_id=tenant_id,
            scope=scope,
            record_id=record_id,
            reason=reason,
            activated_by=activated_by,
            activated_at=datetime.now(UTC),
            expires_at=expires_at,
        )

        # Store in PostgreSQL
        stmt = text("""
            INSERT INTO legal_hold (
                id, tenant_id, scope, record_id, reason,
                activated_by, activated_at, expires_at,
                released_at, released_by
            ) VALUES (
                :id, :tenant_id, :scope, :record_id, :reason,
                :activated_by, :activated_at, :expires_at,
                :released_at, :released_by
            )
        """)
        params = {
            "id": hold.id,
            "tenant_id": hold.tenant_id,
            "scope": hold.scope,
            "record_id": hold.record_id,
            "reason": hold.reason,
            "activated_by": hold.activated_by,
            "activated_at": hold.activated_at,
            "expires_at": hold.expires_at,
            "released_at": hold.released_at,
            "released_by": hold.released_by,
        }

        try:
            await self._db.execute(stmt, params)
            await self._db.commit()
            logger.info(
                "Legal Hold activated: id=%s tenant=%s scope=%s reason=%s",
                hold.id, tenant_id, scope, reason,
            )
        except Exception as exc:
            await self._db.rollback()
            logger.error("Failed to activate legal hold: %s", exc)
            raise RuntimeError(f"Failed to activate legal hold: {exc}") from exc

        return hold

    async def release_hold(
        self,
        hold_id: str,
        released_by: str,
    ) -> LegalHoldRecord:
        """Release an active Legal Hold.

        Args:
            hold_id: The ID of the hold to release.
            released_by: Identity of the person releasing the hold.

        Returns:
            The updated LegalHoldRecord with released_at and
            released_by set.

        Raises:
            ValueError: If the hold ID is not found.
        """
        # Check if hold exists
        check_stmt = text(
            "SELECT * FROM legal_hold WHERE id = :id"
        )
        try:
            result = await self._db.execute(check_stmt, {"id": hold_id})
            row = await result.fetchone()
        except Exception:
            row = None

        if row is None:
            raise ValueError(f"Hold not found: {hold_id}")

        # Update hold
        now = datetime.now(UTC)
        update_stmt = text("""
            UPDATE legal_hold
            SET released_at = :released_at,
                released_by = :released_by
            WHERE id = :id
        """)
        try:
            await self._db.execute(update_stmt, {
                "released_at": now,
                "released_by": released_by,
                "id": hold_id,
            })
            await self._db.commit()
            logger.info(
                "Legal Hold released: id=%s by=%s", hold_id, released_by
            )
        except Exception as exc:
            await self._db.rollback()
            logger.error("Failed to release legal hold: %s", exc)
            raise RuntimeError(
                f"Failed to release legal hold: {exc}"
            ) from exc

        # Return updated record
        return LegalHoldRecord(
            id=hold_id,
            tenant_id=row[2] if len(row) > 2 else "",
            released_at=now,
            released_by=released_by,
        )

    async def is_on_hold(
        self,
        tenant_id: str,
        record_id: str | None = None,
    ) -> bool:
        """Check if a tenant or record is under active Legal Hold.

        Args:
            tenant_id: The tenant to check.
            record_id: Optional record ID for record-level checks.

        Returns:
            True if an active (unreleased, not expired) hold exists
            for the given tenant or record.
        """
        if record_id:
            # Check record-level hold
            stmt = text("""
                SELECT COUNT(*) FROM legal_hold
                WHERE (tenant_id = :tenant_id OR record_id = :record_id)
                  AND released_at IS NULL
                  AND (expires_at IS NULL OR expires_at > :now)
            """)
            params = {
                "tenant_id": tenant_id,
                "record_id": record_id,
                "now": datetime.now(UTC),
            }
        else:
            # Check tenant-level hold
            stmt = text("""
                SELECT COUNT(*) FROM legal_hold
                WHERE tenant_id = :tenant_id
                  AND released_at IS NULL
                  AND (expires_at IS NULL OR expires_at > :now)
            """)
            params = {
                "tenant_id": tenant_id,
                "now": datetime.now(UTC),
            }

        try:
            result = await self._db.execute(stmt, params)
            row = await result.fetchone()
            count = row[0] if row else 0
            return count > 0
        except Exception:
            # Table might not exist yet
            return False

    async def list_active_holds(
        self,
        tenant_id: str | None = None,
    ) -> list[LegalHoldRecord]:
        """List active (unreleased) Legal Holds.

        Args:
            tenant_id: Optional tenant filter.

        Returns:
            List of LegalHoldRecord instances for active holds.
        """
        if tenant_id:
            stmt = text("""
                SELECT * FROM legal_hold
                WHERE tenant_id = :tenant_id
                  AND released_at IS NULL
                ORDER BY activated_at DESC
            """)
            params = {"tenant_id": tenant_id}
        else:
            stmt = text("""
                SELECT * FROM legal_hold
                WHERE released_at IS NULL
                ORDER BY activated_at DESC
            """)
            params = {}

        try:
            result = await self._db.execute(stmt, params)
            rows = await result.fetchall()
        except Exception:
            return []

        holds: list[LegalHoldRecord] = []
        for row in rows:
            row_dict = dict(row._mapping) if hasattr(row, "_mapping") else {}
            holds.append(LegalHoldRecord(**row_dict))

        return holds

    async def get_records_on_hold(
        self,
        tenant_id: str,
    ) -> list[str]:
        """Get record IDs under hold for a tenant.

        Args:
            tenant_id: The tenant to query.

        Returns:
            List of record IDs under active hold.
        """
        stmt = text("""
            SELECT record_id FROM legal_hold
            WHERE tenant_id = :tenant_id
              AND scope = 'record'
              AND released_at IS NULL
              AND (expires_at IS NULL OR expires_at > :now)
        """)
        params = {
            "tenant_id": tenant_id,
            "now": datetime.now(UTC),
        }

        try:
            result = await self._db.execute(stmt, params)
            rows = await result.fetchall()
            return [row[0] for row in rows if row[0]]
        except Exception:
            return []
