"""DLP data models (Plan 13-01)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DLPCategory(str, Enum):
    PII = "PII"
    FINANCIAL = "Financial"
    HEALTH = "Health"
    SOURCE_CODE = "Source Code"
    CREDENTIALS = "Credentials"
    LEGAL = "Legal"
    EXPORT_CONTROLLED = "Export Controlled"
    INTELLECTUAL_PROPERTY = "Intellectual Property"


class DLPAction(str, Enum):
    ALLOW = "allow"
    ANONYMIZE = "anonymize"
    REDACT = "redact"
    QUARANTINE = "quarantine"
    BLOCK = "block"


@dataclass
class DLPDetection:
    category: DLPCategory
    action: DLPAction
    match_text: str         # The matched content (for context, not stored)
    confidence: float       # 0.0 to 1.0
    start: int
    end: int
    pattern_id: str         # Which pattern triggered
    is_custom_category: bool = False


@dataclass
class DLPResult:
    tenant_id: str
    detections: list[DLPDetection]
    max_action: DLPAction   # Most restrictive action across all detections
    is_blocked: bool = False
    is_quarantined: bool = False
