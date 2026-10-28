"""Unit tests for AuditChainService with aiosqlite async engine."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from anonreq.models.audit import AuditEvent
from anonreq.services.audit_chain import (
    AuditChainService,
    AuditConfig,
)

_CREATE_TABLE = """\
CREATE TABLE audit_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    prev_hash TEXT,
    hash TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    tenant_id TEXT NOT NULL,
    request_id TEXT,
    policy_id TEXT,
    decision TEXT,
    provider TEXT,
    latency_ms INTEGER,
    event_type TEXT NOT NULL,
    operator_id TEXT,
    change_type TEXT,
    prev_value_hash TEXT,
    new_value_hash TEXT,
    metadata_json TEXT,
    retention_days INTEGER NOT NULL DEFAULT 2557
)"""


def _make_event(
    event_id: str,
    tenant_id: str,
    event_type: str = "config_change",
    **overrides: object,
) -> AuditEvent:
    return AuditEvent(
        event_id=event_id,
        prev_hash=None,
        hash="",
        timestamp=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        tenant_id=tenant_id,
        request_id=None,
        policy_id=None,
        decision=None,
        provider=None,
        latency_ms=None,
        event_type=event_type,
        operator_id=None,
        change_type=None,
        prev_value_hash=None,
        new_value_hash=None,
        metadata_json=None,
        **overrides,  # type: ignore[arg-type]
    )


@pytest_asyncio.fixture
async def engine() -> AsyncEngine:  # type: ignore[misc]
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.execute(text(_CREATE_TABLE))
    yield eng  # type: ignore[misc]
    await eng.dispose()


@pytest.fixture
def chain(engine: AsyncEngine) -> AuditChainService:
    return AuditChainService(engine)


@pytest.mark.unit
class TestAuditChainService:
    @pytest.mark.anyio
    async def test_store_and_retrieve(self, chain: AuditChainService) -> None:
        event = _make_event("evt-1", "t1")
        stored = await chain.store_event(event)
        assert stored.hash != ""
        assert stored.prev_hash is None

        latest = await chain.get_latest_event("t1")
        assert latest is not None
        assert latest.event_id == "evt-1"

    @pytest.mark.anyio
    async def test_chain_links_prev_hash(self, chain: AuditChainService) -> None:
        e1 = await chain.store_event(_make_event("e1", "t1"))
        e2 = await chain.store_event(_make_event("e2", "t1"))
        e3 = await chain.store_event(_make_event("e3", "t1"))

        assert e2.prev_hash == e1.hash
        assert e3.prev_hash == e2.hash

    @pytest.mark.anyio
    async def test_verify_intact_chain(self, chain: AuditChainService) -> None:
        await chain.store_event(_make_event("a", "t1"))
        await chain.store_event(_make_event("b", "t1"))
        await chain.store_event(_make_event("c", "t1"))

        result = await chain.verify_chain("t1")
        assert result.is_intact is True
        assert result.checked_count == 3
        assert result.broken_at is None

    @pytest.mark.anyio
    async def test_verify_empty_tenant(self, chain: AuditChainService) -> None:
        result = await chain.verify_chain("nonexistent")
        assert result.is_intact is True
        assert result.checked_count == 0

    @pytest.mark.anyio
    async def test_verify_from_id(self, chain: AuditChainService) -> None:
        await chain.store_event(_make_event("a", "t1"))
        await chain.store_event(_make_event("b", "t1"))
        await chain.store_event(_make_event("c", "t1"))

        result = await chain.verify_chain("t1", from_id=2)
        assert result.is_intact is True
        assert result.checked_count == 2

    @pytest.mark.anyio
    async def test_tenant_isolation(self, chain: AuditChainService) -> None:
        await chain.store_event(_make_event("a", "t1"))
        await chain.store_event(_make_event("b", "t2"))

        result1 = await chain.verify_chain("t1")
        result2 = await chain.verify_chain("t2")
        assert result1.checked_count == 1
        assert result2.checked_count == 1

        events = await chain.get_events(tenant_id="t1")
        assert len(events) == 1
        assert events[0].tenant_id == "t1"

    @pytest.mark.anyio
    async def test_get_events_filters(self, chain: AuditChainService) -> None:
        await chain.store_event(_make_event("a", "t1", event_type="config_change"))
        await chain.store_event(_make_event("b", "t1", event_type="policy_decision"))
        await chain.store_event(_make_event("c", "t2", event_type="config_change"))

        by_type = await chain.get_events(tenant_id="t1", event_type="policy_decision")
        assert len(by_type) == 1
        assert by_type[0].event_id == "b"

    @pytest.mark.anyio
    async def test_count_events(self, chain: AuditChainService) -> None:
        await chain.store_event(_make_event("a", "t1"))
        await chain.store_event(_make_event("b", "t1"))
        await chain.store_event(_make_event("c", "t2"))

        assert await chain.count_events(tenant_id="t1") == 2
        assert await chain.count_events() == 3

    @pytest.mark.anyio
    async def test_store_rejects_already_hashed(self, chain: AuditChainService) -> None:
        event = _make_event("x", "t1")
        event.hash = "already-set"
        with pytest.raises(ValueError, match="already has a hash"):
            await chain.store_event(event)

    @pytest.mark.anyio
    async def test_pagination(self, chain: AuditChainService) -> None:
        for i in range(5):
            await chain.store_event(_make_event(f"e{i}", "t1"))

        page = await chain.get_events(tenant_id="t1", limit=2, offset=0)
        assert len(page) == 2
        page2 = await chain.get_events(tenant_id="t1", limit=2, offset=2)
        assert len(page2) == 2

    @pytest.mark.anyio
    async def test_anonymization_entity_filter_and_timestamp_sort(
        self, chain: AuditChainService,
    ) -> None:
        older = _make_event("old", "acme", event_type="anonymization")
        older.request_id = "r-old"
        older.decision = "ANONYMIZE"
        older.timestamp = datetime(2026, 1, 1, tzinfo=UTC)
        older.metadata_json = json.dumps({
            "entity_types": ["EMAIL_ADDRESS"],
            "entity_counts": {"EMAIL_ADDRESS": 2},
            "model": "gpt-4o",
            "locale": "en",
            "token_count": 2,
        })
        newer = _make_event("new", "acme", event_type="anonymization")
        newer.request_id = "r-new"
        newer.decision = "PASS"
        newer.timestamp = datetime(2026, 6, 1, tzinfo=UTC)
        newer.metadata_json = json.dumps({
            "entity_counts": {"EMAIL_ADDRESS": 1, "PERSON": 1},
            "model": "gpt-4o",
        })
        other = _make_event("person", "acme", event_type="anonymization")
        other.request_id = "r-person"
        other.timestamp = datetime(2026, 3, 1, tzinfo=UTC)
        other.metadata_json = json.dumps({"entity_types": ["PERSON"]})
        await chain.store_event(older)
        await chain.store_event(newer)
        await chain.store_event(other)

        emails = await chain.get_events(
            tenant_id="acme",
            event_type="anonymization",
            entity_type="EMAIL_ADDRESS",
            sort="timestamp:asc",
        )
        assert [event.request_id for event in emails] == ["r-old", "r-new"]
        desc = await chain.get_events(
            tenant_id="acme",
            event_type="anonymization",
            entity_type="EMAIL_ADDRESS",
            sort="timestamp:desc",
        )
        assert [event.request_id for event in desc] == ["r-new", "r-old"]
        assert await chain.count_events(
            tenant_id="acme",
            event_type="anonymization",
            entity_type="PERSON",
        ) == 2
        assert await chain.count_events(
            tenant_id="acme",
            event_type="anonymization",
            entity_type="EMAIL_ADDRESS",
            date_from=datetime(2026, 5, 1, tzinfo=UTC),
        ) == 1

    @pytest.mark.anyio
    async def test_keyset_cursor_on_timestamp_and_id(self, chain: AuditChainService) -> None:
        first = _make_event("k1", "acme", event_type="anonymization")
        first.timestamp = datetime(2026, 1, 1, tzinfo=UTC)
        second = _make_event("k2", "acme", event_type="anonymization")
        second.timestamp = datetime(2026, 1, 1, tzinfo=UTC)
        third = _make_event("k3", "acme", event_type="anonymization")
        third.timestamp = datetime(2026, 2, 1, tzinfo=UTC)
        await chain.store_event(first)
        await chain.store_event(second)
        await chain.store_event(third)

        page = await chain.get_events(
            tenant_id="acme",
            event_type="anonymization",
            sort="timestamp:asc",
            limit=2,
        )
        assert [event.event_id for event in page] == ["k1", "k2"]
        assert page[-1].row_id is not None
        nxt = await chain.get_events(
            tenant_id="acme",
            event_type="anonymization",
            sort="timestamp:asc",
            limit=2,
            cursor_timestamp=page[-1].timestamp,
            cursor_id=page[-1].row_id,
        )
        assert [event.event_id for event in nxt] == ["k3"]

    @pytest.mark.anyio
    async def test_metadata_json_preserved(self, chain: AuditChainService) -> None:
        event = _make_event("m", "t1")
        event.metadata_json = '{"key": "value"}'
        stored = await chain.store_event(event)
        assert stored.metadata_json == '{"key": "value"}'

    @pytest.mark.anyio
    async def test_config_defaults(self) -> None:
        cfg = AuditConfig()
        assert cfg.retention_days == 2557
        assert cfg.chain_anchor_enabled is True
        assert cfg.chain_anchor_time == "23:59:59 UTC"


@pytest.mark.unit
class TestAuditChainIdempotency:
    @pytest.mark.anyio
    async def test_log_event_with_same_event_id_writes_once(
        self, chain: AuditChainService, engine: AsyncEngine,
    ) -> None:
        first = await chain.log_event(
            "anonymization", tenant_id="t1", request_id="r1", event_id="idem-1",
        )
        second = await chain.log_event(
            "anonymization", tenant_id="t1", request_id="r1", event_id="idem-1",
        )
        assert first is not None
        assert second is not None
        assert first.event_id == second.event_id == "idem-1"
        assert second.hash == first.hash
        async with engine.connect() as conn:
            count = (await conn.execute(
                text("SELECT COUNT(*) FROM audit_event WHERE event_id = 'idem-1'"),
            )).scalar_one()
        assert count == 1
        result = await chain.verify_chain("t1")
        assert result.is_intact is True
        assert result.checked_count == 1
