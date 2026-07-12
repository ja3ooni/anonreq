"""SOC Integration Service — AI Security Event Pipeline.

Provides:
- ``NormalizedEvent``: Canonical event shape consumed by all SIEM sinks
- ``SeverityLevel``: Enum for event severity classification
- ``RawSecurityEvent``: Source event model for detection engine events
- ``SOCNormalizer``: Event normalizer that strips content and enriches metadata
- ``MITREMapper``: MITRE ATT&CK/ATLAS technique ID resolver
"""

from anonreq.soc.event import NormalizedEvent, RawSecurityEvent, SeverityLevel
from anonreq.soc.mitre import MappingEntry, MITREMapper, load_mitre_mapping
from anonreq.soc.normalizer import SOCNormalizer

__all__ = [
    "MITREMapper",
    "MappingEntry",
    "NormalizedEvent",
    "RawSecurityEvent",
    "SOCNormalizer",
    "SeverityLevel",
    "load_mitre_mapping",
]
