"""PipelineManager — stage registry + sequential execution.

Per D-45 through D-49:
- Stages are registered in order via ``register()``
- ``run()`` iterates stages sequentially, checking ``ctx.has_errors()``
  before each stage
- Any stage failure (either via ``ctx.fail_secure()`` or unhandled
  exception) aborts forwarding immediately — no downstream stage,
  especially the provider call, ever executes per D-49 and FAIL-01.
- Stages marked ``guaranteed`` (cleanup and the audit write) still run
  from a ``finally`` block. A failure inside those stages does not
  replace the original pipeline error.
"""

from __future__ import annotations

import sys

from structlog import get_logger

from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.base import PipelineStage

logger = get_logger("anonreq.pipeline")


class PipelineManager:
    """Sequential stage registry and executor.

    Typical usage::

        manager = PipelineManager()
        manager.register(ClassificationStage(engine))
        manager.register(DetectionStage(detector, presidio, arbiter, exclusions))
        manager.register(TokenizationStage(tokenizer, cache))
        manager.register(ForwardingGuard())
        manager.register(ProviderStage(base_url, api_key, timeout))
        manager.register(RestorationStage())
        manager.register(CleanupStage(cache))

        ctx = await manager.run(ctx)
        if ctx.has_errors():
            # return appropriate HTTP error
            ...
    """

    def __init__(self) -> None:
        self._stages: list[PipelineStage] = []

    def register(self, stage: PipelineStage) -> None:
        """Append a stage to the execution pipeline.

        Args:
            stage: A ``PipelineStage`` instance.  Stages execute in the
                order they are registered.
        """
        self._stages.append(stage)

    @property
    def stages(self) -> list[PipelineStage]:
        """Return a read-only copy of the registered stage list."""
        return list(self._stages)

    async def _invoke(
        self,
        ctx: ProcessingContext,
        stage: PipelineStage,
    ) -> tuple[ProcessingContext, Exception | None]:
        """Run one stage. Exceptions are recorded and returned, not raised.

        Errors already on ``ctx`` belong to an earlier stage. A guaranteed
        stage that finishes without adding an error is not a failure.
        """
        prior_errors = len(ctx.errors)
        logger.info(
            "pipeline.stage.start",
            stage=stage.name,
            request_id=ctx.request_id,
        )
        try:
            ctx = await stage.execute(ctx)
        except Exception as exc:
            ctx.fail_secure(exc)
            logger.error(
                "pipeline.stage.exception",
                stage=stage.name,
                request_id=ctx.request_id,
                error_type=type(exc).__name__,
            )
            return ctx, exc

        if len(ctx.errors) > prior_errors:
            logger.error(
                "pipeline.stage.failed",
                stage=stage.name,
                request_id=ctx.request_id,
                error_type=type(ctx.errors[-1]).__name__,
            )
            return ctx, ctx.errors[-1]

        logger.info(
            "pipeline.stage.complete",
            stage=stage.name,
            request_id=ctx.request_id,
        )
        return ctx, None

    async def run(self, ctx: ProcessingContext) -> ProcessingContext:
        """Execute registered stages, then always run guaranteed stages.

        A failure skips every later stage that is not marked ``guaranteed``.
        Cleanup and the audit write are guaranteed: they run from the
        ``finally`` block when the main loop stopped before reaching them.
        The original error stays ``ctx.errors[-1]`` so callers still
        surface it when a guaranteed stage also fails.

        Args:
            ctx: A ``ProcessingContext``, typically pre-populated with
                ``request_id``, ``original_request``, and ``text_nodes``
                by the route handler.

        Returns:
            The (possibly mutated) ``ProcessingContext``.  Callers must
            check ``ctx.has_errors()`` to determine the response.
        """
        surfaced: list[Exception] | None = None
        ran: set[int] = set()
        try:
            for index, stage in enumerate(self._stages):
                if ctx.has_errors():
                    surfaced = list(ctx.errors)
                    break
                ctx, error = await self._invoke(ctx, stage)
                ran.add(index)
                if error is not None:
                    surfaced = list(ctx.errors)
                    break
        finally:
            pending = sys.exc_info()[1]
            for index, stage in enumerate(self._stages):
                if index in ran or getattr(stage, "guaranteed", False) is not True:
                    continue
                try:
                    ctx, error = await self._invoke(ctx, stage)
                except Exception as exc:
                    logger.error(
                        "pipeline.stage.exception",
                        stage=stage.name,
                        request_id=ctx.request_id,
                        error_type=type(exc).__name__,
                    )
                    if surfaced is None and pending is None:
                        ctx.fail_secure(exc)
                        surfaced = list(ctx.errors)
                    continue
                if error is not None and surfaced is None and pending is None:
                    surfaced = list(ctx.errors)
            if surfaced is not None and pending is None:
                ctx.errors = list(surfaced)
        return ctx
