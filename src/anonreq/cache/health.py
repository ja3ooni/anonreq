"""Cache health check logic for the AnonReq gateway.

Per CACH-06: The health check verifies:
1. Valkey is reachable (via PING)
2. Persistence is disabled (``save ""`` — no RDB or AOF)

The result dict contains ``reachable``, ``persistence_disabled``, and
``healthy`` booleans.  ``healthy`` is ``True`` only when both conditions
are met.

This module is used by the ``/health`` endpoint (Phase 1) and the
pre-flight startup checks (Phase 1). It is implemented here because it
requires access to ``'CacheManager'._redis`` internals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from anonreq.cache.manager import CacheManager


async def check_cache_health(manager: CacheManager) -> dict[str, Any]:
    """Check Valkey reachability and persistence-disabled state.

    Args:
        manager: A ``'CacheManager'`` instance with an active Valkey
            connection.

    Returns:
        A dict with:
        - ``reachable``: ``True`` if the PING command succeeded.
        - ``persistence_disabled``: ``True`` if ``CONFIG GET save``
          returns an empty string.
        - ``healthy``: ``True`` only when both reachable and
          persistence-disabled are ``True``.
        - ``error``: Present only when an exception occurs (contains
          the exception message).
    """
    try:
        ping = await manager._redis.ping()
        config_save = await manager._redis.config_get("save")
        save_value = config_save.get("save", "") if config_save else ""
        save_val_list = [save_value] if isinstance(save_value, str) else (save_value or [])
        persistence_disabled = not save_val_list or save_val_list == [""]

        return {
            "reachable": ping,
            "persistence_disabled": persistence_disabled,
            "healthy": ping and persistence_disabled,
        }
    except Exception as e:
        return {
            "reachable": False,
            "persistence_disabled": False,
            "healthy": False,
            "error": str(e),
        }
