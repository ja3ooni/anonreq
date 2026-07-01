"""Idempotent stream session cleanup."""

from __future__ import annotations

import inspect
import time
from typing import Any


class SessionCleanup:
    """Deletes session mappings exactly once after stream termination."""

    def __init__(
        self,
        cache_manager: Any,
        tenant_id: str,
        session_id: str,
        audit_logger: Any = None,
        metrics: Any = None,
    ) -> None:
        self._cache = cache_manager
        self._tenant_id = tenant_id
        self._session_id = session_id
        self._audit_logger = audit_logger
        self._metrics = metrics
        self._cleaned = False
        self._started_at = time.monotonic()
        self.terminal_state: str | None = None

    async def cleanup(self, terminal_state: str = "FINISH") -> None:
        if self._cleaned:
            return
        self._cleaned = True
        self.terminal_state = terminal_state

        if hasattr(self._cache, "delete_mapping"):
            await self._cache.delete_mapping(self._tenant_id, self._session_id)
        else:
            key = f"anonreq:{self._tenant_id}:{self._session_id}"
            result = self._cache.delete(key)
            if inspect.isawaitable(result):
                await result

        if self._audit_logger is not None and hasattr(self._audit_logger, "info"):
            self._audit_logger.info(
                "stream.cleanup",
                tenant_id=self._tenant_id,
                session_id=self._session_id,
                terminal_state=terminal_state,
                duration_ms=int((time.monotonic() - self._started_at) * 1000),
            )

        if terminal_state == "CLIENT_DISCONNECT" and self._metrics is not None:
            counter = getattr(self._metrics, "disconnects", None)
            if counter is not None and hasattr(counter, "inc"):
                counter.inc()

    async def cleanup_async(self, terminal_state: str = "FINISH") -> None:
        await self.cleanup(terminal_state=terminal_state)
