"""Idempotent stream session cleanup."""

from __future__ import annotations

import inspect
import time
from collections.abc import Awaitable, Callable
from typing import Any

from structlog import get_logger

from anonreq.pipeline.audit_emit import emit_anonymization_audit

logger = get_logger("anonreq.streaming.cleanup")


class SessionCleanup:
    """Deletes session mappings exactly once after stream termination.

    The audit-chain write uses the same ``anonymization`` event as the
    non-streaming cleanup stage. It runs after mapping deletion even when
    deletion fails, including client disconnect and stream error states.
    """

    def __init__(
        self,
        cache_manager: Any,
        tenant_id: str,
        session_id: str,
        audit_logger: Any = None,
        metrics: Any = None,
        processing_context: Any = None,
        *,
        audit_attempts: int | None = None,
        audit_backoff_seconds: float | None = None,
        audit_sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._cache = cache_manager
        self._tenant_id = tenant_id
        self._session_id = session_id
        self._audit_logger = audit_logger
        self._metrics = metrics
        self._processing_context = processing_context
        self._audit_attempts = audit_attempts
        self._audit_backoff_seconds = audit_backoff_seconds
        self._audit_sleep = audit_sleep
        self._cleaned = False
        self._started_at = time.monotonic()
        self.terminal_state: str | None = None

    async def _delete_mapping(self) -> None:
        if hasattr(self._cache, "delete_mapping"):
            await self._cache.delete_mapping(self._tenant_id, self._session_id)
            return
        key = f"anonreq:{self._tenant_id}:{self._session_id}"
        result = self._cache.delete(key)
        if inspect.isawaitable(result):
            await result

    def _emit_terminal_log(self, terminal_state: str) -> None:
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

    async def cleanup(self, terminal_state: str = "FINISH") -> None:
        if self._cleaned:
            return
        self._cleaned = True
        self.terminal_state = terminal_state
        if self._processing_context is not None:
            self._processing_context.terminal_state = terminal_state

        try:
            await self._delete_mapping()
        except Exception as exc:
            logger.warning(
                "stream.mapping_delete_failed",
                tenant_id=self._tenant_id,
                session_id=self._session_id,
                error_type=type(exc).__name__,
            )
        finally:
            audit_error: Exception | None = None
            try:
                if self._processing_context is not None:
                    await emit_anonymization_audit(
                        self._processing_context,
                        attempts=self._audit_attempts,
                        backoff_seconds=self._audit_backoff_seconds,
                        sleep=self._audit_sleep,
                    )
            except Exception as exc:
                audit_error = exc
            try:
                self._emit_terminal_log(terminal_state)
            except Exception as exc:
                logger.error(
                    "stream.cleanup_log_failed",
                    tenant_id=self._tenant_id,
                    session_id=self._session_id,
                    error_type=type(exc).__name__,
                )
            if audit_error is not None:
                raise audit_error

    async def cleanup_async(self, terminal_state: str = "FINISH") -> None:
        await self.cleanup(terminal_state=terminal_state)
