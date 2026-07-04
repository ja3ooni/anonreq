"""PDP #2 — Policy Decision Point with DLP-aware evaluation (Plan 13-02).

PDP #2 sits after the DLP Engine in the pipeline and enforces the most
restrictive action across:
1. DLP detections (category determines base action)
2. Classification level (tightens, never loosens)
3. Tenant policy overrides

Execution order:
  ... → DLP Engine → PDP #2 → Anonymize → Forward → Restore → ...

Per D-010: Category wins, then filter — classification tightens, never loosens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from anonreq.models.processing_context import ProcessingContext


@dataclass
class PolicyDecision:
    """Result of PDP #2 evaluation.

    Attributes:
        action: The final action to take (ALLOW, ANONYMIZE, REDACT,
            QUARANTINE, BLOCK).
        status_code: HTTP status code for the response.
        detail: Human-readable reason (safe, no internals).
        audit_event_type: Audit event type for logging.
        metadata_only: If True, only metadata is logged (no payload).
    """

    action: str
    status_code: int
    detail: str
    audit_event_type: str
    metadata_only: bool = False


class PDP2Service:
    """Policy Decision Point #2 — DLP-aware policy evaluation.

    Evaluates the combined DLP + classification + tenant policy context
    and produces a single PolicyDecision that the pipeline enforces.
    """

    def __init__(self, tenant_policies: dict[str, Any] | None = None) -> None:
        self._tenant_policies: dict[str, Any] = tenant_policies or {}

    async def evaluate(self, ctx: ProcessingContext) -> PolicyDecision:
        """Evaluate policies against the processing context.

        Args:
            ctx: ProcessingContext with dlp_result and
                classification_result_v2 populated.

        Returns:
            A PolicyDecision with the combined enforcement action.
        """
        raise NotImplementedError("PDP2Service.evaluate not yet implemented")
