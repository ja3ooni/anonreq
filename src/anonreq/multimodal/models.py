from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ContentType(str, Enum):
    TEXT_PLAIN = "text/plain"
    APPLICATION_JSON = "application/json"
    MULTIPART_FORM_DATA = "multipart/form-data"
    UNKNOWN = "unknown"


class UnifiedDetectionResult(BaseModel):
    content_type: ContentType
    entities: list[dict] = Field(default_factory=list)
    risk_score: float = 0.0
    classification: str = "Internal"
    analyzer_metadata: dict = Field(default_factory=dict)


class AnalyzerResult(BaseModel):
    source_analyzer: str
    content_type: ContentType
    detection_result: UnifiedDetectionResult
    should_process: bool = True
    action: str = "ANONYMIZE"
