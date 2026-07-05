"""MITRE ATT&CK / ATLAS technique ID mapping loader and resolver.

Per D-013 through D-016:
- Maps security event_types to MITRE ATT&CK (Enterprise) and ATLAS
  technique IDs via ``config/mitre-mapping.yaml``
- Applied at the event normalizer stage before sink formatting
- Unknown event types receive ``TEMP:UNMAPPED`` fallback with warning log
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import yaml

logger = logging.getLogger("anonreq.soc.mitre")


@dataclass
class MappingEntry:
    """A single MITRE ATT&CK/ATLAS mapping entry.

    Attributes:
        event_type: The security event type identifier.
        mitre_id: MITRE ATT&CK (T-number) or ATLAS (AML-number) ID.
        framework: ``"ATT&CK"`` or ``"ATLAS"``.
        technique: Human-readable technique name.
    """

    event_type: str
    mitre_id: str
    framework: str
    technique: str


class MITREMapper:
    """MITRE technique ID resolver for security event types.

    Loads mapping from a YAML config file, validates entries, and
    provides lookup by event_type with ``TEMP:UNMAPPED`` fallback.

    Args:
        config_path: Path to the MITRE mapping YAML file.
            Defaults to ``"config/mitre-mapping.yaml"``.
    """

    def __init__(self, config_path: str = "config/mitre-mapping.yaml") -> None:
        self._config_path = config_path
        self._entries: dict[str, MappingEntry] = {}

        with open(config_path) as f:
            raw: dict[str, Any] = yaml.safe_load(f)

        if raw is None:
            return

        mappings = raw.get("event_type_mappings", {})
        for event_type, mapping in mappings.items():
            if not isinstance(mapping, dict):
                continue
            self._entries[event_type] = MappingEntry(
                event_type=event_type,
                mitre_id=mapping.get("mitre_id", "TEMP:UNMAPPED"),
                framework=mapping.get("framework", "ATT&CK"),
                technique=mapping.get("technique", ""),
            )

    def resolve(self, event_type: str) -> str:
        """Resolve an event_type to its MITRE technique ID.

        Args:
            event_type: The security event type to look up.

        Returns:
            MITRE technique ID string, or ``"TEMP:UNMAPPED"`` if the
            event_type has no mapping. A warning is logged on fallback.
        """
        entry = self._entries.get(event_type)
        if entry is None:
            logger.warning(
                "No MITRE mapping for event_type '%s'",
                event_type,
                extra={"event_type": event_type, "mitre_id": "TEMP:UNMAPPED"},
            )
            return "TEMP:UNMAPPED"
        return entry.mitre_id

    def get_entry(self, event_type: str) -> MappingEntry | None:
        """Return the full MappingEntry for an event_type, or None."""
        return self._entries.get(event_type)

    def validate(self) -> list[str]:
        """Validate all mapping entries have required fields.

        Returns:
            List of validation error messages. Empty list if all valid.
        """
        errors: list[str] = []
        for event_type, entry in self._entries.items():
            if not entry.mitre_id or entry.mitre_id == "TEMP:UNMAPPED":
                errors.append(
                    f"Entry '{event_type}': missing or invalid mitre_id"
                )
            if not entry.framework:
                errors.append(f"Entry '{event_type}': missing framework")
            if not entry.technique:
                errors.append(f"Entry '{event_type}': missing technique")
        return errors

    @property
    def entries(self) -> dict[str, MappingEntry]:
        """Return all loaded mapping entries."""
        return dict(self._entries)


def load_mitre_mapping(config_path: str = "config/mitre-mapping.yaml") -> MITREMapper:
    """Convenience factory for creating a MITREMapper instance.

    Args:
        config_path: Path to the MITRE mapping YAML file.

    Returns:
        A configured MITREMapper instance.
    """
    return MITREMapper(config_path)
