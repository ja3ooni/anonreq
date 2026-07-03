"""Daily chain anchoring service for tamper-evident audit trail.

Provides:
- ``ChainAnchorService``: Computes, signs, stores, and verifies daily
  chain anchors for the audit hash chain.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from anonreq.models.audit import DailyAnchor
from anonreq.services.audit_chain import AuditChainService


@dataclass
class AnchorConfig:
    """Configuration for chain anchoring.

    Attributes:
        signing_key: HMAC-SHA384 signing key. If None, anchoring is
            still computed but not cryptographically signed.
        minio_endpoint: MinIO/S3 endpoint URL.
        minio_access_key: MinIO access key.
        minio_secret_key: MinIO secret key.
        minio_bucket: MinIO bucket name for anchor archives.
        minio_region: MinIO region.
        anchor_time: ISO time string for daily anchor computation.
    """

    signing_key: str | None = None
    minio_endpoint: str | None = None
    minio_access_key: str | None = None
    minio_secret_key: str | None = None
    minio_bucket: str = "anonreq-audit-archives"
    minio_region: str = "us-east-1"
    anchor_time: str = "23:59:59 UTC"


class ChainAnchorService:
    """Daily chain anchoring for tamper-evident audit trail.

    Computes a daily root hash from all events on a given date,
    signs it with HMAC-SHA384, and stores it for verification.
    """

    def __init__(
        self,
        audit_chain: AuditChainService,
        engine: AsyncEngine,
        config: AnchorConfig | None = None,
    ) -> None:
        """Initialize with audit chain service and DB engine.

        Args:
            audit_chain: The AuditChainService to query events from.
            engine: Async SQLAlchemy engine for anchor storage.
            config: Anchor configuration. Uses defaults if None.
        """
        self._audit_chain = audit_chain
        self._engine = engine
        self._config = config or AnchorConfig()
        self._session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    def _date_sql(self) -> str:
        """Return dialect-appropriate date extraction clause.

        PostgreSQL uses ``CAST(timestamp AS date)``; SQLite uses ``DATE(timestamp)``.
        """
        if self._engine.dialect.name == "sqlite":
            return "DATE(timestamp)"
        return "CAST(timestamp AS date)"

    async def compute_daily_anchor(self, anchor_date: date) -> DailyAnchor:
        """Compute the daily root hash from all events on that date.

        1. Query all events for the date, ordered by id.
        2. Concatenate all hashes: combined = ''.join(event.hash for ...).
        3. Compute daily_root_hash = SHA-384(combined).
        4. Sign: HMAC-SHA384(daily_root_hash, signing_key).

        Args:
            anchor_date: The date to compute the anchor for.

        Returns:
            A DailyAnchor with date, root hash, signature, and event count.

        Raises:
            ValueError: If no events exist for the given date.
        """
        async with self._session_factory() as session:
            date_expr = self._date_sql()
            result = await session.execute(
                text(
                    "SELECT hash FROM audit_event "
                    f"WHERE {date_expr} = :anchor_date "
                    "ORDER BY id ASC"
                ),
                {"anchor_date": anchor_date.isoformat()},
            )
            rows = result.all()
            if not rows:
                raise ValueError(f"No events found for date {anchor_date}")

            combined = "".join(row[0] for row in rows)
            daily_root_hash = hashlib.sha384(combined.encode()).hexdigest()

            signature = self._sign_hash(daily_root_hash)

            anchor = DailyAnchor(
                anchor_date=anchor_date,
                daily_root_hash=daily_root_hash,
                signature=signature,
                event_count=len(rows),
                created_at=datetime.utcnow(),
            )
        return anchor

    async def store_anchor(self, anchor: DailyAnchor) -> None:
        """Store anchor in PostgreSQL.

        Also archives to MinIO object storage if configured.

        Args:
            anchor: The DailyAnchor to store.
        """
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    text(
                        "INSERT INTO audit_anchor "
                        "(anchor_date, daily_root_hash, signature, event_count, created_at) "
                        "VALUES (:anchor_date, :daily_root_hash, :signature, "
                        ":event_count, :created_at)"
                    ),
                    {
                        "anchor_date": anchor.anchor_date.isoformat(),
                        "daily_root_hash": anchor.daily_root_hash,
                        "signature": anchor.signature,
                        "event_count": anchor.event_count,
                        "created_at": anchor.created_at,
                    },
                )

        if self._config.minio_endpoint:
            await self._archive_to_minio(anchor)

    async def _archive_to_minio(self, anchor: DailyAnchor) -> None:
        """Archive anchor JSON to MinIO WORM bucket."""
        try:
            from minio import Minio

            client = Minio(
                self._config.minio_endpoint,
                access_key=self._config.minio_access_key,
                secret_key=self._config.minio_secret_key,
                region=self._config.minio_region,
                secure=False,
            )
            object_path = f"anchors/{anchor.anchor_date.isoformat()}/anchor.json"
            data = json.dumps({
                "anchor_date": anchor.anchor_date.isoformat(),
                "daily_root_hash": anchor.daily_root_hash,
                "signature": anchor.signature,
                "event_count": anchor.event_count,
                "created_at": anchor.created_at.isoformat(),
            })
            client.put_object(
                self._config.minio_bucket,
                object_path,
                io.BytesIO(data.encode()),
                len(data),
                content_type="application/json",
            )
        except Exception:
            pass

    async def verify_anchor(self, anchor_date: date) -> bool:
        """Recompute daily root hash from events and verify against stored anchor.

        Args:
            anchor_date: The date to verify.

        Returns:
            True if the anchor is valid, False otherwise.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT daily_root_hash, signature, event_count "
                    "FROM audit_anchor "
                    "WHERE anchor_date = :anchor_date "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"anchor_date": anchor_date.isoformat()},
            )
            row = result.mappings().one_or_none()
            if row is None:
                return False

            stored_hash = row["daily_root_hash"]
            stored_signature = row["signature"]

            result = await session.execute(
                text(
                    "SELECT hash FROM audit_event "
                    f"WHERE {self._date_sql()} = :anchor_date "
                    "ORDER BY id ASC"
                ),
                {"anchor_date": anchor_date.isoformat()},
            )
            rows = result.all()
            if not rows:
                return False

            combined = "".join(row[0] for row in rows)
            recomputed_hash = hashlib.sha384(combined.encode()).hexdigest()
            if recomputed_hash != stored_hash:
                return False

            expected_sig = self._sign_hash(stored_hash)
            if expected_sig != stored_signature:
                return False

        return True

    async def run_daily_anchor(self, anchor_date: date | None = None) -> DailyAnchor:
        """Compute, sign, store, and archive the daily anchor.

        Args:
            anchor_date: The date to anchor. Defaults to yesterday.

        Returns:
            The computed DailyAnchor.
        """
        if anchor_date is None:
            import datetime as dt

            anchor_date = (dt.datetime.utcnow() - dt.timedelta(days=1)).date()

        anchor = await self.compute_daily_anchor(anchor_date)
        await self.store_anchor(anchor)
        return anchor

    async def get_anchor_status(self) -> dict:
        """Return latest anchor date, count, and verification status.

        Returns:
            Dict with latest_anchor_date, event_count, and is_verified.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT anchor_date, event_count FROM audit_anchor "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
            )
            row = result.mappings().one_or_none()
            if row is None:
                return {
                    "latest_anchor_date": None,
                    "event_count": 0,
                    "is_verified": False,
                }

            anchor_date = row["anchor_date"]
            if isinstance(anchor_date, str):
                from datetime import date as date_type

                anchor_date = date_type.fromisoformat(anchor_date)

            is_verified = await self.verify_anchor(anchor_date)
            return {
                "latest_anchor_date": anchor_date.isoformat() if hasattr(anchor_date, "isoformat") else anchor_date,
                "event_count": row["event_count"],
                "is_verified": is_verified,
            }

    def _sign_hash(self, hash_value: str) -> str:
        """Sign a hash with HMAC-SHA384 using the configured key.

        Args:
            hash_value: The hex digest to sign.

        Returns:
            HMAC-SHA384 hex digest, or empty string if no key configured.
        """
        if not self._config.signing_key:
            return ""
        return hmac.new(
            self._config.signing_key.encode(),
            hash_value.encode(),
            hashlib.sha384,
        ).hexdigest()
