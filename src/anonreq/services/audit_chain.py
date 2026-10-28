"""Audit chain service with SHA-384 hash chaining.

Provides:
- ``AuditChainService``: Ingests audit events with hash chain computation,
  chain verification, and tamper detection.
- ``ChainVerificationResult``: Result of a chain integrity check.
- ``AuditConfig``: Dataclass for audit configuration values.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

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

    async def log_event(self, event_type: str, **fields: Any) -> AuditEvent | None:
        """Store a metadata-only audit event. Never pass raw PII in ``fields``."""
        tenant_id = str(fields.pop("tenant_id", "default"))
        request_id = fields.pop("request_id", None)
        operator_id = fields.pop("operator_id", None)
        provider = fields.pop("provider", None)
        decision = fields.pop("decision", None)
        latency_ms = fields.pop("latency_ms", None)
        event_id = fields.pop("event_id", None)
        event = AuditEvent(
            event_id=str(event_id) if event_id else uuid4().hex,
            prev_hash=None,
            hash="",
            timestamp=datetime.now(UTC),
            tenant_id=tenant_id,
            request_id=str(request_id) if request_id else None,
            policy_id=None,
            decision=str(decision) if decision else None,
            provider=str(provider) if provider else None,
            latency_ms=int(latency_ms) if latency_ms is not None else None,
            event_type=event_type,
            operator_id=str(operator_id) if operator_id else None,
            change_type=None,
            prev_value_hash=None,
            new_value_hash=None,
            metadata_json=json.dumps(fields, default=str, sort_keys=True),
            retention_days=self._config.retention_days,
        )
        return await self.store_event(event)

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

        async with self._session_factory() as session, session.begin():
            latest = await self._get_latest_event_in_session(
                session, event.tenant_id, for_update=use_for_update,
            )
            # Idempotency: a retried write whose earlier attempt already
            # committed (for example, it timed out after commit) must not
            # append a second event. The tenant's chain lock is held here.
            existing = await session.execute(
                text("SELECT hash, prev_hash FROM audit_event WHERE event_id = :event_id"),
                {"event_id": event.event_id},
            )
            row = existing.first()
            if row is not None:
                event.hash = row[0]
                event.prev_hash = row[1]
                return event
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

                if previous_expected_hash is not None and row_dict["prev_hash"] != previous_expected_hash:  # noqa: E501
                    return ChainVerificationResult(
                        is_intact=False,
                        broken_at=row_dict["id"],
                        checked_count=checked,
                    )

                previous_expected_hash = expected
                checked += 1

        return ChainVerificationResult(is_intact=True, checked_count=checked)

    def _event_where(
        self,
        *,
        tenant_id: str | None = None,
        event_type: str | None = None,
        operator_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        entity_type: str | None = None,
        sort: str | None = None,
        cursor_timestamp: datetime | None = None,
        cursor_id: int | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Shared WHERE clause for event list and count queries."""
        clauses = ["1=1"]
        params: dict[str, Any] = {}

        if tenant_id is not None:
            clauses.append("tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id
        if event_type is not None:
            clauses.append("event_type = :event_type")
            params["event_type"] = event_type
        if operator_id is not None:
            clauses.append("operator_id = :operator_id")
            params["operator_id"] = operator_id
        if date_from is not None:
            clauses.append("timestamp >= :date_from")
            params["date_from"] = date_from
        if date_to is not None:
            clauses.append("timestamp <= :date_to")
            params["date_to"] = date_to
        if cursor_timestamp is not None and cursor_id is not None:
            clauses.append(self._cursor_clause(sort))
            params["cursor_timestamp"] = cursor_timestamp
            params["cursor_id"] = cursor_id
        if entity_type is not None:
            clauses.append(self._entity_type_clause())
            params["entity_type"] = entity_type

        return " AND ".join(clauses), params

    def _entity_type_clause(self) -> str:
        """Match an entity type stored in metadata_json without raw values.

        ``entity_types`` is a JSON array and ``entity_counts`` is a JSON
        object. The clause is dialect-specific and always bound.
        """
        dialect = self._engine.dialect.name
        if dialect == "postgresql":
            return (
                "("
                "EXISTS ("
                "SELECT 1 FROM jsonb_array_elements_text("
                "CASE WHEN metadata_json IS NOT NULL "
                "AND jsonb_typeof(metadata_json::jsonb -> 'entity_types') = 'array' "
                "THEN metadata_json::jsonb -> 'entity_types' "
                "ELSE '[]'::jsonb END"
                ") AS entity_type_elem(value) "
                "WHERE entity_type_elem.value = :entity_type"
                ") OR ("
                "metadata_json IS NOT NULL "
                "AND jsonb_typeof(metadata_json::jsonb -> 'entity_counts') = 'object' "
                "AND jsonb_exists(metadata_json::jsonb -> 'entity_counts', :entity_type)"
                "))"
            )
        return (
            "("
            "EXISTS ("
            "SELECT 1 FROM json_each("
            "COALESCE(json_extract(metadata_json, '$.entity_types'), '[]')"
            ") AS entity_types_json "
            "WHERE entity_types_json.value = :entity_type"
            ") OR EXISTS ("
            "SELECT 1 FROM json_each("
            "COALESCE(json_extract(metadata_json, '$.entity_counts'), '{}')"
            ") AS entity_counts_json "
            "WHERE entity_counts_json.key = :entity_type"
            "))"
        )

    @staticmethod
    def _cursor_clause(sort: str | None) -> str:
        """Keyset predicate on ``(timestamp, id)``.

        Descending pages move strictly before the cursor. Ascending pages
        move strictly after it. Equal timestamps use the integer id.
        """
        if sort == "timestamp:asc":
            return (
                "(timestamp > :cursor_timestamp OR "
                "(timestamp = :cursor_timestamp AND id > :cursor_id))"
            )
        return (
            "(timestamp < :cursor_timestamp OR "
            "(timestamp = :cursor_timestamp AND id < :cursor_id))"
        )

    @staticmethod
    def _order_by(sort: str | None) -> str:
        if sort == "timestamp:asc":
            return " ORDER BY timestamp ASC, id ASC"
        if sort == "timestamp:desc":
            return " ORDER BY timestamp DESC, id DESC"
        return " ORDER BY id DESC"

    async def get_events(
        self,
        tenant_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
        event_type: str | None = None,
        operator_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        entity_type: str | None = None,
        sort: str | None = None,
        cursor_timestamp: datetime | None = None,
        cursor_id: int | None = None,
    ) -> list[AuditEvent]:
        """Paginated, filterable event query.

        ``cursor_timestamp`` and ``cursor_id`` together select the next
        keyset page. ``offset`` remains for callers that still use it.
        """
        where, params = self._event_where(
            tenant_id=tenant_id,
            event_type=event_type,
            operator_id=operator_id,
            date_from=date_from,
            date_to=date_to,
            entity_type=entity_type,
            sort=sort,
            cursor_timestamp=cursor_timestamp,
            cursor_id=cursor_id,
        )
        params["limit"] = limit
        params["offset"] = offset
        query = (
            "SELECT * FROM audit_event WHERE "
            + where
            + self._order_by(sort)
            + " LIMIT :limit OFFSET :offset"
        )

        async with self._session_factory() as session:
            result = await session.execute(text(query), params)
            return [self._row_to_event(dict(row)) for row in result.mappings().all()]

    async def count_events(
        self,
        tenant_id: str | None = None,
        event_type: str | None = None,
        operator_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        entity_type: str | None = None,
    ) -> int:
        """Count events matching the given filters."""
        where, params = self._event_where(
            tenant_id=tenant_id,
            event_type=event_type,
            operator_id=operator_id,
            date_from=date_from,
            date_to=date_to,
            entity_type=entity_type,
        )
        query = "SELECT COUNT(*) FROM audit_event WHERE " + where

        async with self._session_factory() as session:
            result = await session.execute(text(query), params)
            return result.scalar() or 0

    @staticmethod
    def _row_to_event(row: dict[str, Any]) -> AuditEvent:
        """Convert a DB row dict to an AuditEvent dataclass."""
        ts = row["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)

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
            row_id=row.get("id"),
        )
