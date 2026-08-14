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

from anonreq.middleware.rbac import Role, require_role
from anonreq.services.audit_chain import AuditChainService
from anonreq.services.audit_export import safe_anonymization_row

# Prefix "/v1/admin/audit" is used when registered as a standalone router,
# or "/audit" if registered under the global admin router prefix.
router = APIRouter(prefix="/v1/admin/audit", tags=["admin"])
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
    items: list[ConfigHistoryItem]
    total: int
    limit: int
    offset: int


@router.get("/config-history")
async def get_config_history(
    request: Request,
    tenant_id: str = Query(default=None),
    event_type: str = Query(default=None),
    operator_id: str = Query(default=None),
    date_from: datetime = Query(default=None),
    date_to: datetime = Query(default=None),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0),
    _auth: Annotated[bool | None, Depends(require_admin_role)] = None,
) -> ConfigHistoryResponse:
    """Return paginated, filterable config change audit trail."""
    service = getattr(request.app.state, "audit_chain", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Audit chain service not initialized")

    events = await service.get_events(
        tenant_id=tenant_id,
        event_type=event_type,
        operator_id=operator_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    total = await service.count_events(
        tenant_id=tenant_id,
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

    return ConfigHistoryResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
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
        for e in events:
            evt_dict = {
                "event_id": e.event_id,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "tenant_id": e.tenant_id,
                "change_type": e.change_type,
                "operator_id": e.operator_id,
                "prev_value_hash": e.prev_value_hash,
                "new_value_hash": e.new_value_hash,
            }
            yield json.dumps(evt_dict) + "\n"
        offset += chunk_size


@router.get("/config-history/export")
async def export_config_history(
    request: Request,
    tenant_id: str = Query(default=None),
    event_type: str = Query(default=None),
    operator_id: str = Query(default=None),
    date_from: datetime = Query(default=None),
    date_to: datetime = Query(default=None),
    _auth: Annotated[bool | None, Depends(require_admin_role)] = None,
) -> StreamingResponse:
    """Stream filtered audit events as JSONL."""
    service = getattr(request.app.state, "audit_chain", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Audit chain service not initialized")

    return StreamingResponse(
        _jsonl_stream(service, tenant_id, event_type, operator_id, date_from, date_to),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=config-history-export.jsonl"},
    )


@router.get("/anonymization-export")
async def export_anonymization_activity(
    request: Request,
    tenant_id: str = Query(default=None),
    date_from: datetime = Query(default=None),
    date_to: datetime = Query(default=None),
    export_format: str = Query(default="json", alias="format", pattern="^(json|csv)$"),
    _auth: Annotated[bool | None, Depends(require_admin_role)] = None,
) -> Response:
    """Export anonymization activity for a DPO/BaFin request.

    Columns are metadata only: who, when, which model, which entity *types*
    were masked. Raw identifiers are never exported.
    """
    service = getattr(request.app.state, "audit_chain", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Audit chain service not initialized")

    events = await service.get_events(
        tenant_id=tenant_id,
        event_type="anonymization",
        date_from=date_from,
        date_to=date_to,
        limit=10000,
        offset=0,
    )
    rows = [safe_anonymization_row(e) for e in events]
    if export_format == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=[
                "timestamp",
                "request_id",
                "tenant_id",
                "operator_id",
                "model",
                "locale",
                "entity_types",
                "token_count",
                "decision",
                "compliance_preset",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=anonymization-export.csv"},
        )
    return Response(
        content=json.dumps(rows, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=anonymization-export.json"},
    )
