"""Admin audit API routes.

Provides endpoints for querying and exporting the config change audit history
and regulator-safe anonymization activity (entity types only, never raw PII).
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from anonreq.admin.auth import require_administrator
from anonreq.middleware.rbac import Role, require_role
from anonreq.services.audit_chain import AuditChainService
from anonreq.services.audit_export import (
    ANONYMIZATION_CSV_FIELDS,
    csv_error_trailer,
    decode_event_cursor,
    encode_event_cursor,
    escape_csv_formula,
    iso_utc,
    iter_filtered_events,
    safe_anonymization_row,
)
from anonreq.services.tenant_scope import resolve_scoped_tenant

# Prefix "/v1/admin/audit" is used when registered as a standalone router,
# or "/audit" if registered under the global admin router prefix.
router = APIRouter(
    prefix="/v1/admin/audit",
    tags=["admin"],
    dependencies=[Depends(require_administrator)],
)
require_admin_role = require_role(Role.ADMINISTRATOR)


class ConfigHistoryItem(BaseModel):
    event_id: str
    timestamp: datetime
    tenant_id: str
    change_type: str | None
    operator_id: str | None
    prev_value_hash: str | None
    new_value_hash: str | None


class ConfigHistoryResponse(BaseModel):
    """Keyset page of config-history events.

    ``next_cursor`` is ``timestamp|id`` of the last row when another page
    exists, otherwise null. The same shape as anonymization events.
    """

    items: list[ConfigHistoryItem]
    total: int
    limit: int
    next_cursor: str | None = None


@router.get("/config-history")
async def get_config_history(
    request: Request,
    tenant_id: str | None = Query(default=None),
    event_type: str = Query(default=None),
    operator_id: str = Query(default=None),
    date_from: datetime = Query(default=None),
    date_to: datetime = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    cursor: str | None = Query(default=None),
    _auth: Annotated[bool | None, Depends(require_admin_role)] = None,
) -> ConfigHistoryResponse:
    """Return keyset-paginated config change audit trail.

    The tenant is the caller's tenant. A ``tenant_id`` query that names a
    different tenant is rejected. ``cursor`` is ``timestamp|id``.
    """
    scoped_tenant = resolve_scoped_tenant(request, tenant_id)
    service = getattr(request.app.state, "audit_chain", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Audit chain service not initialized")

    cursor_timestamp = None
    cursor_id = None
    if cursor is not None and cursor.strip():
        try:
            cursor_timestamp, cursor_id = decode_event_cursor(cursor.strip())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid cursor") from exc

    events = await service.get_events(
        tenant_id=scoped_tenant,
        event_type=event_type,
        operator_id=operator_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=0,
        sort="timestamp:desc",
        cursor_timestamp=cursor_timestamp,
        cursor_id=cursor_id,
    )
    total = await service.count_events(
        tenant_id=scoped_tenant,
        event_type=event_type,
        operator_id=operator_id,
        date_from=date_from,
        date_to=date_to,
    )

    items = [
        ConfigHistoryItem(
            event_id=e.event_id,
            timestamp=e.timestamp,
            tenant_id=e.tenant_id,
            change_type=e.change_type,
            operator_id=e.operator_id,
            prev_value_hash=e.prev_value_hash,
            new_value_hash=e.new_value_hash,
        )
        for e in events
    ]

    next_cursor = None
    if len(events) == limit and events[-1].row_id is not None:
        stamp = iso_utc(events[-1].timestamp)
        if stamp:
            next_cursor = encode_event_cursor(stamp, events[-1].row_id)
    return ConfigHistoryResponse(
        items=items,
        total=total,
        limit=limit,
        next_cursor=next_cursor,
    )


async def _jsonl_stream(
    service: AuditChainService,
    tenant_id: str | None,
    event_type: str | None,
    operator_id: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> AsyncGenerator[str, None]:
    offset = 0
    chunk_size = 1000
    while True:
        events = await service.get_events(
            tenant_id=tenant_id,
            event_type=event_type,
            operator_id=operator_id,
            date_from=date_from,
            date_to=date_to,
            limit=chunk_size,
            offset=offset,
        )
        if not events:
            break
        for event in events:
            evt_dict = {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "tenant_id": event.tenant_id,
                "change_type": event.change_type,
                "operator_id": event.operator_id,
                "prev_value_hash": event.prev_value_hash,
                "new_value_hash": event.new_value_hash,
            }
            yield json.dumps(evt_dict) + "\n"
        offset += chunk_size


@router.get("/config-history/export")
async def export_config_history(
    request: Request,
    tenant_id: str | None = Query(default=None),
    event_type: str = Query(default=None),
    operator_id: str = Query(default=None),
    date_from: datetime = Query(default=None),
    date_to: datetime = Query(default=None),
    _auth: Annotated[bool | None, Depends(require_admin_role)] = None,
) -> StreamingResponse:
    """Stream filtered audit events as JSONL for the caller's tenant."""
    scoped_tenant = resolve_scoped_tenant(request, tenant_id)
    service = getattr(request.app.state, "audit_chain", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Audit chain service not initialized")

    return StreamingResponse(
        _jsonl_stream(service, scoped_tenant, event_type, operator_id, date_from, date_to),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": "attachment; filename=config-history-export.jsonl",
        },
    )


