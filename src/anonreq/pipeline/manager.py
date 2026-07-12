"""PipelineManager — stage registry + sequential execution.

Per D-45 through D-49:
- Stages are registered in order via ``register()``
- ``run()`` iterates stages sequentially, checking ``ctx.has_errors()``
  before each stage
- Any stage failure (either via ``ctx.fail_secure()`` or unhandled
  exception) aborts the pipeline immediately — no downstream stage,
  especially the provider call, ever executes per D-49 and FAIL-01.
"""

from __future__ import annotations

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

    async def run(self, ctx: ProcessingContext) -> ProcessingContext:
        """Execute all registered stages sequentially.

        For each stage:
        1. Check ``ctx.has_errors()`` — if true, skip remaining stages.
        2. Log stage start.
        3. Execute the stage.
        4. If the stage raised an unhandled exception, record it via
           ``ctx.fail_secure()`` and abort.
        5. If ``ctx.has_errors()`` after execution, log failure and abort.
        6. Log stage completion.

        Args:
            ctx: A ``ProcessingContext``, typically pre-populated with
                ``request_id``, ``original_request``, and ``text_nodes``
                by the route handler.

        Returns:
            The (possibly mutated) ``ProcessingContext``.  Callers must
            check ``ctx.has_errors()`` to determine the response.
        """
        for stage in self._stages:
            if ctx.has_errors():
                break

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
                    error=str(exc),
                )
                break

            if ctx.has_errors():
                logger.error(
                    "pipeline.stage.failed",
                    stage=stage.name,
                    request_id=ctx.request_id,
                    error=str(ctx.errors[-1]),
                )
                break

            logger.info(
                "pipeline.stage.complete",
                stage=stage.name,
                request_id=ctx.request_id,
            )

        return ctx
