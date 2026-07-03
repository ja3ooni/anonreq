"""Audit chain service with SHA-384 hash chaining.

Provides:
- ``AuditChainService``: Ingests audit events with hash chain computation,
  chain verification, and tamper detection.
- ``ChainVerificationResult``: Result of a chain integrity check.
- ``AuditConfig``: Dataclass for audit configuration values.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from anonreq.models.audit import AuditEvent, compute_event_hash


@dataclass
class ChainVerificationResult:
    """Result of a hash chain verification.

    Attributes:
        is_intact: True if the entire chain verified correctly.
        broken_at: ID of the first broken event, or None if intact.
        checked_count: Number of events checked.
    """

    is_intact: bool
    broken_at: int | None = None
    checked_count: int = 0


@dataclass
class AuditConfig:
    """Audit configuration values.

    Attributes:
        retention_days: Default retention period in days.
        chain_anchor_enabled: Whether daily anchoring is enabled.
        chain_anchor_time: Time of day for anchor computation (UTC).
    """

    retention_days: int = 2557
    chain_anchor_enabled: bool = True
    chain_anchor_time: str = "23:59:59 UTC"


class AuditChainService:
    """Ingests audit events with SHA-384 hash chaining.

    Operations are append-only: no update or delete methods exist.
    Hash chain integrity can be verified at any time via ``verify_chain``.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        config: AuditConfig | None = None,
    ) -> None:
        """Initialize with an async SQLAlchemy engine.

        Args:
            engine: Async SQLAlchemy engine (asyncpg for PostgreSQL,
                aiosqlite for testing).
            config: Audit configuration. Uses defaults if None.
        """
        self._engine = engine
        self._config = config or AuditConfig()
        self._session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def get_latest_event(self, tenant_id: str) -> AuditEvent | None:
        """Fetch the most recent event for a tenant to get prev_hash.

        Uses ``FOR UPDATE`` on PostgreSQL for atomicity; SQLite skips it.

        Args:
            tenant_id: The tenant to query.

        Returns:
            The most recent AuditEvent, or None if no events exist.
        """
        async with self._session_factory() as session:
            return await self._get_latest_event_in_session(session, tenant_id)

    async def _get_latest_event_in_session(
        self,
        session: AsyncSession,
        tenant_id: str,
        for_update: bool = False,
    ) -> AuditEvent | None:
        """Internal: fetch latest event within an existing session/transaction.

        Args:
            session: The async session to use.
            tenant_id: The tenant to query.
            for_update: Whether to add FOR UPDATE (PostgreSQL only).

        Returns:
            AuditEvent or None.
        """
        fu = " FOR UPDATE" if for_update else ""
        result = await session.execute(
            text(
                "SELECT * FROM audit_event "
                "WHERE tenant_id = :tenant_id "
                "ORDER BY id DESC LIMIT 1" + fu
            ),
            {"tenant_id": tenant_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return self._row_to_event(dict(row))

    async def store_event(self, event: AuditEvent) -> AuditEvent:
        """Compute hash, link to previous event, insert atomically.

        Uses ``SELECT ... FOR UPDATE`` on the latest event to prevent
        race conditions on the chain ordering (PostgreSQL only).

        Args:
            event: The AuditEvent to store. Its ``hash`` field will be
                computed and ``prev_hash`` linked to the previous event.

        Returns:
            The stored event with hash and prev_hash populated.

        Raises:
            ValueError: If the event already has a hash set.
        """
        if event.hash:
            raise ValueError("Event already has a hash; cannot re-store")

        dialect = self._engine.dialect.name
        use_for_update = dialect == "postgresql"

        async with self._session_factory() as session:
            async with session.begin():
                latest = await self._get_latest_event_in_session(
                    session, event.tenant_id, for_update=use_for_update,
                )
                event.prev_hash = latest.hash if latest else None
                event.hash = compute_event_hash(event)

                await session.execute(
                    text(
                        "INSERT INTO audit_event "
                        "(event_id, prev_hash, hash, timestamp, tenant_id, "
                        "request_id, policy_id, decision, provider, latency_ms, "
                        "event_type, operator_id, change_type, prev_value_hash, "
                        "new_value_hash, metadata_json, retention_days) "
                        "VALUES (:event_id, :prev_hash, :hash, :timestamp, :tenant_id, "
                        ":request_id, :policy_id, :decision, :provider, :latency_ms, "
                        ":event_type, :operator_id, :change_type, :prev_value_hash, "
                        ":new_value_hash, :metadata_json, :retention_days)"
                    ),
                    {
                        "event_id": event.event_id,
                        "prev_hash": event.prev_hash,
                        "hash": event.hash,
                        "timestamp": event.timestamp,
                        "tenant_id": event.tenant_id,
                        "request_id": event.request_id,
                        "policy_id": event.policy_id,
                        "decision": event.decision,
                        "provider": event.provider,
                        "latency_ms": event.latency_ms,
                        "event_type": event.event_type,
                        "operator_id": event.operator_id,
                        "change_type": event.change_type,
                        "prev_value_hash": event.prev_value_hash,
                        "new_value_hash": event.new_value_hash,
                        "metadata_json": event.metadata_json,
                        "retention_days": event.retention_days,
                    },
                )
        return event

    async def verify_chain(
        self,
        tenant_id: str,
        from_id: int | None = None,
    ) -> ChainVerificationResult:
        """Walk the chain and verify every hash link.

        Iterates from oldest to newest, recomputing each event's hash
        from its fields and comparing against the stored hash.

        Args:
            tenant_id: The tenant to verify.
            from_id: Optional starting event ID. If None, starts from
                the beginning of the chain.

        Returns:
            ChainVerificationResult with integrity status.
        """
        async with self._session_factory() as session:
            if from_id is not None:
                result = await session.execute(
                    text(
                        "SELECT * FROM audit_event "
                        "WHERE tenant_id = :tenant_id AND id >= :from_id "
                        "ORDER BY id ASC"
                    ),
                    {"tenant_id": tenant_id, "from_id": from_id},
                )
            else:
                result = await session.execute(
                    text(
                        "SELECT * FROM audit_event "
                        "WHERE tenant_id = :tenant_id "
                        "ORDER BY id ASC"
                    ),
                    {"tenant_id": tenant_id},
                )

            rows = result.mappings().all()
            if not rows:
                return ChainVerificationResult(is_intact=True, checked_count=0)

            checked = 0
            previous_expected_hash: str | None = None

            for row in rows:
                row_dict = dict(row)
                event = self._row_to_event(row_dict)
                expected = compute_event_hash(event)

                if row_dict["hash"] != expected:
                    return ChainVerificationResult(
                        is_intact=False,
                        broken_at=row_dict["id"],
                        checked_count=checked,
                    )

                if previous_expected_hash is not None and row_dict["prev_hash"] != previous_expected_hash:
                    return ChainVerificationResult(
                        is_intact=False,
                        broken_at=row_dict["id"],
                        checked_count=checked,
                    )

                previous_expected_hash = expected
                checked += 1

        return ChainVerificationResult(is_intact=True, checked_count=checked)

    async def get_events(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
        event_type: str | None = None,
    ) -> list[AuditEvent]:
        """Paginated event query.

        Args:
            tenant_id: The tenant to query.
            limit: Maximum number of events to return.
            offset: Number of events to skip.
            event_type: Optional event type filter.

        Returns:
            List of AuditEvent objects.
        """
        async with self._session_factory() as session:
            if event_type:
                result = await session.execute(
                    text(
                        "SELECT * FROM audit_event "
                        "WHERE tenant_id = :tenant_id "
                        "AND event_type = :event_type "
                        "ORDER BY id DESC "
                        "LIMIT :limit OFFSET :offset"
                    ),
                    {
                        "tenant_id": tenant_id,
                        "event_type": event_type,
                        "limit": limit,
                        "offset": offset,
                    },
                )
            else:
                result = await session.execute(
                    text(
                        "SELECT * FROM audit_event "
                        "WHERE tenant_id = :tenant_id "
                        "ORDER BY id DESC "
                        "LIMIT :limit OFFSET :offset"
                    ),
                    {
                        "tenant_id": tenant_id,
                        "limit": limit,
                        "offset": offset,
                    },
                )
            return [self._row_to_event(dict(row)) for row in result.mappings().all()]

    @staticmethod
    def _row_to_event(row: dict) -> AuditEvent:
        """Convert a DB row dict to an AuditEvent dataclass."""
        ts = row["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

        return AuditEvent(
            event_id=row["event_id"],
            prev_hash=row.get("prev_hash"),
            hash=row["hash"],
            timestamp=ts,
            tenant_id=row["tenant_id"],
            request_id=row.get("request_id"),
            policy_id=row.get("policy_id"),
            decision=row.get("decision"),
            provider=row.get("provider"),
            latency_ms=row.get("latency_ms"),
            event_type=row["event_type"],
            operator_id=row.get("operator_id"),
            change_type=row.get("change_type"),
            prev_value_hash=row.get("prev_value_hash"),
            new_value_hash=row.get("new_value_hash"),
            metadata_json=row.get("metadata_json"),
            retention_days=row.get("retention_days", 2557),
        )
