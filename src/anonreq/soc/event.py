"""SOC event data types — canonical event shape for all SIEM sinks.

Per D-011 through D-012 and 20-ARCHITECTURE.md:
- ``NormalizedEvent``: Canonical event with 8 required fields + metadata dict
- ``SeverityLevel``: Five severity tiers (informational → critical)
- ``RawSecurityEvent``: Source event model from detection engines

No raw prompt content is ever present in NormalizedEvent — content fields
are stripped before normalization (D-012).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class SeverityLevel(StrEnum):
    """Severity classification for security events.

    Ordered from least to most severe for comparison:
        informational < low < medium < high < critical
    """

    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def __lt__(self, other: SeverityLevel) -> bool:  # type: ignore[override]
        levels = list(SeverityLevel)
        return levels.index(self) < levels.index(other)

    def __le__(self, other: SeverityLevel) -> bool:  # type: ignore[override]
        levels = list(SeverityLevel)
        return levels.index(self) <= levels.index(other)


@dataclass
class NormalizedEvent:
    """Canonical normalized security event for SIEM sink consumption.

    All 8 required fields per D-011 are present. The ``metadata`` dict
    carries structured context safe for forwarding (no raw prompt content).

    Attributes:
        severity: Event severity classification.
        event_type: Machine-readable event type identifier.
        tenant_id: Tenant identifier.
        session_id: Request/session identifier.
        timestamp: ISO 8601 UTC timestamp string.
        gateway_version: AnonReq gateway version at event time.
        appliance_instance_id: Unique appliance instance identifier.
        mitre_technique_id: MITRE ATT&CK/ATLAS technique ID.
        metadata: Additional structured metadata (no raw content).
    """

    severity: SeverityLevel
    event_type: str
    tenant_id: str
    session_id: str
    timestamp: str
    gateway_version: str
    appliance_instance_id: str
    mitre_technique_id: str = "TEMP:UNMAPPED"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for sink formatting.

        Returns:
            Dict with all fields including serialised severity value.
        """
        return {
            "severity": self.severity.value,
            "event_type": self.event_type,
            "tenant_id": self.tenant_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "gateway_version": self.gateway_version,
            "appliance_instance_id": self.appliance_instance_id,
            "mitre_technique_id": self.mitre_technique_id,
            "metadata": self.metadata,
        }


@dataclass
class RawSecurityEvent:
    """Source security event from a detection engine before normalization.

    Detection engines (Phases 10, 13, 12, 8, 17, 18) publish these to the
    event bus. The SOC normalizer consumes them, strips raw content fields,
    applies MITRE mapping, and produces ``NormalizedEvent`` instances.

    Attributes:
        source_engine: Name of the originating detection engine
            (e.g. ``"firewall"``, ``"dlp"``, ``"classification"``).
        event_type: Raw event type from the source engine.
        tenant_id: Tenant identifier.
        session_id: Request/session identifier.
        content: Full event payload dict (may include raw content fields
            that will be stripped by the normalizer).
        timestamp: ISO 8601 UTC timestamp string (defaults to now if empty).
    """

    source_engine: str
    event_type: str
    tenant_id: str
    session_id: str
    content: dict[str, Any]
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()
