"""Keyset-paginated anonymization events and an unbounded CSV export.

Rows are one per request and contain metadata only. Raw detected values
are never returned. The tenant is the caller's tenant. CSV streams every
matching row and formula-escapes every cell.
"""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncGenerator
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from anonreq.admin.auth import require_administrator
from anonreq.services.audit_export import (
    ANONYMIZATION_EVENT_FIELDS,
    anonymization_event_csv_row,
    anonymization_event_record,
    csv_error_trailer,
    decode_event_cursor,
    encode_event_cursor,
    iter_filtered_events,
)
from anonreq.services.tenant_scope import resolve_scoped_tenant

router = APIRouter(
    prefix="/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_administrator)],
)

_NO_STORE = "no-store"


class EntityTypeCount(BaseModel):
    """How many times one entity type was masked in a request."""

    type: str
    count: int


class AnonymizationEventItem(BaseModel):
    """One anonymization request. Timestamps are ISO-8601 UTC."""

    request_id: str | None = None
    timestamp: str
    tenant_id: str
    model: str | None = None
    locale: str | None = None
    decision: str | None = None
    token_count: int | None = None
    entity_types: list[EntityTypeCount]


class AnonymizationEventsResponse(BaseModel):
    """Keyset page of anonymization events.

    ``next_cursor`` is ``timestamp|id`` of the last row when another page
    exists, otherwise null. Pass it back as the ``cursor`` query param.
    """

    total: int
    limit: int
    next_cursor: str | None = None
    items: list[AnonymizationEventItem]


def _service(request: Request) -> object:
    service = getattr(request.app.state, "audit_chain", None)
    if service is None:
        from anonreq.state import get_app_state

        service = get_app_state(request.app).audit_chain
    if service is None:
        raise HTTPException(status_code=503, detail="Audit chain service not initialized")
    return service


def _cursor(raw: str | None) -> tuple[datetime, int] | None:
    if raw is None or not raw.strip():
        return None
    try:
        return decode_event_cursor(raw.strip())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid cursor") from exc


def _filters(
    tenant_id: str,
    date_from: datetime | None,
    date_to: datetime | None,
    entity_type: str | None,
    sort: str,
) -> dict[str, object]:
    return {
        "tenant_id": tenant_id,
        "event_type": "anonymization",
        "date_from": date_from,
        "date_to": date_to,
        "entity_type": entity_type,
        "sort": sort,
    }


def _next_cursor(records: list[dict[str, object]], limit: int) -> str | None:
    if len(records) < limit:
        return None
    last = records[-1]
    row_id = last.get("row_id")
    timestamp = last.get("timestamp")
    if not isinstance(row_id, int) or not isinstance(timestamp, str) or not timestamp:
        return None
    return encode_event_cursor(timestamp, row_id)


@router.get("/anonymization-events", response_model=AnonymizationEventsResponse)
async def list_anonymization_events(
    request: Request,
    response: Response,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    sort: str = Query(default="timestamp:desc", pattern="^timestamp:(asc|desc)$"),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
) -> AnonymizationEventsResponse:
    """Return one row per anonymized request for the caller's tenant."""
    scoped_tenant = resolve_scoped_tenant(request, tenant_id)
    cursor_parts = _cursor(cursor)
    service = _service(request)
    kwargs: dict[str, object] = {
        "limit": limit,
        "offset": 0,
        **_filters(scoped_tenant, date_from, date_to, entity_type, sort),
    }
    if cursor_parts is not None:
        kwargs["cursor_timestamp"] = cursor_parts[0]
        kwargs["cursor_id"] = cursor_parts[1]
    events = await service.get_events(**kwargs)  # type: ignore[attr-defined]
    total = await service.count_events(  # type: ignore[attr-defined]
        tenant_id=scoped_tenant,
        event_type="anonymization",
        date_from=date_from,
        date_to=date_to,
        entity_type=entity_type,
    )
    records = [anonymization_event_record(event) for event in events]
    items = [
        AnonymizationEventItem.model_validate(
            {key: value for key, value in record.items() if key != "row_id"}
        )
        for record in records
    ]
    response.headers["Cache-Control"] = _NO_STORE
    return AnonymizationEventsResponse(
        total=total,
        limit=limit,
        next_cursor=_next_cursor(records, limit),
        items=items,
    )


async def _csv_stream(
    service: object,
    tenant_id: str,
    date_from: datetime | None,
    date_to: datetime | None,
    entity_type: str | None,
    sort: str,
    snapshot_max_id: int | None = None,
) -> AsyncGenerator[str, None]:
    fieldnames = list(ANONYMIZATION_EVENT_FIELDS)
    header = io.StringIO()
    writer = csv.DictWriter(header, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    yield header.getvalue()
    filters = _filters(tenant_id, date_from, date_to, entity_type, sort)
    if snapshot_max_id is not None:
        filters["max_row_id"] = snapshot_max_id
    try:
        async for event in iter_filtered_events(service, **filters):
            line = io.StringIO()
            writer = csv.DictWriter(line, fieldnames=fieldnames, lineterminator="\n")
            writer.writerow(anonymization_event_csv_row(anonymization_event_record(event)))
            yield line.getvalue()
    except Exception:
        line = io.StringIO()
        writer = csv.DictWriter(line, fieldnames=fieldnames, lineterminator="\n")
        writer.writerow(csv_error_trailer(fieldnames))
        yield line.getvalue()


@router.get("/anonymization-events/export")
async def export_anonymization_events(
    request: Request,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    sort: str = Query(default="timestamp:desc", pattern="^timestamp:(asc|desc)$"),
) -> StreamingResponse:
    """Stream every matching anonymization event as CSV.

    Filters match the JSON list. The tenant is the caller's tenant.
    """
    scoped_tenant = resolve_scoped_tenant(request, tenant_id)
    service = _service(request)
    # Snapshot bound: capture the newest row id before streaming, so rows
    # written while a long export is open are never included. An empty
    # tenant exports only the header (bound 0).
    snapshot_max_id: int | None = None
    max_row_id = getattr(service, "max_row_id", None)
    if callable(max_row_id):
        latest = await max_row_id(scoped_tenant)
        snapshot_max_id = latest if isinstance(latest, int) else 0
    return StreamingResponse(
        _csv_stream(
            service, scoped_tenant, date_from, date_to, entity_type, sort, snapshot_max_id,
        ),
        media_type="text/csv; charset=utf-8",
        headers={
            "Cache-Control": _NO_STORE,
            "Content-Disposition": "attachment; filename=anonymization-events.csv",
        },
    )
