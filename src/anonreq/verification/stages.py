"""Post-restoration scan pipeline stages.

Provides ``ScanStage`` (non-streaming) and ``StreamScanStage`` (streaming)
that execute warn-only scans after restoration, incrementing the
``unrestored_tokens`` counter when residual tokens are found per D-143.

Both stages are warn-only per AG-17:
- Never modify the response
- Never raise exceptions
- Never block response delivery
"""

from __future__ import annotations

import logging
from typing import Any

from anonreq.monitoring.metrics import unrestored_tokens
from anonreq.verification.scanner import ResponseScanner

logger = logging.getLogger(__name__)
scanner = ResponseScanner()


class ScanStage:
    """Non-streaming scan stage — scans after restoration, before response.

    Operates on ``context.restored_response`` (dict, converted to string for
    scanning).  Increments ``unrestored_tokens`` counter and logs a warning
    if residual tokens are found.  Never modifies or blocks the response
    per AG-17.
    """

    async def execute(self, context: Any) -> None:
        """Execute the scan on the restored response.

        Args:
            context: ``ProcessingContext`` with ``restored_response`` set by
                the ``RestorationStage``.
        """
        if context.restored_response is None:
            return

        text = str(context.restored_response)
        result = scanner.scan(text)

        if result.match_count > 0:
            # Increment unrestored_tokens counter for each match
            for _ in result.matches:
                unrestored_tokens.labels(entity_type="UNKNOWN").inc()

            logger.warning(
                "Unrestored tokens detected after restoration",
                extra={"count": result.match_count, "tokens": result.matches},
            )

        # Never modifies context.restored_response — warn-only per AG-17


class StreamScanStage:
    """Streaming scan stage — scans assembled text after FINISH event.

    Operates on ``context.assembled_response`` (full text assembled from
    stream chunks).  Increments ``unrestored_tokens`` counter and logs a
    warning if residual tokens are found.  Never blocks emission per AG-17.
    """

    async def execute(self, context: Any) -> None:
        """Execute the scan on the assembled stream response.

        Args:
            context: ``ProcessingContext`` with ``assembled_response`` set
                after stream FINISH event.
        """
        if context.assembled_response is None:
            return

        text = str(context.assembled_response)
        result = scanner.scan(text)

        if result.match_count > 0:
            # Increment unrestored_tokens counter for each match
            for _ in result.matches:
                unrestored_tokens.labels(entity_type="UNKNOWN").inc()

            logger.warning(
                "Unrestored tokens detected in streamed response",
                extra={"count": result.match_count, "tokens": result.matches},
            )

        # Never blocks FINISH emission per AG-17
