"""SOC integration status API.

Provides an admin endpoint to query SIEM sink health status.
Mounted at ``/v1/admin/soc/integration/status``.
"""

from __future__ import annotations

from typing import Any


def create_soc_status_response(health_monitor: Any | None) -> dict[str, Any]:
    """Generate a SOC integration status response from a health monitor.

    Can safely handle ``None`` (when sinks are not initialized).

    Args:
        health_monitor: A ``SinkHealthMonitor`` instance or ``None``.

    Returns:
        Dict with ``aggregate_status``, ``sinks``, and ``summary`` keys.
    """
    if health_monitor is None:
        return {
            "aggregate_status": "unknown",
            "sinks": {},
            "summary": {"healthy": 0, "degraded": 0, "unknown": 0},
        }

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
