"""Compliance preset routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from anonreq.state import get_app_state

router = APIRouter(prefix="/v1/compliance", tags=["compliance"])


@router.get("/presets")
async def list_compliance_presets(request: Request) -> dict[str, Any]:
    """GET /v1/compliance/presets returns configured preset metadata."""

    engine = get_app_state(request.app).preset_engine
    if engine is None:
        raise HTTPException(status_code=503, detail="Preset engine not initialized")
    presets = engine.list_presets()
    return {
        "object": "list",
        "data": [
            {
                "id": preset.id,
                "name": preset.name,
                "description": preset.description,
                "jurisdictions": preset.jurisdictions,
                "mandatory_entity_types": preset.mandatory_entity_types,
                "metadata": preset.metadata,
            }
            for preset in presets.values()
        ],
    }
