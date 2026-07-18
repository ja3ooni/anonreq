"""Data subject processing restriction service (D-023).

Per D-023: Restriction blocks all future requests from a data
subject at pipeline entry. Stores restriction in PostgreSQL and
caches in Valkey for fast-path pipeline checks.

Idempotent: restrict_subject returns False if already restricted.
remove_restriction allows future requests again.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from anonreq.cache.manager import CacheManager

logger = logging.getLogger("anonreq.dsar.restriction")

RESTRICTION_CACHE_PREFIX = "anonreq:restricted"
"""Valkey key prefix for fast-path restriction checks."""


class DataRestrictionService:
    """Manages data subject processing restrictions.

    Per D-023: Restricted subjects cannot be processed — the pipeline
    checks restriction status before any classification or anonymization.
    """

    RESTRICTION_TABLE = "subject_restriction"

    def __init__(
        self,
        db: AsyncSession,
        cache_manager: CacheManager,
    ) -> None:
        """Initialize the restriction service.

        Args:
            db: SQLAlchemy async session for restriction records.
            cache_manager: CacheManager for Valkey fast-path.
        """
        self._db = db
        self._cache = cache_manager

    async def restrict_subject(
        self,
        tenant_id: str,
        subject_id: str,
        restricted_by: str = "dsar_workflow",
    ) -> bool:
        """Restrict processing for a data subject.

        Args:
            tenant_id: The tenant the subject belongs to.
            subject_id: The data subject identifier.
            restricted_by: Identity of the entity imposing the
                restriction (default: ``dsar_workflow``).

        Returns:
            True if newly restricted, False if already restricted.
        """
        # Check if already restricted
        if await self.is_subject_restricted(subject_id):
            return False

        now = datetime.now(UTC)

        # Store in PostgreSQL
        try:
            stmt = text("""
                INSERT INTO subject_restriction (
                    id, tenant_id, subject_id, restricted_at,
                    restricted_by
                ) VALUES (
                    :id, :tenant_id, :subject_id, :restricted_at,
                    :restricted_by
                )
            """)
            await self._db.execute(stmt, {
                "id": f"restriction_{uuid4().hex[:16]}",
                "tenant_id": tenant_id,
                "subject_id": subject_id,
                "restricted_at": now,
                "restricted_by": restricted_by,
            })
            await self._db.commit()
        except Exception as exc:
            await self._db.rollback()
            logger.error(
                "Failed to create restriction for %s: %s",
                subject_id, exc,
            )
            raise RuntimeError(
                f"Failed to restrict subject: {exc}"
            ) from exc

        # Cache in Valkey for fast-path pipeline check
        try:
            cache_key = f"{RESTRICTION_CACHE_PREFIX}:{subject_id}"
            await self._cache._redis.setex(cache_key, 86400, "1")
        except Exception as exc:
            logger.warning(
                "Failed to cache restriction for %s: %s",
                subject_id, exc,
            )

        logger.info(
            "Subject restricted: id=%s tenant=%s", subject_id, tenant_id
        )
        return True

    async def is_subject_restricted(
        self, subject_id: str
    ) -> bool:
        """Check if a subject has processing restricted.

        Checks Valkey cache first (fast path), falls back to
        PostgreSQL.

        Args:
            subject_id: The data subject identifier.

        Returns:
            True if the subject is restricted.
        """
        # Fast path: Valkey cache
        try:
            cache_key = f"{RESTRICTION_CACHE_PREFIX}:{subject_id}"
            cached = await self._cache._redis.get(cache_key)
            if cached is not None:
                return True
        except Exception:
            pass

        # Fallback: PostgreSQL
        try:
            stmt = text(
                "SELECT COUNT(*) FROM subject_restriction "
                "WHERE subject_id = :subject_id"
            )
            result = await self._db.execute(
                stmt, {"subject_id": subject_id}
            )
            row = result.fetchone()
            count = row[0] if row else 0
            return count > 0
        except Exception:
            return False

    async def remove_restriction(
        self, subject_id: str
    ) -> bool:
        """Remove a processing restriction.

        Deletes restriction from PostgreSQL and Valkey cache.

        Args:
            subject_id: The data subject identifier.

        Returns:
            True if a restriction was active and removed, False if
            no restriction existed.
        """
        removed = False

        # Delete from PostgreSQL
        try:
            stmt = text(
                "DELETE FROM subject_restriction "
                "WHERE subject_id = :subject_id"
            )
            result = await self._db.execute(
                stmt, {"subject_id": subject_id}
            )
            await self._db.commit()
            if hasattr(result, 'rowcount') and result.rowcount and result.rowcount > 0:
                removed = True
        except Exception:
            await self._db.rollback()

        # Delete from Valkey cache
        try:
            cache_key = f"{RESTRICTION_CACHE_PREFIX}:{subject_id}"
            await self._cache._redis.delete(cache_key)
        except Exception:
            pass

        if removed:
            logger.info(
                "Restriction removed: subject=%s", subject_id
            )

        return removed

    async def list_restricted_subjects(
        self,
    ) -> list[dict[str, object]]:
        """List all restricted subjects.

        Returns:
            List of dicts with subject_id, tenant_id, restricted_at.
        """
        try:
            stmt = text("""
                SELECT subject_id, tenant_id, restricted_at
                FROM subject_restriction
                ORDER BY restricted_at DESC
            """)
            result = await self._db.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "subject_id": row[0],
                    "tenant_id": row[1],
                    "restricted_at": row[2],
                }
                for row in rows
                if row[0]
            ]
        except Exception:
            return []
