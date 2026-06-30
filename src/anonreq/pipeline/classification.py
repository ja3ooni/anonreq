"""ClassificationStage — evaluates rules and determines request action.

Per CLASS-AC-01 through CLASS-AC-05:
- Runs ClassificationEngine against extracted text nodes
- BLOCK action → sets ctx.errors (403 PipelineAbortError)
- ROUTE_LOCAL action → sets ctx.errors (501 not implemented)
- PASS action → stores result, pipeline forwards unchanged
- ANONYMIZE action → stores result, pipeline continues to detection
"""

from __future__ import annotations

from typing import Any

from anonreq.exceptions import PipelineAbortError
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.base import PipelineStage
from anonreq.pipeline.extraction import TextExtractor


class ClassificationStage(PipelineStage):
    """Evaluates classification rules against request text nodes.

    The stage determines which action (BLOCK, PASS, ANONYMIZE, or
    ROUTE_LOCAL) applies to the current request per D-24.

    Attributes:
        _engine: A ``ClassificationEngine`` loaded with YAML rules.
    """

    def __init__(self, engine: Any) -> None:
        """Initialise with a classification engine.

        Args:
            engine: A ``ClassificationEngine`` instance (from
                ``anonreq.classification.engine``).
        """
        super().__init__("ClassificationStage")
        self._engine = engine

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        """Classify the request and set ``ctx.classification_result``.

        Steps:
        1. Ensure ``ctx.text_nodes`` is populated via ``TextExtractor``.
        2. Call ``self._engine.classify(text_nodes)``.
        3. Store the result on ``ctx.classification_result``.
        4. Act on the classification action:
           - ``BLOCK`` → ``ctx.fail_secure(PipelineAbortError(403, ...))``
           - ``ROUTE_LOCAL`` → ``ctx.fail_secure(PipelineAbortError(501, ...))``
           - ``PASS`` or ``ANONYMIZE`` → continue (stored for downstream).

        Returns:
            The mutated ``ProcessingContext``.
        """
        # Ensure text nodes are extracted
        text_nodes = ctx.text_nodes
        if text_nodes is None:
            text_nodes = TextExtractor.extract(ctx.original_request)
            ctx.text_nodes = text_nodes

        # Run classification engine
        result = self._engine.classify(text_nodes)
        ctx.classification_result = result

        # Act on the determined action
        action = result.get("action", "PASS")

        if action == "BLOCK":
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=403,
                    message="Request blocked by policy",
                    request_id=ctx.request_id,
                )
            )
        elif action == "ROUTE_LOCAL":
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=501,
                    message="ROUTE_LOCAL not yet implemented",
                    request_id=ctx.request_id,
                )
            )
        # PASS and ANONYMIZE continue — the result is stored for downstream
        # stages (ForwardingGuard, CleanupStage) to inspect.

        return ctx
