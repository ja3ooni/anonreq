"""Startup validation for compliance preset requirements."""

from __future__ import annotations

from dataclasses import dataclass

from anonreq.compliance.merge import PresetMergeResult
from anonreq.compliance.preset import CompliancePreset
from anonreq.locale.bundle import RecognizerTier


@dataclass(frozen=True)
class ComplianceViolation:
    """A single compliance startup validation failure."""

    preset_id: str
    entity_type: str
    violation_type: str
    message: str


def _tiers_for(effective_config: dict | PresetMergeResult, entity_type: str) -> list[RecognizerTier]:
    if isinstance(effective_config, PresetMergeResult):
        return effective_config.merged_minimum_tiers.get(entity_type, [])
    raw = (effective_config.get("entity_types") or {}).get(entity_type, {})
    if not raw:
        return []
    tier = raw.get("tier", RecognizerTier.REGEX)
    return [tier if isinstance(tier, RecognizerTier) else RecognizerTier(str(tier))]


def _threshold_for(effective_config: dict | PresetMergeResult, entity_type: str) -> float:
    if isinstance(effective_config, PresetMergeResult):
        return effective_config.merged_thresholds.get(entity_type, 0.0)
    raw = (effective_config.get("entity_types") or {}).get(entity_type, {})
    return float(raw.get("confidence_threshold", raw.get("threshold", 0.0)))


def _has_entity(effective_config: dict | PresetMergeResult, entity_type: str) -> bool:
    if isinstance(effective_config, PresetMergeResult):
        if entity_type in effective_config.disabled_entity_types:
            return False
        return entity_type in effective_config.merged_entity_types
    if entity_type in (effective_config.get("disabled_entity_types") or []):
        return False
    return entity_type in (effective_config.get("entity_types") or {})


def _has_checksum(effective_config: dict | PresetMergeResult, entity_type: str) -> bool:
    if isinstance(effective_config, PresetMergeResult):
        return entity_type in effective_config.requires_checksum
    return entity_type in (effective_config.get("requires_checksum") or [])


def validate_effective_config(
    active_presets: list[CompliancePreset],
    effective_config: dict | PresetMergeResult,
) -> list[ComplianceViolation]:
    """Collect all compliance validation violations."""

    violations: list[ComplianceViolation] = []
    for preset in active_presets:
        for entity_type in preset.mandatory_entity_types:
            if not _has_entity(effective_config, entity_type):
                violations.append(ComplianceViolation(
                    preset.id,
                    entity_type,
                    "missing_type",
                    f"{preset.id} requires {entity_type}",
                ))
                continue

            required_threshold = preset.thresholds.get(entity_type)
            if required_threshold is not None and _threshold_for(effective_config, entity_type) < required_threshold:
                violations.append(ComplianceViolation(
                    preset.id,
                    entity_type,
                    "low_threshold",
                    f"{entity_type} threshold below {required_threshold}",
                ))

            required_tiers = set(preset.minimum_tiers.get(entity_type, []))
            actual_tiers = set(_tiers_for(effective_config, entity_type))
            if required_tiers and not required_tiers.issubset(actual_tiers):
                violations.append(ComplianceViolation(
                    preset.id,
                    entity_type,
                    "missing_tier",
                    f"{entity_type} missing required tiers",
                ))

            if entity_type in preset.requires_checksum and not _has_checksum(effective_config, entity_type):
                violations.append(ComplianceViolation(
                    preset.id,
                    entity_type,
                    "missing_checksum",
                    f"{entity_type} requires checksum validation",
                ))

    return violations
