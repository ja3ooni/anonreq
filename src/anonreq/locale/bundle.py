"""Locale recognizer bundle domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RecognizerTier(StrEnum):
    """Recognizer execution tier for an entity type."""

    REGEX = "REGEX"
    NER = "NER"
    BOTH = "BOTH"


@dataclass(frozen=True)
class EntityTypeConfig:
    """Entity recognition configuration for one entity type."""

    name: str
    tier: RecognizerTier
    confidence_threshold: float = 0.7
    patterns: list[str] = field(default_factory=list)
    presidio_entities: list[str] = field(default_factory=list)
    reversible: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntityTypeConfig:
        return cls(
            name=str(data["name"]),
            tier=RecognizerTier(str(data["tier"])),
            confidence_threshold=float(data.get("confidence_threshold", 0.7)),
            patterns=list(data.get("patterns") or []),
            presidio_entities=list(data.get("presidio_entities") or []),
            reversible=bool(data.get("reversible", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tier": self.tier.value,
            "confidence_threshold": self.confidence_threshold,
            "patterns": list(self.patterns),
            "presidio_entities": list(self.presidio_entities),
            "reversible": self.reversible,
        }


@dataclass(frozen=True)
class ChecksumConfig:
    """Checksum validator metadata for a locale bundle."""

    algorithm: str
    validator_id: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChecksumConfig:
        return cls(
            algorithm=str(data["algorithm"]),
            validator_id=str(data["validator_id"]),
        )


@dataclass(frozen=True)
class LocaleMetadata:
    """Human-readable locale bundle metadata."""

    name: str
    version: int
    maintainer: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LocaleMetadata:
        return cls(
            name=str(data["name"]),
            version=int(data.get("version", 1)),
            maintainer=str(data.get("maintainer", "AnonReq Core")),
        )


@dataclass(frozen=True)
class LocaleBundle:
    """A drop-in locale recognizer bundle loaded from YAML."""

    code: str
    entity_types: list[EntityTypeConfig]
    checksum: ChecksumConfig | None = None
    checksums: list[ChecksumConfig] = field(default_factory=list)
    metadata: LocaleMetadata | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LocaleBundle:
        checksum_raw = data.get("checksum")
        checksums_raw = data.get("checksums") or []
        checksums = [ChecksumConfig.from_dict(item) for item in checksums_raw]
        checksum = ChecksumConfig.from_dict(checksum_raw) if checksum_raw else None
        if checksum is not None and not checksums:
            checksums = [checksum]
        elif checksum is None and checksums:
            checksum = checksums[0]
        metadata = data.get("metadata")
        return cls(
            code=str(data["code"]),
            entity_types=[
                EntityTypeConfig.from_dict(item)
                for item in data.get("entity_types", [])
            ],
            checksum=checksum,
            checksums=checksums,
            metadata=LocaleMetadata.from_dict(metadata) if metadata else None,
        )

    @property
    def all_checksums(self) -> list[ChecksumConfig]:
        if self.checksums:
            return list(self.checksums)
        if self.checksum is not None:
            return [self.checksum]
        return []

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "code": self.code,
            "entity_types": [entity.to_dict() for entity in self.entity_types],
        }
        if self.checksum is not None:
            data["checksum"] = {
                "algorithm": self.checksum.algorithm,
                "validator_id": self.checksum.validator_id,
            }
        if self.checksums:
            data["checksums"] = [
                {"algorithm": item.algorithm, "validator_id": item.validator_id}
                for item in self.checksums
            ]
        if self.metadata is not None:
            data["metadata"] = {
                "name": self.metadata.name,
                "version": self.metadata.version,
                "maintainer": self.metadata.maintainer,
            }
        return data
