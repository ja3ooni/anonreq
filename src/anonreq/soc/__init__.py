"""SOC Integration Service — AI Security Event Pipeline.

Provides:
- ``NormalizedEvent``: Canonical event shape consumed by all SIEM sinks
- ``SeverityLevel``: Enum for event severity classification
- ``RawSecurityEvent``: Source event model for detection engine events
- ``SOCNormalizer``: Event normalizer that strips content and enriches metadata
- ``MITREMapper``: MITRE ATT&CK/ATLAS technique ID resolver
"""

"""SOC Integration Service — AI Security Event Pipeline."""

from anonreq.soc.event import NormalizedEvent, SeverityLevel, RawSecurityEvent
from anonreq.soc.mitre import MITREMapper, MappingEntry, load_mitre_mapping

__all__ = [
    "NormalizedEvent",
    "SeverityLevel",
    "RawSecurityEvent",
    "MITREMapper",
    "MappingEntry",
    "load_mitre_mapping",
]
