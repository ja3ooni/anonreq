"""Deterministic max classification engine (CLASS-01, CLASS-02).

Maps detected entity types to sensitivity levels using the entity-type-to-
classification mapping. Implements the highest-sensitivity algorithm:

    highest = max(entity_mapping[e] for e in detected_entities)

No AI, no scoring, no confidence blending. Purely deterministic.
"""

from __future__ import annotations

import logging

from anonreq.models.classification import (
    ENTITY_CLASSIFICATION_MAP,
    ClassificationLevel,
    ClassificationResult,
)

logger = logging.getLogger(__name__)


class ClassificationEngine:
    """Computes request sensitivity from detected entity types.

    Uses a deterministic max algorithm: the highest sensitivity level
    among all detected entity types becomes the request classification.
    Unknown entity types default to INTERNAL with a log warning.

    Supports client-asserted override (increase-only) and runtime
    entity map updates for Phase 8 tenant policy integration.
    """

    def __init__(
        self,
        entity_map: dict[str, ClassificationLevel] | None = None,
    ) -> None:
        """Initialize with optional override map.

        Falls back to ``ENTITY_CLASSIFICATION_MAP`` defaults. Override
        maps are typically loaded from tenant policy YAML (Phase 8).
        """
        self._entity_map = dict(entity_map or ENTITY_CLASSIFICATION_MAP)

    async def classify(self, entity_types: list[str]) -> ClassificationResult:
        """Classify request based on detected entity types.

        Deterministic max algorithm:
        1. For each entity type, look up classification level
        2. Unknown types → INTERNAL (log warning)
        3. ``highest = max(levels)``
        4. If empty input → INTERNAL (undetected default per CLASS-02)
        5. Return ``ClassificationResult`` with highest, labels, levels

        Args:
            entity_types: List of detected entity type strings.

        Returns:
            ClassificationResult with computed highest level.
        """
        if not entity_types:
            return ClassificationResult(
                highest=ClassificationLevel.INTERNAL,
                labels=[],
                detected_levels=[],
            )

        labels: list[str] = []
        levels: list[ClassificationLevel] = []

        for et in entity_types:
            level = self._entity_map.get(et.upper())
            if level is None:
                logger.warning("Unknown entity type %r — defaulting to INTERNAL", et)
                level = ClassificationLevel.INTERNAL
            labels.append(et)
            levels.append(level)

        highest = max(levels)

        return ClassificationResult(
            highest=highest,
            labels=labels,
            detected_levels=levels,
        )

    async def classify_with_client_override(
        self,
        entity_types: list[str],
        client_level: ClassificationLevel | None = None,
    ) -> ClassificationResult:
        """Classify and apply client-asserted override (increase-only).

        Higher of detected vs client wins. Client may never decrease
        classification (D-009, D-010). Override logged.

        Args:
            entity_types: List of detected entity type strings.
            client_level: Optional client-asserted classification level.

        Returns:
            ClassificationResult with optional override applied.
        """
        result = await self.classify(entity_types)
        if client_level is not None and client_level > result.highest:
            logger.info(
                "Client override: %s -> %s (original: %s)",
                result.highest.name,
                client_level.name,
                entity_types,
            )
            result.highest = client_level
            result.client_override = True
            result.client_asserted_level = client_level
        return result

    def update_entity_map(
        self,
        overrides: dict[str, ClassificationLevel],
    ) -> None:
        """Merge tenant-specific overrides into entity map.

        Called at runtime when tenant policy YAML is loaded (Phase 8).
        Overrides are additive — existing entries are updated, new ones added.

        Args:
            overrides: Entity-type-to-level overrides from tenant policy.
        """
        self._entity_map.update(overrides)
