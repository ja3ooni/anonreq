from __future__ import annotations

from anonreq.compliance.merge import merge_presets
from anonreq.compliance.preset import CompliancePreset


def base_config() -> dict:
    return {
        "entity_types": {
            "EMAIL_ADDRESS": {"tier": "REGEX", "confidence_threshold": 0.9},
            "PERSON": {"tier": "NER", "confidence_threshold": 0.7},
        }
    }


def test_merge_single_preset_adds_mandatory_types_and_thresholds() -> None:
    preset = CompliancePreset(
        id="x",
        name="X",
        description="",
        jurisdictions=[],
        mandatory_entity_types=["PHONE_NUMBER"],
        thresholds={"PHONE_NUMBER": 0.85},
    )
    result = merge_presets(base_config(), [preset])
    assert "PHONE_NUMBER" in result.merged_entity_types
    assert result.merged_thresholds["PHONE_NUMBER"] == 0.85


def test_merge_never_lowers_base_threshold() -> None:
    preset = CompliancePreset(
        id="x",
        name="X",
        description="",
        jurisdictions=[],
        mandatory_entity_types=["EMAIL_ADDRESS"],
        thresholds={"EMAIL_ADDRESS": 0.2},
    )
    result = merge_presets(base_config(), [preset])
    assert result.merged_thresholds["EMAIL_ADDRESS"] == 0.9


def test_multi_preset_merge_unions_types_and_checksum() -> None:
    first = CompliancePreset("a", "A", "", [], ["CPF"], {"CPF": 0.8}, requires_checksum=["CPF"])
    second = CompliancePreset("b", "B", "", [], ["CNPJ"], {"CNPJ": 0.9}, requires_checksum=["CNPJ"])
    result = merge_presets(base_config(), [first, second])
    assert {"CPF", "CNPJ"}.issubset(result.merged_entity_types)
    assert result.requires_checksum == ["CNPJ", "CPF"]


def test_customer_overrides_cannot_weaken() -> None:
    result = merge_presets(
        base_config(),
        [],
        overrides={"entity_types": {"EMAIL_ADDRESS": {"tier": "REGEX", "confidence_threshold": 0.1}}},  # noqa: E501
    )
    assert result.merged_thresholds["EMAIL_ADDRESS"] == 0.9
