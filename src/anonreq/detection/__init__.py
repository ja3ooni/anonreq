"""Detection engine package.

Provides hybrid regex + NER PII detection via:
- ``RegexDetector`` — deterministic pattern matching
- ``PresidioClient`` — async HTTP client for Presidio Analyzer sidecar
- ``SpanArbiter`` — regex+NER merge with overlap resolution
- ``ExclusionList`` — exact-match and wildcard suppression

Phase 15 Financial Services Compliance:
- ``recognizers`` — MNPI recognizer bundle (ticker symbols, deal codenames,
  tenant restricted names)
"""

from anonreq.detection.exclusion_list import ExclusionList
from anonreq.detection.presidio_client import PresidioClient, PresidioError, PresidioTimeoutError
from anonreq.detection.regex_detector import RegexDetector
from anonreq.detection.regex_patterns import ENTITY_SPECIFICITY, PATTERNS, luhn_checksum
from anonreq.detection.span_arbiter import SpanArbiter

__all__ = [
    "ENTITY_SPECIFICITY",
    "PATTERNS",
    "ExclusionList",
    "PresidioClient",
    "PresidioError",
    "PresidioTimeoutError",
    "RegexDetector",
    "SpanArbiter",
    "luhn_checksum",
]
