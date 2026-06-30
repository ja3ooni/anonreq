"""RestorationStage — replaces tokens with original values in provider response.

Per PIPE-04:
- Takes the provider response from ``ctx.provider_response``
- Applies ``Restorer.restore_response()`` to replace all ``[TYPE_N]`` tokens
  with their original values
- Performs post-restoration verification: scans for residual tokens
- On missing provider response: 500 error
"""

from __future__ import annotations

import re
from typing import Any

import structlog
from structlog import get_logger

from anonreq.exceptions import PipelineAbortError
from anonreq.models.processing_context import ProcessingContext
from anonreq.models.tokenization import TOKEN_PATTERN
from anonreq.pipeline.base import PipelineStage
from anonreq.tokenization.restorer import Restorer

logger = get_logger("anonreq.pipeline.restoration")


class RestorationStage(PipelineStage):
    """Restores ``[TYPE_N]`` tokens to original values in the provider response.

    Operates after the provider call completes.  Scans the response for
    token patterns and replaces them using the session's token mapping.
    """

    def __init__(self, restorer: type[Restorer] = Restorer) -> None:
        """Initialise with a restorer class (defaults to ``Restorer``).

        Args:
            restorer: The ``Restorer`` class or an instance with
                ``restore_response`` and ``restore_text`` static methods.
        """
        super().__init__("RestorationStage")
        self._restorer = restorer

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        """Restore tokens in the provider response.

        Steps:
        1. Skip if classification is PASS or BLOCK (no anonymisation).
        2. Fail if ``ctx.provider_response`` is missing.
        3. Restore tokens using ``Restorer.restore_response()``.
        4. Post-restoration scan for residual ``[TYPE_N]`` patterns.
        5. Set ``ctx.restored_response``.

        Returns:
            The mutated ``ProcessingContext``.
        """
        # Skip if no response to restore
        if ctx.classification_result:
            action = ctx.classification_result.get("action")
            if action in ("PASS", "BLOCK"):
                return ctx

        if ctx.provider_response is None:
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=500,
                    message="No provider response to restore",
                    request_id=ctx.request_id,
                )
            )
            return ctx

        # Get token mapping (from in-memory or cache)
        mapping = ctx.token_mappings or {}

        try:
            # Restore tokens in the response
            restored = self._restorer.restore_response(ctx.provider_response, mapping)
            ctx.restored_response = restored

            # Post-restoration verification: scan for residual tokens
            residual_counts: dict[str, int] = {}
            if isinstance(restored, dict):
                restored_str = str(restored)
                for match in TOKEN_PATTERN.finditer(restored_str):
                    entity_type = match.group(0)
                    residual_counts[entity_type] = (
                        residual_counts.get(entity_type, 0) + 1
                    )

            if residual_counts:
                logger.warning(
                    "restoration.residual_tokens",
                    stage=self.name,
                    request_id=ctx.request_id,
                    residual_counts=residual_counts,
                )

            logger.info(
                "restoration.complete",
                stage=self.name,
                request_id=ctx.request_id,
                mapping_size=len(mapping),
            )

        except PipelineAbortError:
            raise
        except Exception as exc:
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=500,
                    message="Restoration stage failed",
                    request_id=ctx.request_id,
                )
            )

        return ctx
