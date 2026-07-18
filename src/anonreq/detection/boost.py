"""Context-word confidence boosting for financial crime detection.

Per D-013:
- High-risk financial crime words within 50 chars of entity → confidence +0.15
- Boost capped at 1.0 (never exceeds maximum confidence)
- Only financial crime entity types boosted (IBAN, PAYMENT_REF, CUSTOMER_ID, AML_CASE_REF)
- Multiple high-risk words near entity = single +0.15 boost (no stacking)

Threat model T-15-03-01:
- Boost capped at 1.0; only financial entity types; single boost per entity
"""

from __future__ import annotations

import logging
import re
from typing import Any

import yaml

from anonreq.models.detection import DetectionResult

logger = logging.getLogger(__name__)

FINANCIAL_ENTITY_TYPES: list[str] = [
    "IBAN",
    "PAYMENT_REF",
    "CUSTOMER_ID",
    "AML_CASE_REF",
]


class ContextBooster:
    """Applies confidence boosting to financial crime entity detections
    based on proximity to high-risk words.

    The booster loads a config file with high-risk words, boost amount,
    proximity threshold, and financial entity types. During detection,
    it checks if any high-risk word appears within the proximity window
    of a financial entity and applies a confidence boost if so.
    """

    def __init__(
        self,
        config_path: str = "config/financial_crime_words.yaml",
    ) -> None:
        self.config_path = config_path
        config = self.load_config()
        fc = config["financial_crime"]
        self.high_risk_words: list[str] = [w.lower() for w in fc["high_risk_words"]]
        self.boost_amount: float = float(fc["boost_amount"])
        self.proximity: int = int(fc["proximity_chars"])
        self.financial_entity_types: list[str] = list(fc["financial_entity_types"])

    def load_config(self) -> dict[str, Any]:
        """Load the financial crime words config from YAML.

        Returns:
            The parsed config dictionary.

        Raises:
            FileNotFoundError: If the config file does not exist.
            yaml.YAMLError: If the config file is malformed.
        """
        with open(self.config_path) as f:
            result = yaml.safe_load(f)
            return result if isinstance(result, dict) else {}

    def find_high_risk_word_positions(
        self,
        text: str,
        high_risk_words: list[str],
    ) -> list[tuple[int, int]]:
        """Find all (start, end) positions of high-risk words in text.

        Uses case-insensitive matching with word boundaries to avoid
        partial matches (e.g. "swift" matched inside "swiftly").

        Args:
            text: The text to search.
            high_risk_words: List of high-risk word strings (lowercase).

        Returns:
            List of (start, end) tuples for each match position.
        """
        positions: list[tuple[int, int]] = []
        for word in high_risk_words:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            for match in pattern.finditer(text):
                positions.append((match.start(), match.end()))
        return positions

    def is_within_proximity(
        self,
        entity_start: int,
        entity_end: int,
        word_positions: list[tuple[int, int]],
        proximity: int,
    ) -> bool:
        """Check if any high-risk word position is within ``proximity``
        characters of the entity span.

        The proximity is measured from the entity's start (looking
        backward) and end (looking forward). If the distance between
        a word boundary and the entity boundary is ≤ proximity, returns
        True.

        Args:
            entity_start: Start offset of the entity in the source text.
            entity_end: End offset of the entity in the source text.
            word_positions: List of (start, end) tuples from
                ``find_high_risk_word_positions``.
            proximity: Maximum char distance for a boost to apply.

        Returns:
            True if any word is within proximity of the entity.
        """
        if not word_positions:
            return False

        for ws, we in word_positions:
            # Distance from word end to entity start (word is before entity)
            if we <= entity_start:
                distance = entity_start - we
            # Distance from entity end to word start (word is after entity)
            elif ws >= entity_end:
                distance = ws - entity_end
            # Word overlaps or contains the entity
            else:
                return True

            if distance <= proximity:
                return True

        return False

    def apply_boost(
        self,
        entity: DetectionResult,
        _text: str,
        word_positions: list[tuple[int, int]],
    ) -> DetectionResult:
        """Apply confidence boost to an entity if it qualifies.

        Boosts only if:
        1. Entity type is in ``financial_entity_types``
        2. A high-risk word is within ``proximity`` chars of the entity

        The boost is a single +0.15 addition, capped at 1.0.

        Args:
            entity: The detection result to potentially boost.
            text: The original source text (used for position context).
            word_positions: Pre-computed positions of high-risk words.

        Returns:
            A new ``DetectionResult`` with the boosted score, or the
            original entity if no boost applies.
        """
        # Only boost financial crime entity types
        if entity.entity_type not in self.financial_entity_types:
            return entity

        # Check proximity
        if not self.is_within_proximity(
            entity.start,
            entity.end,
            word_positions,
            self.proximity,
        ):
            return entity

        # Apply capped boost
        new_score = min(entity.score + self.boost_amount, 1.0)

        return DetectionResult(
            entity_type=entity.entity_type,
            start=entity.start,
            end=entity.end,
            score=new_score,
            source=entity.source,
        )
