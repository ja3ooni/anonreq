"""Compliance preset domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from anonreq.locale.bundle import RecognizerTier


@dataclass(frozen=True)
class CompliancePreset:
    """Jurisdiction-specific detection requirements."""

    id: str
    name: str
    description: str
    jurisdictions: list[str]
    mandatory_entity_types: list[str]
    thresholds: dict[str, float] = field(default_factory=dict)
    minimum_tiers: dict[str, list[RecognizerTier]] = field(default_factory=dict)
    requires_checksum: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompliancePreset:
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data.get("description", "")),
            jurisdictions=list(data.get("jurisdictions") or []),
            mandatory_entity_types=list(data.get("mandatory_entity_types") or []),
            thresholds={k: float(v) for k, v in (data.get("thresholds") or {}).items()},
            minimum_tiers={
                key: [RecognizerTier(str(tier)) for tier in tiers]
                for key, tiers in (data.get("minimum_tiers") or {}).items()
            },
            requires_checksum=list(data.get("requires_checksum") or []),
            metadata=dict(data.get("metadata") or {}),
        )
