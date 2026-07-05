"""Immutable data lineage tracker with PostgreSQL + MinIO dual storage.

Per D-009, D-010, D-011:
- Records per-session immutable lineage with full provenance
- Stores in PostgreSQL (queryable) and archives to MinIO (JSONL)
- NO update or delete operations — append-only by design
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from anonreq.lineage.archive import LineageArchiver
from anonreq.models.lineage import LineageRecord

logger = logging.getLogger("anonreq.lineage.tracker")


async def record_lineage(
    db: AsyncSession,
    record: LineageRecord,
    archive_service: LineageArchiver | None = None,
) -> str:
    """Record an immutable lineage entry (module-level convenience).

    Args:
        db: SQLAlchemy async session for PostgreSQL.
        record: The lineage record to store.
        archive_service: Optional LineageArchiver for MinIO archival.

    Returns:
        The record ID string.
    """
    tracker = LineageTracker(db=db, archive_service=archive_service)
    return await tracker.record_lineage(record)


async def query_lineage(
    db: AsyncSession,
    session_id: str | None = None,
    tenant_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[LineageRecord]:
    """Query lineage records (module-level convenience).

    Args:
        db: SQLAlchemy async session.
        session_id: Filter by session ID.
        tenant_id: Filter by tenant ID.
        provider: Filter by provider.
        model: Filter by model.
        date_from: Filter by minimum timestamp.
        date_to: Filter by maximum timestamp.
        skip: Number of records to skip (pagination).
        limit: Maximum number of records to return.

    Returns:
        List of matching LineageRecord instances.
    """
    tracker = LineageTracker(db=db)
    return await tracker.query_lineage(
        session_id=session_id,
        tenant_id=tenant_id,
        provider=provider,
        model=model,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )


class LineageTracker:
    """Immutable lineage record store with PostgreSQL + MinIO archival.

    This is the core class for recording and querying per-session
    data lineage. It writes to a ``data_lineage`` table in PostgreSQL
    and optionally archives to MinIO for long-term compliance storage.

    Per D-011: No update or delete operations are exposed.
    """

    def __init__(
        self,
        db: AsyncSession,
        archive_service: LineageArchiver | None = None,
    ) -> None:
        """Initialize the tracker.

        Args:
            db: SQLAlchemy async session for PostgreSQL queries.
            archive_service: Optional LineageArchiver for MinIO archival.
        """
        self._db = db
        self._archive_service = archive_service

    async def record_lineage(self, record: LineageRecord) -> str:
        """Record an immutable lineage entry.

        Inserts the record into PostgreSQL and archives to MinIO
        if an archive service is configured.

        Args:
            record: The lineage record to store. If ``record.id`` is
                empty, a UUID will be assigned.

        Returns:
            The record ID string.

        Raises:
            RuntimeError: If the database insert fails.
        """
        if not record.id:
            record.id = f"lin_{uuid4().hex[:16]}"

        if record.request_timestamp is None:
            record.request_timestamp = datetime.now(timezone.utc)

        now = record.request_timestamp.isoformat() if record.request_timestamp else datetime.now(timezone.utc).isoformat()

        # Insert into PostgreSQL using raw SQL (no ORM table defined for lineage)
        stmt = text("""
            INSERT INTO data_lineage (
                id, session_id, tenant_id, provider, model,
                entity_types, entity_count, policies_applied,
                classification_action, processing_time_ms,
                request_timestamp, response_timestamp,
                cache_hit, success, error_type
            ) VALUES (
                :id, :session_id, :tenant_id, :provider, :model,
                :entity_types, :entity_count, :policies_applied,
                :classification_action, :processing_time_ms,
                :request_timestamp, :response_timestamp,
                :cache_hit, :success, :error_type
            )
        """)
        params = {
            "id": record.id,
            "session_id": record.session_id,
            "tenant_id": record.tenant_id,
            "provider": record.provider,
            "model": record.model,
            "entity_types": ",".join(record.entity_types) if record.entity_types is not None else None,
            "entity_count": record.entity_count,
            "policies_applied": ",".join(record.policies_applied) if record.policies_applied is not None else None,
            "classification_action": record.classification_action,
            "processing_time_ms": record.processing_time_ms,
            "request_timestamp": record.request_timestamp,
            "response_timestamp": record.response_timestamp,
            "cache_hit": record.cache_hit,
            "success": record.success,
            "error_type": record.error_type,
        }
        try:
            await self._db.execute(stmt, params)
            await self._db.commit()
        except Exception as exc:
            await self._db.rollback()
            raise RuntimeError(f"Failed to record lineage: {exc}") from exc

        # Archive to MinIO if archive service configured
        if self._archive_service is not None:
            try:
                await self._archive_service.archive_lineage(record)
            except Exception as exc:
                logger.warning(
                    "Lineage archival to MinIO failed (record still in PostgreSQL): %s",
                    exc,
                )

        logger.info(
            "Lineage recorded: id=%s session=%s tenant=%s",
            record.id, record.session_id, record.tenant_id,
        )
        return record.id

    async def query_lineage(
        self,
        session_id: str | None = None,
        tenant_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[LineageRecord]:
        """Query lineage records by various filters.

        Args:
            session_id: Filter by exact session ID match.
            tenant_id: Filter by exact tenant ID match.
            provider: Filter by exact provider match.
            model: Filter by exact model match.
            date_from: Only records with request_timestamp >= this value.
            date_to: Only records with request_timestamp <= this value.
            skip: Number of records to skip (for pagination).
            limit: Maximum records to return (default 50, max 500).

        Returns:
            A list of matching LineageRecord instances.
        """
        conditions: list[str] = []
        params: dict = {}

        if session_id is not None:
            conditions.append("session_id = :session_id")
            params["session_id"] = session_id
        if tenant_id is not None:
            conditions.append("tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id
        if provider is not None:
            conditions.append("provider = :provider")
            params["provider"] = provider
        if model is not None:
            conditions.append("model = :model")
            params["model"] = model
        if date_from is not None:
            conditions.append("request_timestamp >= :date_from")
            params["date_from"] = date_from
        if date_to is not None:
            conditions.append("request_timestamp <= :date_to")
            params["date_to"] = date_to

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        stmt = text(f"""
            SELECT * FROM data_lineage
            WHERE {where_clause}
            ORDER BY request_timestamp DESC
            LIMIT :limit OFFSET :skip
        """)
        params["skip"] = skip
        params["limit"] = min(limit, 500)

        try:
            result = await self._db.execute(stmt, params)
            rows = result.fetchall()
        except Exception:
            # Table or query might not exist yet; return empty
            return []

        records: list[LineageRecord] = []
        for row in rows:
            row_dict = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
            # Convert comma-separated strings back to lists
            if isinstance(row_dict.get("entity_types"), str):
                row_dict["entity_types"] = [
                    e.strip() for e in row_dict["entity_types"].split(",") if e.strip()
                ]
            if isinstance(row_dict.get("policies_applied"), str):
                row_dict["policies_applied"] = [
                    p.strip() for p in row_dict["policies_applied"].split(",") if p.strip()
                ]
            records.append(LineageRecord(**row_dict))

        return records

    async def get_lineage_by_session(
        self, session_id: str
    ) -> LineageRecord | None:
        """Get a single lineage record by session ID.

        Args:
            session_id: The session ID to look up.

        Returns:
            The LineageRecord if found, None otherwise.
        """
        records = await self.query_lineage(session_id=session_id, limit=1)
        return records[0] if records else None
