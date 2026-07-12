from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from anonreq.firewall.models import FirewallRule
from anonreq.firewall.rules import FirewallRuleLoader


class FirewallRuleReloader:
    def __init__(self, loader: FirewallRuleLoader) -> None:
        self._loader = loader
        self._watcher_task: asyncio.Task[Any] | None = None
        self._logger = logging.getLogger("anonreq.firewall.reloader")

    async def reload(self) -> tuple[list[FirewallRule], list[FirewallRule]]:
        old = list(self._loader.rules)
        try:
            new = self._loader.reload()
            return old, new
        except Exception as exc:
            self._logger.error("firewall.reload_failed", extra={"error": str(exc)})
            return old, list(old)

    async def start_watcher(self, interval: int = 30) -> None:
        async def _watch() -> None:
            while True:
                await asyncio.sleep(interval)
                try:
                    old, new = await self.reload()
                    if old != new:
                        self._logger.info(
                            "firewall.rules_reloaded",
                            extra={"old_count": len(old), "new_count": len(new)},
                        )
                except Exception as exc:
                    self._logger.error(
                        "firewall.watcher_error",
                        extra={"error": str(exc)},
                    )

        self._watcher_task = asyncio.create_task(_watch(), name="firewall-watcher")

    async def stop_watcher(self) -> None:
        if self._watcher_task is not None:
            self._watcher_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._watcher_task
            self._watcher_task = None
