from __future__ import annotations

from anonreq.locale.bundle import EntityTypeConfig, LocaleBundle, RecognizerTier
from anonreq.locale.merger import RecognizerMerger
from anonreq.locale.registry import LocaleRegistry


def test_merge_universal_and_german_highest_confidence_wins() -> None:
    universal = LocaleBundle(
        code="en",
        entity_types=[
            EntityTypeConfig("PERSON", RecognizerTier.NER, 0.7),
            EntityTypeConfig("EMAIL_ADDRESS", RecognizerTier.REGEX, 0.9),
        ],
    )
    german = LocaleBundle(
        code="de-DE",
        entity_types=[
            EntityTypeConfig("PERSON", RecognizerTier.NER, 0.8),
            EntityTypeConfig("TAX_ID_DE", RecognizerTier.REGEX, 0.85),
        ],
    )

    merged = RecognizerMerger(universal).merge([german])
    assert merged.entity_configs["PERSON"].confidence_threshold == 0.8
    assert "EMAIL_ADDRESS" in merged.entity_configs
    assert "TAX_ID_DE" in merged.entity_configs


def test_merge_empty_locale_list_is_universal_only() -> None:
    registry = LocaleRegistry("config/locales")
    merged = RecognizerMerger(registry.get("en")).merge([])
    assert merged.source_locales == ["en"]
    assert "EMAIL_ADDRESS" in merged.entity_configs


def test_multi_locale_merge_is_order_independent() -> None:
    registry = LocaleRegistry("config/locales")
    merger = RecognizerMerger(registry.get("en"))
    de = registry.get("de-DE")
    fr = registry.get("fr-FR")

    first = merger.merge([de, fr])
    second = merger.merge([fr, de])
    assert first.entity_configs == second.entity_configs
    assert first.source_locales == second.source_locales
