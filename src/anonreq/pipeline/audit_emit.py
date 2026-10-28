"""Shared anonymization audit-chain write.

Both the non-streaming ``CleanupStage`` and streaming ``SessionCleanup``
emit the same ``anonymization`` event. Transient write failures are
retried with bounded exponential backoff. When the budget is exhausted
the failure is counted on ``anonreq_audit_failures_total``, logged at
ERROR with the exception type only, and raised so the request fails
closed.

The audit chain's hash, anchor, and lock logic is not involved here.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from structlog import get_logger

from anonreq.exceptions import PipelineAbortError
from anonreq.models.processing_context import ProcessingContext

logger = get_logger("anonreq.pipeline.audit_emit")

_MAX_ATTEMPTS = 5
_MAX_BACKOFF_SECONDS = 1.0

SleepFn = Callable[[float], Awaitable[None]]


def anonymization_audit_fields(ctx: ProcessingContext) -> dict[str, Any]:
    """Metadata-only fields for an ``anonymization`` audit event.

    No raw prompt, response, token mapping, or entity value is included.
    ``terminal_state`` is added only when the context recorded one, so a
    streaming disconnect or stream error stays on the same event.
    """
    entity_counts: dict[str, int] = {}
    if ctx.detections:
        for detection in ctx.detections:
            entity_type = detection.get("entity_type", "UNKNOWN")
            entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1

    action = "unknown"
    matched_rule_ids: list[str] = []
    if ctx.classification_result:
        action = ctx.classification_result.get("action", "unknown")
        matched_rule_ids = ctx.classification_result.get("matched_rule_ids", [])

    error_type: str | None = None
    if ctx.errors:
        error_type = type(ctx.errors[-1]).__name__

    provider_status = 0
    action_taken = "anonymized"
    if ctx.classification_result:
        classification_action = ctx.classification_result.get("action", "PASS")
        if classification_action == "PASS":
            action_taken = "passed"
        elif classification_action == "BLOCK":
            action_taken = "blocked"

    if ctx.provider_response:
        provider_status = 200 if ctx.restored_response else 0

    classification_level = None
    classification_labels: list[Any] = []
    classification_client_override = False
    classification_client_asserted_level = None
    if ctx.classification_result_v2:
        result = ctx.classification_result_v2
        classification_level = result.highest.name
        classification_labels = result.labels
        classification_client_override = result.client_override
        if result.client_asserted_level:
            classification_client_asserted_level = result.client_asserted_level.name

    fields: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
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
    if ctx.terminal_state:
        fields["terminal_state"] = ctx.terminal_state
    return fields


def _retry_policy(
    attempts: int | None,
    backoff_seconds: float | None,
) -> tuple[int, float]:
    if attempts is None or backoff_seconds is None:
        from anonreq.config import settings

        if attempts is None:
            attempts = settings.AUDIT_WRITE_ATTEMPTS
        if backoff_seconds is None:
            backoff_seconds = settings.AUDIT_WRITE_BACKOFF_SECONDS
    bounded_attempts = max(1, min(int(attempts), _MAX_ATTEMPTS))
    bounded_backoff = max(0.0, min(float(backoff_seconds), _MAX_BACKOFF_SECONDS))
    return bounded_attempts, bounded_backoff


def _backoff_delay(attempt: int, backoff_seconds: float) -> float:
    return min(backoff_seconds * (2 ** (attempt - 1)), _MAX_BACKOFF_SECONDS)


async def emit_anonymization_audit(
    ctx: ProcessingContext,
    *,
    attempts: int | None = None,
    backoff_seconds: float | None = None,
    sleep: SleepFn | None = None,
) -> None:
    """Write the anonymization audit event, then fail closed if it cannot.

    A missing ``audit_chain`` is a deployment without chain storage and
    is a no-op. A chain that is configured but rejects the write is
    retried, then raised as ``PipelineAbortError``.
    """
    if ctx.audit_chain is None:
        return

    max_attempts, backoff = _retry_policy(attempts, backoff_seconds)
    pause = sleep or asyncio.sleep
    audit_fields = anonymization_audit_fields(ctx)
    event_fields: dict[str, Any] = {
        "tenant_id": ctx.tenant_id,
        "request_id": ctx.request_id,
        "operator_id": ctx.audit_metadata.get("operator_id"),
        "provider": ctx.provider,
        "decision": audit_fields.get("classification_action"),
        "latency_ms": (
            int(ctx.processing_overhead_ms)
            if ctx.processing_overhead_ms is not None
            else None
        ),
        "entity_types": sorted(audit_fields.get("entity_counts", {})),
        "entity_counts": audit_fields.get("entity_counts", {}),
        "token_count": audit_fields.get("token_count", 0),
        "locale": ctx.audit_metadata.get("locale"),
        "model": ctx.model,
        "compliance_preset": ctx.audit_metadata.get("compliance_preset"),
    }
    if ctx.terminal_state:
        event_fields["terminal_state"] = ctx.terminal_state
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            await ctx.audit_chain.log_event("anonymization", **event_fields)
            return
        except Exception as exc:
            last_error = exc
            if attempt < max_attempts:
                await pause(_backoff_delay(attempt, backoff))

    from anonreq.monitoring.metrics import audit_failures

    audit_failures.inc()
    logger.error(
        "cleanup.audit_chain_failed",
        request_id=ctx.request_id,
        tenant_id=ctx.tenant_id,
        error_type=type(last_error).__name__ if last_error else "Exception",
        attempt=max_attempts,
    )
    raise PipelineAbortError(
        status_code=500,
        message="Audit write failed",
        request_id=ctx.request_id,
    ) from None
