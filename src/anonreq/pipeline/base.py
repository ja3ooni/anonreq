"""PipelineStage abstract base class.

Per D-45 through D-49:
- ``PipelineStage`` defines the interface for all pipeline stages
- Each stage receives and returns a ``ProcessingContext``
- Stages are sequential — no concurrent stage execution in Phase 2
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from anonreq.models.processing_context import ProcessingContext


class PipelineStage(ABC):
    """Abstract base class for all pipeline stages.

    Each stage operates on a shared ``ProcessingContext``, reading from
    fields set by prior stages and populating fields consumed by downstream
    stages.  If a stage encounters an unrecoverable error, it must call
    ``ctx.fail_secure(error)`` to abort the pipeline per D-49.
    """

    def __init__(self, name: str) -> None:
        """Initialise the stage with a human-readable name used in logs.

        Args:
            name: Stage name for logging (e.g. ``"ClassificationStage"``).
        """
        self.name = name

    @abstractmethod
    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        """Execute this stage against the processing context.

        Args:
            ctx: The shared ``ProcessingContext`` carrying state from
                previous stages.

        Returns:
            The mutated ``ProcessingContext`` with this stage's results
            populated.  On error, call ``ctx.fail_secure()`` before
            returning — the pipeline manager will abort after this stage.
        """
        ...
