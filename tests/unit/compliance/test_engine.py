from __future__ import annotations

from anonreq.compliance.engine import PresetEngine


def test_engine_loads_six_presets() -> None:
    engine = PresetEngine("config/compliance")
    assert set(engine.list_presets()) == {
        "gdpr",
        "lgpd",
        "pdpa",
        "pipeda",
        "popia",
        "privacy_act",
    }


def test_engine_get_preset() -> None:
    engine = PresetEngine("config/compliance")
    assert engine.get_preset("gdpr").name == "GDPR"
    assert engine.get_preset("missing") is None
