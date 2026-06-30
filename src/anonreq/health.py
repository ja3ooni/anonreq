"""Health endpoint for the AnonReq gateway.

Provides:
- ``GET /health`` — Returns component status (200 if healthy, 503 if degraded).
- ``GET /health/ready`` — Same as /health, intended for Docker HEALTHCHECK.

Per FAIL-03, FAIL-04: Health endpoint exposes component status for
load balancers, orchestrators, and monitoring systems.

The endpoint checks Valkey and Presidio connectivity on each request and
reports the status of each component:
- ``healthy`` — component is reachable and responding
- ``unhealthy`` — component is not reachable
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Response

from anonreq.__about__ import __version__
from anonreq.config import settings
from anonreq.startup_checks import check_presidio, check_valkey

router = APIRouter(prefix="", tags=["health"])
logger = structlog.get_logger()


async def _check_components() -> tuple[dict[str, str], bool]:
    """Run health checks and return component status + overall health.

    Returns:
        A tuple of ``(components, all_healthy)`` where ``components`` is
        a dict of component name to status dict, and ``all_healthy`` is
        ``True`` if all components are healthy.
    """
    valkey_ok = await check_valkey(settings.VALKEY_URL)
    presidio_ok = await check_presidio(settings.PRESIDIO_URL)

    components = {
        "valkey": {"status": "healthy" if valkey_ok else "unhealthy"},
        "presidio": {"status": "healthy" if presidio_ok else "unhealthy"},
        "gateway": {"status": "healthy"},
    }

    all_healthy = all(
        comp["status"] == "healthy" for comp in components.values()
    )

    return components, all_healthy


def _build_health_response(
    components: dict[str, dict[str, str]],
    all_healthy: bool,
) -> dict:
    """Build the health response body and log the result.

    Args:
        components: Component status map.
        all_healthy: Whether all components are healthy.

    Returns:
        A dict with ``status``, ``version``, and ``components`` keys.
    """
    overall_status = "healthy" if all_healthy else "degraded"

    logger.info(
        "health_check",
        component="health_check",
        status=overall_status,
        valkey=components["valkey"]["status"],
        presidio=components["presidio"]["status"],
    )

    return {
        "status": overall_status,
        "version": __version__,
        "components": components,
    }


@router.get("/health")
async def health(response: Response) -> dict:
    """Health check endpoint returning component status.

    Checks Valkey and Presidio connectivity. Returns 200 with
    ``{"status": "healthy", ...}`` when all components are reachable,
    or 503 with ``{"status": "degraded", ...}`` if any component is
    unreachable.

    The response body contains:
    - ``status``: ``"healthy"`` or ``"degraded"``
    - ``version``: Application version string
    - ``components``: Dict with per-component status objects

    Args:
        response: The response object (used to set status code).

    Returns:
        A dict with status information.
    """
    components, all_healthy = await _check_components()
    response.status_code = 200 if all_healthy else 503
    return _build_health_response(components, all_healthy)


@router.get("/health/ready")
async def health_ready(response: Response) -> dict:
    """Readiness probe endpoint for Docker HEALTHCHECK.

    Identical to ``GET /health``. Returns 200 when the gateway is ready
    to accept traffic, 503 when degraded.

    Args:
        response: The response object (used to set status code).

    Returns:
        Same structure as ``GET /health``.
    """
    components, all_healthy = await _check_components()
    response.status_code = 200 if all_healthy else 503
    return _build_health_response(components, all_healthy)
