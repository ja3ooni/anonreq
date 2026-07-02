from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from anonreq.locale.bundle import EntityTypeConfig, LocaleBundle, RecognizerTier


LOCALES = ["en", "de-DE", "fr-FR", "nl-NL", "es", "it-IT", "ar", "pt-BR"]


def test_all_locale_yaml_files_parse() -> None:
    for locale in LOCALES:
        with open(Path("config/locales") / f"{locale}.yaml") as f:
            bundle = LocaleBundle.from_dict(yaml.safe_load(f))
        assert bundle.code == locale
        assert bundle.entity_types


def test_entity_type_config_round_trip() -> None:
    config = EntityTypeConfig(
        name="EMAIL_ADDRESS",
        tier=RecognizerTier.REGEX,
        confidence_threshold=0.9,
        patterns=[r"\S+@\S+"],
    )
    restored = EntityTypeConfig.from_dict(config.to_dict())
    assert restored == config


def test_recognizer_tier_validation_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        EntityTypeConfig.from_dict({"name": "X", "tier": "UNKNOWN"})