def _escaped_export_row(event: object) -> dict[str, str]:
    safe = safe_anonymization_row(event)
    return {
        field: escape_csv_formula(safe.get(field))
        for field in ANONYMIZATION_CSV_FIELDS
    }


async def _anonymization_csv_stream(
    service: AuditChainService,
    tenant_id: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    entity_type: str | None,
    *,
    bom: bool,
) -> AsyncGenerator[str, None]:
    """Stream every matching anonymization row. No 10k cap."""
    fieldnames = list(ANONYMIZATION_CSV_FIELDS)
    if bom:
        yield "\ufeff"
    header = io.StringIO()
    writer = csv.DictWriter(header, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    yield header.getvalue()
    try:
        async for event in iter_filtered_events(
            service,
            tenant_id=tenant_id,
            event_type="anonymization",
            date_from=date_from,
            date_to=date_to,
            entity_type=entity_type,
            sort="timestamp:desc",
        ):
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
            writer.writerow(_escaped_export_row(event))
            yield buf.getvalue()
    except Exception:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
        writer.writerow(csv_error_trailer(fieldnames))
        yield buf.getvalue()


@router.get("/anonymization-export")
async def export_anonymization_activity(
    request: Request,
    tenant_id: str | None = Query(default=None),
    date_from: datetime = Query(default=None),
    date_to: datetime = Query(default=None),
    entity_type: str = Query(default=None),
    export_format: str = Query(default="json", alias="format", pattern="^(json|csv)$"),
    bom: bool = Query(default=False),
    _auth: Annotated[bool | None, Depends(require_admin_role)] = None,
) -> Response:
    """Export anonymization activity for a DPO/BaFin request.

    Columns are metadata only: who, when, which model, which entity *types*
    were masked. Raw identifiers are never exported. The tenant is always the
    caller's tenant. CSV streams every matching row. ``bom=true`` prefixes a
    UTF-8 BOM on CSV output.
    """
    scoped_tenant = resolve_scoped_tenant(request, tenant_id)
    service = getattr(request.app.state, "audit_chain", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Audit chain service not initialized")

    if export_format == "csv":
        return StreamingResponse(
            _anonymization_csv_stream(
                service,
                scoped_tenant,
                date_from,
                date_to,
                entity_type,
                bom=bom,
            ),
            media_type="text/csv; charset=utf-8",
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": "attachment; filename=anonymization-export.csv",
            },
        )

    events = await service.get_events(
        tenant_id=scoped_tenant,
        event_type="anonymization",
        date_from=date_from,
        date_to=date_to,
        entity_type=entity_type,
        limit=10000,
        offset=0,
    )
    rows = [safe_anonymization_row(event) for event in events]
    return Response(
        content=json.dumps(rows, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": "attachment; filename=anonymization-export.json",
        },
    )
