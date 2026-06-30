"""Detection engine package.

Provides hybrid regex + NER PII detection via:
- ``RegexDetector`` — deterministic pattern matching
- ``PresidioClient`` — async HTTP client for Presidio Analyzer sidecar
- ``SpanArbiter`` — regex+NER merge with overlap resolution
- ``ExclusionList`` — exact-match and wildcard suppression
"""

from anonreq.detection.regex_detector import RegexDetector
from anonreq.detection.regex_patterns import PATTERNS, luhn_checksum, ENTITY_SPECIFICITY
from anonreq.detection.presidio_client import PresidioClient, PresidioTimeoutError, PresidioError
from anonreq.detection.exclusion_list import ExclusionList
from anonreq.detection.span_arbiter import SpanArbiter

__all__ = [
    "RegexDetector",
    "PATTERNS",
    "luhn_checksum",
    "ENTITY_SPECIFICITY",
    "PresidioClient",
    "PresidioTimeoutError",
    "PresidioError",
    "ExclusionList",
    "SpanArbiter",
]
