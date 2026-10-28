"""The events CSV export is bounded by a snapshot taken at request start."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from anonreq.api.v1.admin.anonymization_events import _csv_stream
from anonreq.services.audit_chain import AuditChainService
from tests.unit.services.test_audit_chain import _CREATE_TABLE


@pytest.mark.asyncio
async def test_export_ignores_rows_written_after_snapshot() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(text(_CREATE_TABLE))
    service = AuditChainService(engine)
    try:
        for i in range(2):
            await service.log_event("anonymization", tenant_id="acme", request_id=f"r{i}")
        await service.log_event("anonymization", tenant_id="other", request_id="o1")

        snapshot = await service.max_row_id("acme")
        assert snapshot is not None

        stream = _csv_stream(service, "acme", None, None, None, "timestamp:asc", snapshot)
        header = await stream.__anext__()
        # A row written while the export is open must not appear.
        await service.log_event("anonymization", tenant_id="acme", request_id="late")
        rows = [line async for line in stream]
    finally:
        await engine.dispose()

    assert header.strip()
    assert len(rows) == 2
    assert "late" not in "".join(rows)


@pytest.mark.asyncio
async def test_max_row_id_is_none_for_empty_tenant() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(text(_CREATE_TABLE))
    try:
        assert await AuditChainService(engine).max_row_id("nobody") is None
    finally:
        await engine.dispose()
