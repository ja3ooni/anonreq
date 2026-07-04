"""CleanupStage — deletes Valkey mapping and writes structured audit log.

Per PIPE-05, CACH-04, AUDT-04, AUDT-05:
- Deletes the token mapping from Valkey via ``CacheManager.delete_mapping``
- Writes a structured audit log entry with metadata only (no raw values)
- Audit entry written BEFORE the HTTP response is flushed per AUDT-05
- TTL fallback ensures mapping expires even if DEL fails (CACH-04)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from structlog import get_logger

from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.base import PipelineStage

logger = get_logger("anonreq.pipeline.cleanup")


class CleanupStage(PipelineStage):
    """Post-response cleanup: mapping deletion + structured audit logging.

    Runs after the provider response has been restored.  Deletes the
    session's token mapping from Valkey and emits a metadata-only audit
    log entry per AUDT-02 (no raw values, no token mappings).
    """

    def __init__(self, cache_manager: Any) -> None:
        """Initialise with a cache manager for mapping deletion.

        Args:
            cache_manager: A ``CacheManager`` instance.
        """
        super().__init__("CleanupStage")
        self._cache_manager = cache_manager

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        """Delete mapping and write audit log.

        Steps:
        1. If token_mappings is non-empty: delete from Valkey.
        2. Build structured audit log entry from ctx metadata.
        3. Emit audit log entry.
        4. Return ctx unchanged (cleanup failure does not affect response).

        Returns:
            The (unchanged) ``ProcessingContext``.
        """
        # ── Delete Valkey mapping ──────────────────────────────────────────
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
            except Exception:
                logger.warning(
                    "cleanup.mapping_delete_failed",
                    stage=self.name,
                    request_id=ctx.request_id,
                )
                # Per T-02-04-03: TTL fallback handles expiry if DEL fails.
                # Pipeline does NOT fail if DEL fails.

        # ── Build structured audit log ─────────────────────────────────────
        audit_entry = self._build_audit_entry(ctx)
        logger.info("audit.request_complete", **audit_entry)

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
        # Entity counts from detections
        entity_counts: dict[str, int] = {}
        if ctx.detections:
            for d in ctx.detections:
                etype = d.get("entity_type", "UNKNOWN")
                entity_counts[etype] = entity_counts.get(etype, 0) + 1

        # Classification action
        action = "unknown"
        matched_rule_ids: list[str] = []
        if ctx.classification_result:
            action = ctx.classification_result.get("action", "unknown")
            matched_rule_ids = ctx.classification_result.get("matched_rule_ids", [])

        # Error info
        error_type: str | None = None
        if ctx.errors:
            last_error = ctx.errors[-1]
            error_type = type(last_error).__name__

        # Provider status
        provider_status = 0
        action_taken = "anonymized"
        if ctx.classification_result:
            ca = ctx.classification_result.get("action", "PASS")
            if ca == "PASS":
                action_taken = "passed"
            elif ca == "BLOCK":
                action_taken = "blocked"

        if ctx.provider_response:
            # The provider response is not inspected for status — this is
            # a metadata field.  We just note that a response was received.
            provider_status = 200 if ctx.restored_response else 0

        # Classification (Phase 12)
        classification_level = None
        classification_labels = []
        classification_client_override = False
        classification_client_asserted_level = None

        if ctx.classification_result_v2:
            res = ctx.classification_result_v2
            classification_level = res.highest.name
            classification_labels = res.labels
            classification_client_override = res.client_override
            classification_client_asserted_level = res.client_asserted_level.name if res.client_asserted_level else None

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": ctx.request_id,
            "tenant_id": ctx.tenant_id,
            "context_id": ctx.context_id or "",
            "classification_action": action,
            "matched_rule_ids": matched_rule_ids,
            "entity_counts": entity_counts,
            "token_count": len(ctx.token_mappings) if ctx.token_mappings else 0,
            "provider_status": provider_status,
            "error_type": error_type,
            "action_taken": action_taken,
            "classification_level": classification_level,
            "classification_labels": classification_labels,
            "classification_client_override": classification_client_override,
            "classification_client_asserted_level": classification_client_asserted_level,
        }
