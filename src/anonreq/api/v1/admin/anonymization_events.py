"""Paginated anonymization event list and unbounded CSV export.

Rows are one per request and contain metadata only. Raw detected values
are never returned. CSV streams every row that matches the same filters
as the JSON list.
"""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncGenerator
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from anonreq.admin.auth import require_administrator
from anonreq.services.audit_export import (
    ANONYMIZATION_EVENT_FIELDS,
    anonymization_event_csv_row,
    anonymization_event_record,
    iter_filtered_events,
)

router = APIRouter(
    prefix="/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_administrator)],
)


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
    """Paginated anonymization events."""

    total: int
    limit: int
    offset: int
    items: list[AnonymizationEventItem]


def _service(request: Request) -> object:
    service = getattr(request.app.state, "audit_chain", None)
    if service is None:
        from anonreq.state import get_app_state

        service = get_app_state(request.app).audit_chain
    if service is None:
        raise HTTPException(status_code=503, detail="Audit chain service not initialized")
    return service


def _filters(
    tenant_id: str | None,
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


@router.get("/anonymization-events", response_model=AnonymizationEventsResponse)
async def list_anonymization_events(
    request: Request,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    sort: str = Query(default="timestamp:desc", pattern="^timestamp:(asc|desc)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AnonymizationEventsResponse:
    """Return one row per anonymized request."""
    service = _service(request)
    filters = _filters(tenant_id, date_from, date_to, entity_type, sort)
    events = await service.get_events(limit=limit, offset=offset, **filters)  # type: ignore[attr-defined]
    total = await service.count_events(  # type: ignore[attr-defined]
        tenant_id=tenant_id,
        event_type="anonymization",
        date_from=date_from,
        date_to=date_to,
        entity_type=entity_type,
    )
    items = [
        AnonymizationEventItem.model_validate(anonymization_event_record(event))
        for event in events
    ]
    return AnonymizationEventsResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


async def _csv_stream(
    service: object,
    tenant_id: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    entity_type: str | None,
    sort: str,
) -> AsyncGenerator[str, None]:
    fieldnames = list(ANONYMIZATION_EVENT_FIELDS)
    header = io.StringIO()
    writer = csv.DictWriter(header, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    yield header.getvalue()

    async for event in iter_filtered_events(
        service,
        **_filters(tenant_id, date_from, date_to, entity_type, sort),
    ):
        line = io.StringIO()
        writer = csv.DictWriter(line, fieldnames=fieldnames, lineterminator="\n")
        writer.writerow(anonymization_event_csv_row(anonymization_event_record(event)))
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

    Pagination is not applied. Filters match ``GET /anonymization-events``.
    """
    service = _service(request)
    return StreamingResponse(
        _csv_stream(service, tenant_id, date_from, date_to, entity_type, sort),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=anonymization-events.csv"},
    )
