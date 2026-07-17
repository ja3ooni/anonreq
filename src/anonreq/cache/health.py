"""Cache health check logic for the AnonReq gateway.

Per CACH-06: The health check verifies:
1. Valkey is reachable (via PING)
2. Persistence is disabled (``save ""`` -- no RDB or AOF)

The result dict contains ``reachable``, ``persistence_disabled``, and
``healthy`` booleans. ``healthy`` is ``True`` only when both conditions
are met.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from anonreq.cache.manager import CacheManager


async def check_cache_health(manager: CacheManager) -> dict[str, Any]:
    """Check Valkey reachability and persistence-disabled state."""

    try:
        ping = bool(await manager._redis.ping())
        config_save = await manager._redis.config_get("save")
        save_value = config_save.get("save", "") if config_save else ""
        save_val_list = [save_value] if isinstance(save_value, str) else (save_value or [])
        persistence_disabled = not save_val_list or save_val_list == [""]
        healthy = ping and persistence_disabled
        return {
            "reachable": ping,
            "persistence_disabled": persistence_disabled,
            "healthy": healthy,
            "status": "healthy" if healthy else "unhealthy",
        }
    except Exception:
        return {
            "reachable": False,
            "persistence_disabled": False,
            "healthy": False,
            "status": "unhealthy",
        }
