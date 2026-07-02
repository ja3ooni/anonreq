from __future__ import annotations

import pytest

from anonreq.compliance.engine import PresetEngine
from anonreq.routes.compliance import list_compliance_presets


def test_startup_validation_passes_with_merged_preset_config() -> None:
    engine = PresetEngine("config/compliance")
    base = {"entity_types": {"PERSON": {"tier": "NER", "confidence_threshold": 0.7}}}
    assert engine.validate_startup(["gdpr"], base) == []


def test_startup_validation_hard_fails_on_violation() -> None:
    engine = PresetEngine("config/compliance")
    with pytest.raises(SystemExit):
        engine.assert_startup_checks(
            ["gdpr"],
            {"entity_types": {}, "disabled_entity_types": ["PERSON"]},
        )


def test_compliance_route_function_importable() -> None:
    assert list_compliance_presets is not None
