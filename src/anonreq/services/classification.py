"""Classification service — header parsing, entity classification, per-level handling.

Provides ``ClassificationService`` that wraps ``ClassificationEngine`` with:
1. ``X-AnonReq-Classification`` header parsing
2. Client-asserted override (increase-only per D-009, D-010)
3. Per-level handling policy (allow_and_anonymize / anonymize_and_flag / block)

Plan 12-02 integration: wired into request pipeline after Content-Type dispatch
but before PDP #2.
"""

from __future__ import annotations

import logging

from anonreq.models.classification import (
    ClassificationLevel,
    ClassificationResult,
)
from anonreq.services.classification_engine import ClassificationEngine

logger = logging.getLogger(__name__)


HANDLING_ALLOW_AND_ANONYMIZE = "allow_and_anonymize"
HANDLING_ANONYMIZE_AND_FLAG = "anonymize_and_flag"
HANDLING_BLOCK = "block"


class ClassificationService:
    """Wraps ClassificationEngine with client-override and per-level handling.

    Usage::

        svc = ClassificationService()
        result = await svc.classify(
            entity_types=["EMAIL", "PERSON"],
            client_level=ClassificationService.parse_client_header(request.headers.get("X-AnonReq-Classification")),
        )
        # result.handling_action → "allow_and_anonymize"
    """

    def __init__(self, engine: ClassificationEngine | None = None) -> None:
        self._engine = engine or ClassificationEngine()

    @staticmethod
    def parse_client_header(header_value: str | None) -> ClassificationLevel | None:
        """Parse ``X-AnonReq-Classification`` header value to ``ClassificationLevel``.

        Returns ``None`` for missing, empty, or unparseable values.
        """
        if not header_value:
            return None
        try:
            return ClassificationLevel[header_value.strip().upper()]
        except (KeyError, ValueError):
            logger.warning("Unparseable classification header: %r", header_value)
            return None

    async def classify(
        self,
        entity_types: list[str],
        client_level: ClassificationLevel | None = None,
    ) -> ClassificationResult:
        """Classify entity types, apply client override, set handling action.

        Steps:
        1. Run ``ClassificationEngine.classify_with_client_override``
        2. Determine ``handling_action`` from the highest level
        3. Record ``highest_entity`` from the label(s) at the highest level

        Args:
            entity_types: List of detected entity type strings.
            client_level: Optional client-asserted classification level.

        Returns:
            ``ClassificationResult`` with ``handling_action`` and
            ``highest_entity`` populated.
        """
        result = await self._engine.classify_with_client_override(
            entity_types,
            client_level=client_level,
        )
        result.handling_action = self.determine_handling(result.highest)
        result.highest_entity = self._find_highest_entity(result) or ""
        return result

    @staticmethod
    def determine_handling(level: ClassificationLevel) -> str:
        """Map classification level to handling action (Plan 12-02).

        Per-level handling policy:
        - PUBLIC / INTERNAL / CONFIDENTIAL (≤ 2) → allow_and_anonymize
        - RESTRICTED (3) → anonymize_and_flag
        - HIGHLY_RESTRICTED (4) → block (HTTP 451)
        """
        if level >= ClassificationLevel.HIGHLY_RESTRICTED:
            return HANDLING_BLOCK
        if level >= ClassificationLevel.RESTRICTED:
            return HANDLING_ANONYMIZE_AND_FLAG
        return HANDLING_ALLOW_AND_ANONYMIZE

    @staticmethod
    def _find_highest_entity(result: ClassificationResult) -> str | None:
        """Find the label with the highest classification level.

        Returns the first entity label at the highest level, or ``None``
        if no labels exist.
        """
        if not result.labels:
            return None
        max_detected = max(result.detected_levels) if result.detected_levels else None
        for label, level in zip(result.labels, result.detected_levels, strict=False):
            if level == max_detected:
                return label
        return None
