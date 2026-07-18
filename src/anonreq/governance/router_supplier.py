"""Supplier governance endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from anonreq.governance.deps import get_db

router = APIRouter()


@router.get("/suppliers")
async def list_suppliers(
    _request: Request,
    risk_status: str | None = None,
    contract_status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """GET /v1/governance/suppliers — list suppliers with optional filters."""
    from anonreq.governance.supplier import SupplierGovernance

    gov = SupplierGovernance(db)
    suppliers = await gov.list_suppliers(
        risk_status=risk_status, contract_status=contract_status
    )
    return {"object": "list", "data": [s.model_dump() for s in suppliers]}


@router.post("/suppliers")
async def create_supplier(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """POST /v1/governance/suppliers — create a supplier record."""
    from anonreq.governance.supplier import SupplierGovernance

    body = await request.json()
    gov = SupplierGovernance(db)
    supplier = await gov.create_supplier(
        name=body["name"],
        provider_type=body.get("provider_type", "llm"),
        contract_status=body.get("contract_status", "active"),
        risk_status=body.get("risk_status", "low"),
    )
    return supplier.model_dump()


@router.get("/suppliers/overdue-reviews")
async def get_supplier_overdue_reviews(
    _request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """GET /v1/governance/suppliers/overdue-reviews — list overdue reviews."""
    from anonreq.governance.supplier import SupplierGovernance

    gov = SupplierGovernance(db)
    overdue = await gov.get_overdue_reviews()
    return {"object": "list", "data": [s.model_dump() for s in overdue]}


@router.post("/suppliers/{supplier_id}/re-evaluate")
async def trigger_supplier_risk_re_evaluation(
    supplier_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """POST /v1/governance/suppliers/{supplier_id}/re-evaluate — trigger re-eval."""
    from anonreq.governance.supplier import SupplierGovernance

    body = await request.json()
    gov = SupplierGovernance(db)
    try:
        result = await gov.trigger_risk_re_evaluation(
            supplier_id, trigger=body.get("trigger", "")
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result.model_dump()
