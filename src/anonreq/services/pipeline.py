"""PipelineService — high-level pipeline orchestrator with DLP integration (Plan 13-02).

This service orchestrates the full request pipeline with DLP stages in the
correct execution order:

  1. Threat Detection (Phase 10)
  2. Content extraction (TextExtractor)
  3. Detection (regex + Presidio)
  4. Classification (Phase 12)
  5. Inbound DLP (Phase 13) ← NEW
  6. PDP #2 — enforces combined policy
  7. Anonymization
  8. Forward to provider
  9. Restoration
  10. Outbound DLP (Phase 13) ← NEW

Inbound DLP runs after Classification (to allow contextual rules) and before
PDP #2 (which enforces the final action).  Outbound DLP scans the provider
response before returning to the client.

Per D-002, D-010, D-015, D-016:
- Execution order: Threat → Classification → DLP → PDP #2 → Provider
- Category wins, then filter — classification tightens, never loosens
- Inbound DLP: detect sensitive data in prompts before provider sees it
- Outbound DLP: detect sensitive data in LLM responses before client receives it
"""

from __future__ import annotations

from typing import Any

from anonreq.models.processing_context import ProcessingContext


class PipelineService:
    """Orchestrates the full request pipeline with DLP integration.

    Wraps the individual pipeline stages (threat detection, content
    extraction, detection, classification, DLP, PDP #2, anonymization,
    forward, restoration) and ensures correct execution ordering.

    DLP stages are the primary additions from this plan:
    - ``_run_inbound_dlp`` — inspects request text before PDP #2
    - ``_run_outbound_dlp`` — inspects response text after restoration
    """

    def __init__(self, dlp_engine: Any = None, pdp2_service: Any = None) -> None:
        """Initialize the pipeline orchestrator.

        Args:
            dlp_engine: DLPEngine instance for content inspection.
            pdp2_service: PDP2Service instance for policy evaluation.
        """
        self._dlp_engine = dlp_engine
        self._pdp2 = pdp2_service

    async def _run_inbound_dlp(self, ctx: ProcessingContext) -> None:
        """Inbound DLP inspection — run after classification, before PDP #2.

        Extracts text from context, inspects for DLP categories, and
        stamps the result on ``ctx.dlp_result``.
        """
        raise NotImplementedError("_run_inbound_dlp not yet implemented")

    async def _run_outbound_dlp(self, ctx: ProcessingContext) -> None:
        """Outbound DLP inspection — scan provider response for exfiltration.

        Dual gate: scans response text before and after restoration.
        Stamps result on ``ctx.outbound_dlp_result``.
        """
        raise NotImplementedError("_run_outbound_dlp not yet implemented")

    async def run(self, ctx: ProcessingContext) -> ProcessingContext:
        """Execute all pipeline stages in the correct order.

        Args:
            ctx: ProcessingContext for the current request.

        Returns:
            The mutated ProcessingContext.  Callers must check
            ``ctx.has_errors()`` to determine the response.
        """
        raise NotImplementedError("run not yet implemented")
