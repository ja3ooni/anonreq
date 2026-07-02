from __future__ import annotations

from anonreq.compliance.preset import CompliancePreset
from anonreq.compliance.validation import validate_effective_config
from anonreq.locale.bundle import RecognizerTier


def test_validation_passes_clean_config() -> None:
    preset = CompliancePreset("x", "X", "", [], ["PERSON"], {"PERSON": 0.7})
    violations = validate_effective_config(
        [preset],
        {"entity_types": {"PERSON": {"tier": "NER", "confidence_threshold": 0.8}}},
    )
    assert violations == []


def test_validation_collects_missing_type_and_low_threshold() -> None:
    preset = CompliancePreset(
        "x",
        "X",
        "",
        [],
        ["PERSON", "EMAIL_ADDRESS"],
        {"PERSON": 0.9},
    )
    violations = validate_effective_config(
        [preset],
        {"entity_types": {"PERSON": {"tier": "NER", "confidence_threshold": 0.5}}},
    )
    assert {v.violation_type for v in violations} == {"low_threshold", "missing_type"}


def test_validation_detects_missing_tier_and_checksum() -> None:
    preset = CompliancePreset(
        "x",
        "X",
        "",
        [],
        ["CPF"],
        minimum_tiers={"CPF": [RecognizerTier.REGEX, RecognizerTier.NER]},
        requires_checksum=["CPF"],
    )
    violations = validate_effective_config(
        [preset],
        {"entity_types": {"CPF": {"tier": "REGEX", "confidence_threshold": 0.9}}},
    )
    assert {v.violation_type for v in violations} == {"missing_tier", "missing_checksum"}
