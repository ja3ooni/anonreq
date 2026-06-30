"""Detection engine data models.

Per D-29 through D-33:
- TextNode represents one extracted text fragment from the request body
- DetectionResult captures a single entity detection (regex or NER)

Per D-31, the TextNode model is reused across classification, detection,
tokenization, and restoration stages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


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
        score: Confidence score (0.0–1.0). Regex detections always have
            score 1.0; NER detections have the Presidio confidence score.
        source: Whether this detection came from a regex pattern or the
            NER (Presidio) engine (D-39).
    """

    entity_type: str
    start: int
    end: int
    score: float
    source: Literal["regex", "ner"]
