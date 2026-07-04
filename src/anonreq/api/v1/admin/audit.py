"""Admin audit API routes.

Provides endpoints for querying and exporting the config change audit history.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from anonreq.middleware.rbac import Role, require_role
from anonreq.services.audit_chain import AuditChainService

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
    tenant_id: str = Query(default=None),
    event_type: str = Query(default=None),
    operator_id: str = Query(default=None),
    date_from: datetime = Query(default=None),
    date_to: datetime = Query(default=None),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0),
    request: Request = None,
    auth: Annotated[bool, Depends(require_admin_role)] = None,
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
):
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
    tenant_id: str = Query(default=None),
    event_type: str = Query(default=None),
    operator_id: str = Query(default=None),
    date_from: datetime = Query(default=None),
    date_to: datetime = Query(default=None),
    request: Request = None,
    auth: Annotated[bool, Depends(require_admin_role)] = None,
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
