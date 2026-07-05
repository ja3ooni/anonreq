"""SOC integration status API.

Provides an admin endpoint to query SIEM sink health status.
Mounted at ``/v1/admin/soc/integration/status``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter


def create_soc_status_router(health_monitor: Any) -> APIRouter:
    """Create a FastAPI router exposing SOC integration status.

    Args:
        health_monitor: A ``SinkHealthMonitor`` instance with
            ``get_status()`` and ``get_aggregate_status()`` methods.

    Returns:
        A configured ``APIRouter`` with prefix ``/v1/admin/soc/integration``.
    """
    router = APIRouter(prefix="/v1/admin/soc/integration")

    @router.get("/status")
    async def get_integration_status() -> dict[str, Any]:
        """Return the current health status of all SIEM sinks.

        Response schema:
        - ``aggregate_status``: ``"healthy"`` | ``"degraded"`` | ``"unknown"``
        - ``sinks``: dict mapping sink name to ``SinkStatus`` (Pydantic model)
        - ``summary``: dict with ``healthy``, ``degraded``, ``unknown`` counts
        """
        statuses = health_monitor.get_status()
        aggregate = health_monitor.get_aggregate_status()

        # Build summary counts from reachable field
        healthy = sum(1 for s in statuses.values() if s.reachable)
        degraded = sum(1 for s in statuses.values() if not s.reachable)
        unknown = 0

        return {
            "aggregate_status": aggregate,
            "sinks": {
                name: {
                    "healthy": status.healthy,
                    "reachable": status.reachable,
                    "last_successful_delivery": status.last_successful_delivery,
                    "last_error": status.last_error,
                    "buffer_size": status.buffer_size,
                }
                for name, status in statuses.items()
            },
            "summary": {
                "healthy": healthy,
                "degraded": degraded,
                "unknown": unknown,
            },
        }

    return router
