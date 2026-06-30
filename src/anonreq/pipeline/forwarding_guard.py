"""ForwardingGuard — fail-secure gate before outbound provider call.

Per D-03 (FAIL-05) and D-48:
- Runs immediately before ProviderStage
- Verifies that classification, detection, and tokenisation completed
  successfully (when applicable)
- PASS classification → no prerequisite checks needed (forward unchanged)
- ANONYMIZE classification → verifies detections and token_mappings exist
- Any check fails → 503 fail-secure: request is never forwarded
"""

from __future__ import annotations

from typing import Any

import structlog
from structlog import get_logger

from anonreq.exceptions import PipelineAbortError
from anonreq.models.processing_context import ProcessingContext
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
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=503,
                    message="ForwardingGuard: classification did not complete",
                    request_id=ctx.request_id,
                )
            )
            return ctx

        action = ctx.classification_result.get("action", "PASS")

        if action == "PASS":
            # PASS requests need no detection or tokenisation
            logger.info(
                "forwarding_guard.check",
                stage=self.name,
                request_id=ctx.request_id,
                action="PASS",
                passed=True,
            )
            return ctx

        if action == "ANONYMIZE":
            # Verify detection ran
            if ctx.detections is None:
                ctx.fail_secure(
                    PipelineAbortError(
                        status_code=503,
                        message=(
                            "ForwardingGuard: detection did not complete "
                            "for ANONYMIZE request"
                        ),
                        request_id=ctx.request_id,
                    )
                )
                return ctx

            # Verify tokenisation ran (or no mapping needed per TOKN-06/07)
            if ctx.token_mappings is None:
                ctx.fail_secure(
                    PipelineAbortError(
                        status_code=503,
                        message=(
                            "ForwardingGuard: tokenisation did not complete "
                            "for ANONYMIZE request"
                        ),
                        request_id=ctx.request_id,
                    )
                )
                return ctx

            # Verify transformed_request exists (but not for empty detections)
            if ctx.detections and ctx.transformed_request is None:
                ctx.fail_secure(
                    PipelineAbortError(
                        status_code=503,
                        message=(
                            "ForwardingGuard: transformed request not built "
                            "for ANONYMIZE request"
                        ),
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
