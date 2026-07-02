"""Checksum validator registry and detection filtering helpers."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any


class ChecksumValidator(ABC):
    """Base class for locale-specific national ID checksum validators."""

    @abstractmethod
    def validate(self, value: str) -> bool:
        """Return True when ``value`` passes this checksum algorithm."""


class ChecksumValidatorRegistry:
    """Maps entity types to checksum validators."""

    def __init__(self) -> None:
        self._validators: dict[str, ChecksumValidator] = {}

    def register(self, entity_type: str, validator: ChecksumValidator) -> None:
        self._validators[entity_type.upper()] = validator

    def get(self, entity_type: str) -> ChecksumValidator | None:
        return self._validators.get(entity_type.upper())

    def validate(self, entity_type: str, value: str) -> bool:
        validator = self.get(entity_type)
        if validator is None:
            return True
        return validator.validate(value)

    def registered_entity_types(self) -> set[str]:
        return set(self._validators)


def _detection_value(detection: dict[str, Any], source_text: str | None = None) -> str:
    value = detection.get("value")
    if value is not None:
        return str(value)
    if source_text is None:
        return ""
    return source_text[int(detection["start"]): int(detection["end"])]


def validate_detection(
    detection: dict[str, Any],
    registry: ChecksumValidatorRegistry,
    source_text: str | None = None,
) -> dict[str, Any] | None:
    """Drop checksum-invalid detections, pass through all others."""

    entity_type = str(detection.get("entity_type", ""))
    validator = registry.get(entity_type)
    if validator is None:
        return detection

    value = _detection_value(detection, source_text)
    if validator.validate(value):
        return detection
    return None


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value)
