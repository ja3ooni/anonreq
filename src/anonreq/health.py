"""Health endpoint for the AnonReq gateway.

Provides:
- ``GET /health`` - Returns process liveness only.
- ``GET /health/ready`` - Returns cache and Presidio readiness.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Request, Response

from anonreq.__about__ import __version__
from anonreq.cache.health import check_cache_health
from anonreq.config import settings
from anonreq.startup_checks import check_presidio

router = APIRouter(prefix="", tags=["health"])
logger = structlog.get_logger()


def _build_health_response(
    components: dict[str, dict[str, str]],
    all_healthy: bool,
) -> dict:
    """Build the health response body and log the result."""

    overall_status = "healthy" if all_healthy else "degraded"
    logger.info(
        "health_check",
        component="health_check",
        status=overall_status,
        gateway=components["gateway"]["status"],
        valkey=components.get("valkey", {}).get("status"),
        presidio=components.get("presidio", {}).get("status"),
    )
    return {
        "status": overall_status,
        "version": __version__,
        "components": components,
    }


@router.get("/health")
async def health(response: Response) -> dict:
    """Process liveness endpoint.

    Returns 200 for a live FastAPI process without probing downstream
    dependencies.
    """

    components = {"gateway": {"status": "healthy"}}
    response.status_code = 200
    return _build_health_response(components, True)


@router.get("/health/ready")
async def health_ready(request: Request, response: Response) -> dict:
    """Readiness probe endpoint for Docker HEALTHCHECK."""

    cache_manager = request.app.state.cache_manager
    cache_health = await check_cache_health(cache_manager)
    presidio_ok = await check_presidio(settings.PRESIDIO_URL)

    components = {
        "gateway": {"status": "healthy"},
        "valkey": {"status": "healthy" if cache_health["healthy"] else "unhealthy"},
        "presidio": {"status": "healthy" if presidio_ok else "unhealthy"},
    }
    all_healthy = all(
        component["status"] == "healthy" for component in components.values()
    )
    response.status_code = 200 if all_healthy else 503
    return _build_health_response(components, all_healthy)
