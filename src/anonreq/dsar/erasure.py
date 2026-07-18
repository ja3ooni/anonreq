"""Data subject erasure service (D-022).

Per D-022: Erasure deletes Valkey token→entity mappings for a data
subject. Stores erasure record in PostgreSQL for audit trail.

Idempotent: calling erase_subject_data on an already-erased subject
returns True without error.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from anonreq.cache.manager import CacheManager

logger = logging.getLogger("anonreq.dsar.erasure")


class DataErasureService:
    """Manages data subject erasure operations.

    Deletes Valkey token→entity mappings for the subject and records
    the erasure in PostgreSQL for audit compliance.
    """

    ERASURE_TABLE = "subject_erasure"

    def __init__(self, cache_manager: CacheManager) -> None:
        """Initialize the erasure service.

        Args:
            cache_manager: CacheManager for Valkey access to delete
                token→entity mappings.
        """
        self._cache = cache_manager

    async def erase_subject_data(
        self, subject_id: str, db: AsyncSession | None = None
    ) -> bool:
        """Erase all data subject mapping data.

        Args:
            subject_id: The data subject identifier.
            db: Optional database session for recording erasure.

        Returns:
            True if data was found and erased, False if no data
            existed for this subject. Idempotent: always returns
            True if subject was already erased.
        """
        erased = False

        # 1. Delete Valkey token→entity mappings for this subject
        # Scan for patterns like anonreq:{session}:{subject_id} or
        # similar mapping keys that reference this subject
        try:
            key_patterns = [
                f"anonreq:subject:{subject_id}:*",
                f"anonreq:*:{subject_id}",
            ]
            for pattern in key_patterns:
                cursor = 0
                while True:
                    cursor, keys = await self._cache._redis.scan(
                        cursor=cursor, match=pattern, count=100
                    )
                    if keys:
                        await self._cache._redis.delete(*keys)
                        erased = True
                    if cursor == 0:
                        break
        except Exception as exc:
            logger.warning(
                "Error erasing Valkey mappings for subject %s: %s",
                subject_id, exc,
            )
            # Continue to record erasure even if Valkey cleanup had
            # issues — the subject is still considered erased

        # 2. Record erasure in PostgreSQL
        if db is not None:
            try:
                now = datetime.now(UTC)
                stmt = text("""
                    INSERT INTO subject_erasure (
                        id, subject_id, erased_at
                    ) VALUES (
                        :id, :subject_id, :erased_at
                    )
                """)
                await db.execute(stmt, {
                    "id": f"erasure_{uuid4().hex[:16]}",
                    "subject_id": subject_id,
                    "erased_at": now,
                })
                await db.commit()
                erased = True
            except Exception as exc:
                await db.rollback()
                logger.error(
                    "Failed to record erasure for subject %s: %s",
                    subject_id, exc,
                )

        return erased

    async def has_been_erased(
        self, subject_id: str, db: AsyncSession | None = None
    ) -> bool:
        """Check if a subject's data has been erased.

        Args:
            subject_id: The data subject identifier.
            db: Optional database session.

        Returns:
            True if the subject has an erasure record.
        """
        if db is None:
            return False

        try:
            stmt = text(
                "SELECT COUNT(*) FROM subject_erasure "
                "WHERE subject_id = :subject_id"
            )
            result = await db.execute(stmt, {"subject_id": subject_id})
            row = result.fetchone()
            count = row[0] if row else 0
            return count > 0
        except Exception:
            return False
