"""CleanupStage — deletes Valkey mapping and writes structured audit log.

Per PIPE-05, CACH-04, AUDT-04, AUDT-05:
- Deletes the token mapping from Valkey via ``CacheManager.delete_mapping``
- Writes a structured audit log entry with metadata only (no raw values)
- Audit entry written BEFORE the HTTP response is flushed per AUDT-05
- TTL fallback ensures mapping expires even if DEL fails (CACH-04)
- The audit-chain write is retried, then fails closed. Mapping deletion
  failure does not fail the request.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from structlog import get_logger

from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.audit_emit import anonymization_audit_fields, emit_anonymization_audit
from anonreq.pipeline.base import PipelineStage

logger = get_logger("anonreq.pipeline.cleanup")


class CleanupStage(PipelineStage):
    """Post-response cleanup: mapping deletion + structured audit logging.

    Runs after the provider response has been restored.  Deletes the
    session's token mapping from Valkey and emits a metadata-only audit
    log entry per AUDT-02 (no raw values, no token mappings).
    """

    def __init__(
        self,
        cache_manager: Any,
        *,
        audit_attempts: int | None = None,
        audit_backoff_seconds: float | None = None,
        audit_sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        """Initialise with a cache manager for mapping deletion.

        Args:
            cache_manager: A ``CacheManager`` instance.
            audit_attempts: Override for ``ANONREQ_AUDIT_WRITE_ATTEMPTS``.
            audit_backoff_seconds: Override for the audit write backoff.
            audit_sleep: Awaitable delay used between audit retries.
        """
        super().__init__("CleanupStage")
        self.guaranteed = True
        self._cache_manager = cache_manager
        self._audit_attempts = audit_attempts
        self._audit_backoff_seconds = audit_backoff_seconds
        self._audit_sleep = audit_sleep

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        """Delete mapping and write the audit event.

        Mapping deletion is best-effort (TTL remains the fallback). The
        structured log and the audit-chain write run in ``finally`` so a
        delete error cannot skip them. An audit-chain write that is still
        failing after the retry budget raises and fails the request.

        Returns:
            The ``ProcessingContext``.
        """
        try:
            if ctx.token_mappings and ctx.context_id:
                try:
                    await self._cache_manager.delete_mapping(
                        ctx.tenant_id,
                        ctx.context_id,
                    )
                    logger.info(
                        "cleanup.mapping_deleted",
                        stage=self.name,
                        request_id=ctx.request_id,
                        tenant_id=ctx.tenant_id,
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    logger.warning(
                        "cleanup.mapping_delete_failed",
                        stage=self.name,
                        request_id=ctx.request_id,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                except Exception as exc:
                    logger.warning(
                        "cleanup.mapping_delete_failed",
                        stage=self.name,
                        request_id=ctx.request_id,
                        error=f"{type(exc).__name__}",
                    )
                    # Per T-02-04-03: TTL fallback handles expiry if DEL fails.
                    # Pipeline does NOT fail if DEL fails.
        finally:
            try:
                audit_entry = self._build_audit_entry(ctx)
                logger.info("audit.request_complete", **audit_entry)
            except Exception as exc:
                logger.error(
                    "cleanup.audit_log_failed",
                    stage=self.name,
                    request_id=ctx.request_id,
                    error_type=type(exc).__name__,
                )
            await emit_anonymization_audit(
                ctx,
                attempts=self._audit_attempts,
                backoff_seconds=self._audit_backoff_seconds,
                sleep=self._audit_sleep,
            )
        return ctx

    @staticmethod
    def _build_audit_entry(ctx: ProcessingContext) -> dict[str, Any]:
        """Build a metadata-only audit log entry from the processing context.

        Per AUDT-02: no raw values, no token mappings, no response text.
        Only metadata fields that are safe for the audit log.

        Args:
            ctx: The completed ``ProcessingContext``.

        Returns:
            A dict of audit-safe metadata fields.
        """
        return anonymization_audit_fields(ctx)
