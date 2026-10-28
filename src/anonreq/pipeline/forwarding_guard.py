"""ForwardingGuard — fail-secure gate before outbound provider call.

Per D-03 (FAIL-05) and D-48:
- Runs immediately before ProviderStage
- Verifies that classification, detection, and tokenisation completed
  successfully (when applicable)
- Every request must have detections, token mappings and a tokenized
  ``transformed_request``; there is no PASS bypass
- Any check fails → 503 fail-secure: request is never forwarded

Instrumentation (D-140, D-161):
- Sets ``ctx.provider_dispatch_time`` on successful verification
- Increments ``fail_secure_events_total`` on fail-secure path
"""

from __future__ import annotations

import time

from structlog import get_logger

from anonreq.exceptions import PipelineAbortError
from anonreq.models.processing_context import ProcessingContext
from anonreq.monitoring.metrics import fail_secure_events
from anonreq.pipeline.base import PipelineStage

logger = get_logger("anonreq.pipeline.guard")


class ForwardingGuard(PipelineStage):
    """Fail-secure gate that ensures all prerequisites are met.

    The guard prevents any outbound call when:
    - Classification did not run (missing ``classification_result``)
    - Detection did not run for an ANONYMIZE request
    - Tokenisation did not complete for an ANONYMIZE request with detections
    """

    def __init__(self) -> None:
        super().__init__("ForwardingGuard")

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        """Verify prerequisites and abort with 503 on failure.

        Returns:
            The unchanged ``ProcessingContext`` if all checks pass, or
            with ``errors`` populated if a check fails.
        """
        # Must have classification result
        if ctx.classification_result is None:
            fail_secure_events.labels(
                tenant_id=ctx.tenant_id,
                failure_type="forwarding_denied",
            ).inc()
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=503,
                    message="ForwardingGuard: classification did not complete",
                    request_id=ctx.request_id,
                )
            )
            return ctx

        action = ctx.classification_result.get("action", "ANONYMIZE")

        # Record provider dispatch time for overhead calculation (D-140).
        ctx.provider_dispatch_time = time.monotonic()

        # Every forwarded request must have been detected and tokenized.
        # There is no PASS bypass: the original request never leaves.
        failure: str | None = None
        if ctx.detections is None:
            failure = "detection did not complete"
        elif ctx.token_mappings is None:
            failure = "tokenisation did not complete"
        elif ctx.transformed_request is None:
            failure = "request was not tokenized"
        if failure is not None:
            fail_secure_events.labels(
                tenant_id=ctx.tenant_id,
                failure_type="forwarding_denied",
            ).inc()
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=503,
                    message=f"ForwardingGuard: {failure}",
                    request_id=ctx.request_id,
                )
            )
            return ctx

        logger.info(
            "forwarding_guard.check",
            stage=self.name,
            request_id=ctx.request_id,
            action=action,
            passed=True,
        )

        return ctx
