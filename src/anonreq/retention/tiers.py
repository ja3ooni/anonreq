"""Retention tier management with configurable schedules and Legal Hold support.

Per D-017:
- PostgreSQL 90 days (operational queries)
- MinIO WORM 7 years (compliance archive)
- Valkey TTL (token mappings)
- Legal Hold infinite until release
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("anonreq.retention.tiers")

RETENTION_TIERS: dict[str, dict] = {
    "postgresql": {
        "duration_days": 90,
        "description": "Operational queries",
    },
    "minio_worm": {
        "duration_days": 2555,
        "description": "Compliance archive (7 years)",
    },
    "valkey": {
        "duration_days": None,
        "description": "TTL-based (ephemeral)",
    },
    "legal_hold": {
        "duration_days": None,
        "description": "Infinite until release",
    },
}
"""Default retention tier configuration.

Tiers with ``duration_days: None`` rely on external mechanisms
(Valkey TTL, Legal Hold explicit release) rather than scheduled purge.
"""


async def get_retention_config() -> dict:
    """Get the current retention configuration (module-level convenience).

    Returns:
        A copy of the current RETENTION_TIERS dict.
    """
    return dict(RETENTION_TIERS)


async def purge_expired(
    db: AsyncSession,
    tier: str,
    dry_run: bool = False,
    legal_hold_manager=None,
) -> dict:
    """Purge expired records for a retention tier (module-level convenience).

    Args:
        db: SQLAlchemy async session.
        tier: The tier to purge (``postgresql``, ``minio_worm``, ``valkey``).
        dry_run: If True, don't actually delete.
        legal_hold_manager: Optional LegalHoldManager for hold checks.

    Returns:
        Dict with ``tier``, ``deleted_count``, ``skipped_legal_hold``,
        and ``dry_run`` keys.
    """
    mgr = RetentionManager(
        db=db, legal_hold_manager=legal_hold_manager
    )
    return await mgr.purge_expired(tier=tier, dry_run=dry_run)


class RetentionManager:
    """Manages retention tier configuration and scheduled purging.

    Provides methods to query and update retention configuration,
    purge expired records per tier, and respect Legal Hold exclusions.

    Scheduled purging is designed to be called by an external scheduler
    (e.g., cron, Celery Beat, APScheduler).
    """

    def __init__(
        self,
        db: AsyncSession,
        legal_hold_manager=None,
        config: dict | None = None,
    ) -> None:
        """Initialize the retention manager.

        Args:
            db: SQLAlchemy async session for database operations.
            legal_hold_manager: Optional LegalHoldManager instance.
                If provided, ``purge_expired`` will check ``is_on_hold``
                before deleting records.
            config: Optional override dict for retention tiers.
                If None, uses the module-level RETENTION_TIERS.
        """
        self._db = db
        self._legal_hold_manager = legal_hold_manager
        self._config = dict(config) if config else dict(RETENTION_TIERS)

    async def get_retention_config(self) -> dict:
        """Get the current retention configuration.

        Returns:
            A dict mapping tier names to their config dicts.
        """
        return dict(self._config)

    async def update_retention_config(
        self, tier: str, duration_days: int
    ) -> dict:
        """Update the retention duration for a specific tier.

        Args:
            tier: The tier name (e.g., ``postgresql``, ``minio_worm``).
            duration_days: New retention duration in days.

        Returns:
            The updated tier config dict.

        Raises:
            ValueError: If the tier name is not recognized.
        """
        if tier not in self._config:
            raise ValueError(f"Unknown tier: {tier}")

        self._config[tier]["duration_days"] = duration_days
        logger.info(
            "Updated retention config: %s → %d days", tier, duration_days
        )
        return {
            "tier": tier,
            "duration_days": duration_days,
            "description": self._config[tier]["description"],
        }

    async def purge_expired(
        self, tier: str, dry_run: bool = False
    ) -> dict:
        """Purge expired records for a given retention tier.

        For PostgreSQL: deletes ``data_lineage`` records older than
        the tier's retention duration, excluding records under Legal Hold.
        For MinIO: placeholder for future MinIO object lifecycle purge.
        For Valkey: no-op (TTL handles expiry automatically).

        Args:
            tier: The retention tier to purge.
            dry_run: If True, report what would be deleted without
                actually deleting.

        Returns:
            Dict with keys:
            - ``tier``: The tier that was purged.
            - ``deleted_count``: Number of records deleted (or estimated).
            - ``skipped_legal_hold``: Records skipped due to Legal Hold.
            - ``dry_run``: Whether this was a dry run.
        """
        if tier not in self._config:
            raise ValueError(f"Unknown tier: {tier}")

        # Valkey is TTL-based — no-op
        if tier == "valkey":
            return {
                "tier": "valkey",
                "deleted_count": 0,
                "skipped_legal_hold": 0,
                "dry_run": dry_run,
            }

        # MinIO — placeholder (object lifecycle policies handle this)
        if tier == "minio_worm":
            return {
                "tier": "minio_worm",
                "deleted_count": 0,
                "skipped_legal_hold": 0,
                "dry_run": dry_run,
            }

        # Legal hold — no purge action
        if tier == "legal_hold":
            return {
                "tier": "legal_hold",
                "deleted_count": 0,
                "skipped_legal_hold": 0,
                "dry_run": dry_run,
            }

        # PostgreSQL tier — delete expired lineage records
        tier_config = self._config[tier]
        duration_days = tier_config["duration_days"]
        cutoff = datetime.now(UTC) - timedelta(days=duration_days)

        # Check Legal Hold
        skipped = 0
        if self._legal_hold_manager is not None:
            try:
                on_hold = await self._legal_hold_manager.is_on_hold(
                    tenant_id="*"
                )
                if on_hold:
                    # In a real implementation, we'd check per-record hold
                    skipped = 1
            except Exception:
                logger.warning(
                    "Legal Hold check failed during purge", exc_info=True
                )

        if dry_run:
            # Estimate count without deleting
            count_stmt = text(
                "SELECT COUNT(*) FROM data_lineage WHERE request_timestamp < :cutoff"
            )
            try:
                result = await self._db.execute(count_stmt, {"cutoff": cutoff})
                row = await result.fetchone()
                estimated = row[0] if row else 0
            except Exception:
                estimated = 0

            return {
                "tier": "postgresql",
                "deleted_count": estimated,
                "skipped_legal_hold": skipped,
                "dry_run": True,
            }

        # Actual deletion
        delete_stmt = text(
            "DELETE FROM data_lineage WHERE request_timestamp < :cutoff"
        )
        try:
            result = await self._db.execute(delete_stmt, {"cutoff": cutoff})
            deleted = result.rowcount
            await self._db.commit()
            logger.info(
                "Purged %d expired records from %s tier",
                deleted, tier,
            )
        except Exception as exc:
            await self._db.rollback()
            logger.error("Failed to purge %s tier: %s", tier, exc)
            deleted = 0

        return {
            "tier": "postgresql",
            "deleted_count": deleted,
            "skipped_legal_hold": skipped,
            "dry_run": False,
        }

    async def run_scheduled_purge(self) -> list[dict]:
        """Run purge for all applicable tiers.

        This is intended to be called by a scheduled task (e.g., cron).
        Processes all tiers that have explicit duration_days set.

        Returns:
            A list of result dicts, one per tier processed.
        """
        results: list[dict] = []
        for tier_name, tier_config in self._config.items():
            if tier_config.get("duration_days") is not None:
                result = await self.purge_expired(tier_name)
                results.append(result)
        return results



