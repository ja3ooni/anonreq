from __future__ import annotations

import pytest

from anonreq.locale.negotiator import LocaleNegotiationError, LocaleNegotiator
from anonreq.locale.registry import LocaleRegistry


@pytest.fixture
def negotiator() -> LocaleNegotiator:
    return LocaleNegotiator(LocaleRegistry("config/locales"))


def test_parse_single_locale(negotiator: LocaleNegotiator) -> None:
    result = negotiator.parse_header("de-DE")
    assert result.locale_codes == ["de-DE"]
    assert result.had_header


def test_parse_multi_locale_with_whitespace(negotiator: LocaleNegotiator) -> None:
    result = negotiator.parse_header(" de-DE , fr-FR, es ")
    assert result.locale_codes == ["de-DE", "fr-FR", "es"]


def test_no_header_resolves_universal(negotiator: LocaleNegotiator) -> None:
    bundles, result = negotiator.negotiate(None)
    assert [bundle.code for bundle in bundles] == ["en"]
    assert result.was_fallback


def test_unknown_single_locale_errors(negotiator: LocaleNegotiator) -> None:
    with pytest.raises(LocaleNegotiationError) as exc:
        negotiator.negotiate("zz-ZZ")
    assert exc.value.status_code == 400
    assert "de-DE" in exc.value.supported_locales


def test_unknown_in_multi_locale_is_dropped(negotiator: LocaleNegotiator) -> None:
    bundles, result = negotiator.negotiate("de-DE, zz-ZZ")
    assert [bundle.code for bundle in bundles] == ["de-DE"]
    assert "zz-ZZ" in result.dropped_codes


def test_max_ten_locales_enforced(negotiator: LocaleNegotiator) -> None:
    result = negotiator.parse_header(",".join(f"en-{i}" for i in range(12)))
    assert len(result.locale_codes) == 10
    assert len(result.dropped_codes) == 2


def test_bg_header_resolves_to_bg_bundle_once() -> None:
    negotiator = LocaleNegotiator(LocaleRegistry("config/locales"))
    for header in ("bg", "bg-BG", "bg, bg-BG"):
        bundles, parsed = negotiator.negotiate(header)
        assert [bundle.code for bundle in bundles] == ["bg-BG"], header
        assert parsed.dropped_codes == []


@pytest.mark.parametrize(
    ("header", "expected"),
    [("de", "de-DE"), ("DE", "de-DE"), ("bg", "bg-BG"), ("de, bg", "de-DE,bg-BG")],
)
def test_bare_language_header_maps_to_regional_bundle(header: str, expected: str) -> None:
    """Pin the bare-language mapping: ``de`` must keep meaning de-DE."""
    negotiator = LocaleNegotiator(LocaleRegistry("config/locales"))
    bundles, parsed = negotiator.negotiate(header)
    assert ",".join(bundle.code for bundle in bundles) == expected
    assert parsed.dropped_codes == []
    assert not parsed.was_fallback


@pytest.mark.parametrize("header", ["de-AT", "de-CH", "pt-PT"])
def test_unbundled_regions_are_not_mapped_to_a_sibling(header: str) -> None:
    negotiator = LocaleNegotiator(LocaleRegistry("config/locales"))
    with pytest.raises(LocaleNegotiationError):
        negotiator.negotiate(header)
