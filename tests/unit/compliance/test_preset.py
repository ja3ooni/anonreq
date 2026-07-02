from __future__ import annotations

import pytest

from anonreq.compliance.preset import CompliancePreset
from anonreq.locale.bundle import RecognizerTier


def test_compliance_preset_from_dict() -> None:
    preset = CompliancePreset.from_dict({
        "id": "test",
        "name": "Test",
        "description": "desc",
        "jurisdictions": ["EU"],
        "mandatory_entity_types": ["PERSON"],
        "thresholds": {"PERSON": 0.8},
        "minimum_tiers": {"PERSON": ["NER"]},
    })
    assert preset.id == "test"
    assert preset.minimum_tiers["PERSON"] == [RecognizerTier.NER]


def test_compliance_preset_rejects_missing_required_fields() -> None:
    with pytest.raises(KeyError):
        CompliancePreset.from_dict({"id": "broken"})
