"""Compliance preset merge logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from anonreq.compliance.preset import CompliancePreset
from anonreq.locale.bundle import RecognizerTier


@dataclass(frozen=True)
class PresetMergeResult:
    """Effective detection requirements after applying presets."""

    merged_entity_types: dict[str, RecognizerTier]
    merged_thresholds: dict[str, float]
    merged_minimum_tiers: dict[str, list[RecognizerTier]]
    requires_checksum: list[str]
    source_presets: list[str]
    has_customer_overrides: bool = False
    disabled_entity_types: list[str] = field(default_factory=list)


def _tier_rank(tier: RecognizerTier) -> int:
    return {RecognizerTier.REGEX: 1, RecognizerTier.NER: 1, RecognizerTier.BOTH: 2}[tier]


def _normalize_base(base_config: dict[str, Any]) -> tuple[dict[str, RecognizerTier], dict[str, float], dict[str, list[RecognizerTier]]]:  # noqa: E501
    entity_types: dict[str, RecognizerTier] = {}
    thresholds: dict[str, float] = {}
    minimum_tiers: dict[str, list[RecognizerTier]] = {}
    for name, config in (base_config.get("entity_types") or {}).items():
        tier = config.get("tier", RecognizerTier.REGEX)
        tier = tier if isinstance(tier, RecognizerTier) else RecognizerTier(str(tier))
        entity_types[name] = tier
        thresholds[name] = float(config.get("confidence_threshold", config.get("threshold", 0.7)))
        minimum_tiers[name] = [tier]
    return entity_types, thresholds, minimum_tiers


def _merge_tiers(existing: list[RecognizerTier], incoming: list[RecognizerTier]) -> list[RecognizerTier]:  # noqa: E501
    tiers = {*(existing or []), *(incoming or [])}
    if RecognizerTier.BOTH in tiers or {RecognizerTier.REGEX, RecognizerTier.NER}.issubset(tiers):
        return [RecognizerTier.REGEX, RecognizerTier.NER]
    return sorted(tiers, key=lambda tier: tier.value)


def _apply_preset(
    preset: CompliancePreset,
    entity_types: dict[str, RecognizerTier],
    thresholds: dict[str, float],
    minimum_tiers: dict[str, list[RecognizerTier]],
    checksums: set[str],
) -> None:
    for entity_type in preset.mandatory_entity_types:
        entity_types.setdefault(entity_type, RecognizerTier.REGEX)
        thresholds[entity_type] = max(
            thresholds.get(entity_type, 0.0),
            preset.thresholds.get(entity_type, 0.7),
        )
    for entity_type, tiers in preset.minimum_tiers.items():
        minimum_tiers[entity_type] = _merge_tiers(minimum_tiers.get(entity_type, []), tiers)
        strongest = max(minimum_tiers[entity_type], key=_tier_rank)
        if _tier_rank(strongest) > _tier_rank(entity_types.get(entity_type, RecognizerTier.REGEX)):
            entity_types[entity_type] = strongest
    checksums.update(preset.requires_checksum)


def merge_presets(
    base_config: dict[str, Any],
    presets: list[CompliancePreset],
    overrides: dict[str, Any] | None = None,
) -> PresetMergeResult:
    """Merge base config, compliance presets, and non-weakening overrides."""

    entity_types, thresholds, minimum_tiers = _normalize_base(base_config)
    checksums: set[str] = set(base_config.get("requires_checksum") or [])
    disabled_entity_types = sorted(base_config.get("disabled_entity_types") or [])

    for preset in presets:
        _apply_preset(preset, entity_types, thresholds, minimum_tiers, checksums)

    if overrides:
        override_preset = CompliancePreset(
            id="customer_overrides",
            name="Customer Overrides",
            description="Customer overrides",
            jurisdictions=[],
            mandatory_entity_types=list((overrides.get("entity_types") or {}).keys()),
            thresholds={
                key: float(value.get("confidence_threshold", value.get("threshold", 0.0)))
                for key, value in (overrides.get("entity_types") or {}).items()
            },
            minimum_tiers={
                key: [RecognizerTier(str(value["tier"]))]
                for key, value in (overrides.get("entity_types") or {}).items()
                if "tier" in value
            },
            requires_checksum=list(overrides.get("requires_checksum") or []),
        )
        _apply_preset(override_preset, entity_types, thresholds, minimum_tiers, checksums)

    return PresetMergeResult(
        merged_entity_types=entity_types,
        merged_thresholds=thresholds,
        merged_minimum_tiers=minimum_tiers,
        requires_checksum=sorted(checksums),
        source_presets=[preset.id for preset in presets],
        has_customer_overrides=bool(overrides),
        disabled_entity_types=disabled_entity_types,
    )
