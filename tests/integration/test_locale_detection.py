from __future__ import annotations

import pytest

from anonreq.locale.checksum import ChecksumValidatorRegistry
from anonreq.locale.merger import RecognizerMerger
from anonreq.locale.negotiator import LocaleNegotiator
from anonreq.locale.registry import LocaleRegistry


@pytest.fixture
def locale_stack():
    checksum = ChecksumValidatorRegistry()
    registry = LocaleRegistry("config/locales", checksum_registry=checksum)
    return registry, LocaleNegotiator(registry), RecognizerMerger(registry.get("en")), checksum


def test_german_locale_detection_config(locale_stack) -> None:
    registry, negotiator, merger, _ = locale_stack
    bundles, _ = negotiator.negotiate("de-DE")
    merged = merger.merge(bundles)
    assert "TAX_ID_DE" in merged.entity_configs
    assert "PERSON" in merged.entity_configs
    assert merged.has_universal


def test_multi_locale_detection_config(locale_stack) -> None:
    _, negotiator, merger, _ = locale_stack
    bundles, _ = negotiator.negotiate("de-DE, fr-FR")
    merged = merger.merge(bundles)
    assert "TAX_ID_DE" in merged.entity_configs
    assert "NIR" in merged.entity_configs
    assert "EMAIL_ADDRESS" in merged.entity_configs


def test_no_header_uses_universal(locale_stack) -> None:
    _, negotiator, merger, _ = locale_stack
    bundles, result = negotiator.negotiate(None)
    merged = merger.merge(bundles)
    assert result.was_fallback
    assert merged.source_locales == ["en"]


def test_checksum_integration_registry(locale_stack) -> None:
    _, _, _, checksum = locale_stack
    assert checksum.validate("CPF", "529.982.247-25")
    assert not checksum.validate("CPF", "529.982.247-26")
