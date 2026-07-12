"""Detection engine data models.

Per D-29 through D-33:
- TextNode represents one extracted text fragment from the request body
- DetectionResult captures a single entity detection (regex or NER)

Per D-31, the TextNode model is reused across classification, detection,
tokenization, and restoration stages.

Phase 15 Financial Services Compliance:
- MNPI entity types (MNPI_TICKER, MNPI_DEAL, MNPI_RESTRICTED_NAME)
- MNPI_POLICY_ACTION literal type for 4 handling policies per D-003
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# MNPI (Material Non-Public Information) entity types (Phase 15, D-001, D-003)
MNPI_ENTITY_TYPES: set[str] = {
    "MNPI_TICKER",
    "MNPI_DEAL",
    "MNPI_RESTRICTED_NAME",
}

# MNPI handling policy actions per D-003:
# - anonymize: tokenize and forward (default)
# - flag: tokenize, forward, and flag for review
# - block: block the request entirely
# - quarantine: block and capture payload for review
MNPI_POLICY_ACTION = Literal["anonymize", "flag", "block", "quarantine"]


@dataclass
class TextNode:
    """A single text fragment extracted from a request body.

    Attributes:
        path: JSON path to the text location (e.g. ``"messages[0].content"``).
        role: The message role (``"system"``, ``"user"``, ``"assistant"``,
            ``"tool"``, ``"function"``).
        value: The extracted text content.
    """

    path: str
    role: str
    value: str


@dataclass
class DetectionResult:
    """A single entity detection from regex or NER analysis.

    Attributes:
        entity_type: The type of detected entity (e.g. ``"EMAIL_ADDRESS"``,
            ``"PERSON"``).
        start: Character offset where the entity starts in the source text.
        end: Character offset where the entity ends in the source text.
        score: Confidence score (0.0-1.0). Regex detections always have
            score 1.0; NER detections have the Presidio confidence score.
        source: Whether this detection came from a regex pattern or the
            NER (Presidio) engine (D-39).
    """

    entity_type: str
    start: int
    end: int
    score: float
    source: Literal["regex", "ner"]
