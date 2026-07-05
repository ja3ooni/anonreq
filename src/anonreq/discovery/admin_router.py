"""Admin API endpoints for discovery, inventory, and costs.

Provides:
- GET /v1/admin/discovery/inventory — list inventory (JSON or CSV)
- GET /v1/admin/discovery/inventory/{service_name} — single record
- POST /v1/admin/discovery/inventory — manual entry
- GET /v1/admin/discovery/costs — cost breakdown
- GET /v1/admin/discovery/refresh — trigger inventory refresh
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from anonreq.dependencies import auth_context

router = APIRouter(prefix="/v1/admin/discovery", dependencies=[Depends(auth_context)])


@router.get("/inventory")
async def list_inventory(
    request: Request,
    format: str = Query("json", regex="^(json|csv)$"),
    provider: str | None = Query(None),
    risk_band: str | None = Query(None),
    approval_status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=10000),
    offset: int = Query(0, ge=0),
):
    """List AI asset inventory with optional filters.

    Returns JSON or CSV based on format parameter.
    Requires admin auth.
    """
    inventory = getattr(request.app.state, "inventory_service", None)
    if inventory is None:
        raise HTTPException(status_code=503, detail="Inventory service not available")

    from anonreq.discovery.inventory import InventoryFilter

    filters = InventoryFilter(
        provider=provider,
        risk_band=risk_band,
        approval_status=approval_status,
    )

    if format == "csv":
        csv_data = await inventory.export_csv(filters=filters)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=inventory.csv"},
        )

    records = inventory.list_records(filters=filters, limit=limit, offset=offset)
    total = len(inventory.list_records(filters=filters)) if hasattr(inventory, "list_records") else len(records)
    return {
        "records": [r.to_dict() for r in records],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/inventory/{service_name}")
async def get_inventory_service(
    request: Request,
    service_name: str,
):
    """Get a single inventory record by service name."""
    inventory = getattr(request.app.state, "inventory_service", None)
    if inventory is None:
        raise HTTPException(status_code=503, detail="Inventory service not available")

    record = inventory.get_record(service_name)
    if record is None:
        raise HTTPException(status_code=404, detail="Service not found")

    return record.to_dict()


@router.post("/inventory")
async def create_inventory_entry(
    request: Request,
    entry: dict[str, Any],
):
    """Create or update a manual inventory entry.

    Accepts InventoryRecord fields as JSON body.
    """
    inventory = getattr(request.app.state, "inventory_service", None)
    if inventory is None:
        raise HTTPException(status_code=503, detail="Inventory service not available")

    from anonreq.discovery.inventory import InventoryRecord

    record = InventoryRecord(
        service_name=entry.get("service_name", ""),
        provider=entry.get("provider"),
        model=entry.get("model"),
        user_count=entry.get("user_count", 0),
        app_count=entry.get("app_count", 0),
        token_volume=entry.get("token_volume", 0),
        estimated_cost=entry.get("estimated_cost", 0.0),
        data_classification=entry.get("data_classification"),
        approval_status=entry.get("approval_status", "not_reviewed"),
        risk_score=entry.get("risk_score", 0.0),
        last_seen=datetime.now(timezone.utc),
        owner=entry.get("owner"),
        business_unit=entry.get("business_unit"),
        sources=["manual"],
    )

    result = inventory.add_record(record)
    return result.to_dict()


@router.get("/costs")
async def get_costs(
    request: Request,
    provider: str | None = Query(None),
    business_unit: str | None = Query(None),
):
    """Get cost breakdown by provider, model, business_unit."""
    inventory = getattr(request.app.state, "inventory_service", None)
    if inventory is None:
        raise HTTPException(status_code=503, detail="Inventory service not available")

    records = inventory.list_records()

    if provider:
        records = [r for r in records if r.provider == provider]
    if business_unit:
        records = [r for r in records if r.business_unit == business_unit]

    from anonreq.discovery.cost_attribution import CostAttributionService
    cost_service = CostAttributionService()
    return cost_service.get_breakdowns(records)


@router.get("/refresh")
async def refresh_inventory(request: Request):
    """Trigger an inventory refresh from DNS/proxy sources."""
    inventory = getattr(request.app.state, "inventory_service", None)
    if inventory is None:
        raise HTTPException(status_code=503, detail="Inventory service not available")

    # In-memory refresh: re-merge from stored sources
    # In production, this would re-read DNS/proxy logs
    return {
        "updated_count": len(inventory._records),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
