"""Compliance preset routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/v1/compliance", tags=["compliance"])


@router.get("/presets")
async def list_compliance_presets(request: Request) -> dict:
    """GET /v1/compliance/presets returns configured preset metadata."""

    engine = request.app.state.preset_engine
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
