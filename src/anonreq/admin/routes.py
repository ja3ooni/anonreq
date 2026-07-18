"""Admin API routes for custom detection rules hot-reload.

Provides:
- GET  /v1/config/rules — returns active config metadata (D-150)
- POST /v1/admin/config/rules — hot-reload custom rules (D-147)

POST is protected by admin API key authentication (D-151).
GET is not admin-protected — uses gateway API key from main auth middleware.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from anonreq.admin.auth import verify_admin_api_key
from anonreq.admin.config import (
    AtomicConfigRegistry,
    CustomRecognizerRule,
    ExclusionEntry,
    RulesConfig,
)

logger = logging.getLogger(__name__)

admin_router = APIRouter()
registry: AtomicConfigRegistry = AtomicConfigRegistry()


class RulesConfigPayload(BaseModel):
    """Pydantic model for the POST /v1/admin/config/rules request body."""

    custom_recognizers: list[dict[str, Any]]
    exclusion_list: list[dict[str, Any]] = []
    thresholds: dict[str, float] = {}


@admin_router.get("/v1/config/rules")
async def get_rules() -> dict[str, Any]:
    """Return active custom rules configuration metadata.

    Returns metadata about the active recognizers (not raw patterns)
    per D-150.  This endpoint is NOT admin-protected — it uses the
    gateway API key from the main auth middleware.
    """
    config = registry.get_active()
    return {
        "version": registry.get_version(),
        "recognizer_count": len(config.custom_recognizers),
        "exclusion_count": len(config.exclusion_list),
        "thresholds": config.thresholds,
        "recognizers": [
            {
                "id": r.id,
                "entity_type": r.entity_type,
                "pattern_count": len(r.patterns),
                "enabled": r.enabled,
                "version": r.version,
            }
            for r in config.custom_recognizers
        ],
    }


@admin_router.post(
    "/v1/admin/config/rules",
    dependencies=[Depends(verify_admin_api_key)],
)
async def update_rules(payload: RulesConfigPayload) -> dict[str, Any]:
    """Hot-reload custom detection rules.

    Accepts a configuration payload with custom recognizer patterns and
    exclusion list entries.  Validates the input and atomically swaps
    the active config if valid (AG-16).

    Args:
        payload: The rules configuration payload.

    Returns:
        Dict with status and new version number on success.

    Raises:
        HTTPException: 422 if config is invalid, 401 if not authorized.
    """
    try:
        new_config = RulesConfig(
            custom_recognizers=[
                CustomRecognizerRule(**cr) for cr in payload.custom_recognizers
            ],
            exclusion_list=[
                ExclusionEntry(**ex) for ex in payload.exclusion_list
            ],
            thresholds=payload.thresholds,
        )
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=422,
            detail=f"Invalid config structure: {e}",
        )

    success, error = registry.validate_and_swap(new_config)
    if not success:
        raise HTTPException(status_code=422, detail=error)

    logger.info(
        "Custom rules config updated via API",
        extra={
            "version": registry.get_version(),
            "recognizer_count": len(new_config.custom_recognizers),
            "exclusion_count": len(new_config.exclusion_list),
        },
    )

    return {"status": "ok", "version": registry.get_version()}
