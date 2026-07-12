"""Property-based tests for locale detection invariants.

Tier 3 tests from 04-TEST-PLAN:

- LOCALE-01: Same input + same locale header = same detection output (AG-13
  determinism)
- LOCALE-03: Adding a locale never reduces detection coverage — union property
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from anonreq.locale.merger import RecognizerMerger
from anonreq.locale.negotiator import LocaleNegotiator
from anonreq.locale.registry import LocaleRegistry

# Sorted list of all 8 MVP locale codes — used as Hypothesis sampling domain
LOCALE_CODES = ["ar", "de-DE", "en", "es", "fr-FR", "it-IT", "nl-NL", "pt-BR"]


# ---------------------------------------------------------------------------
# Shared fixture helpers (lightweight — no conftest dependency)
# ---------------------------------------------------------------------------

def _full_registry() -> LocaleRegistry:
    """Return a real LocaleRegistry for property testing."""
    return LocaleRegistry("config/locales")


def _negotiator() -> LocaleNegotiator:
    return LocaleNegotiator(_full_registry())


def _merger() -> RecognizerMerger:
    registry = _full_registry()
    universal = registry.get("en")
    assert universal is not None, "en bundle must exist"
    return RecognizerMerger(universal)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

locale_code_st = st.sampled_from([c for c in LOCALE_CODES if c != "en"])

def _negotiate_and_merge(header: str | None):
    """Helper: negotiate + merge for a given header value."""
    neg = _negotiator()
    merger = _merger()
    bundles, _ = neg.negotiate(header)
    return merger.merge(bundles)


# ---------------------------------------------------------------------------
# LOCALE-01: AG-13 Determinism
# ---------------------------------------------------------------------------

@given(st.sampled_from(LOCALE_CODES))
@settings(max_examples=50)
def test_locale_determinism_same_result_twice(locale_code: str) -> None:
    """Same locale header produces identical MergedRecognizerSet.

    AG-13 requires that for the same input + same locale header, the
    detection config (entity configs, source locales) is byte-identical
    across repeated calls.
    """
    registry = _full_registry()

    # First call
    negotiator_a = LocaleNegotiator(registry)
    merger_a = RecognizerMerger(registry.get("en"))  # type: ignore[arg-type]
    bundles_a, _ = negotiator_a.negotiate(locale_code)
    result_a = merger_a.merge(bundles_a)

    # Second call — fresh instances, same inputs
    negotiator_b = LocaleNegotiator(registry)
    merger_b = RecognizerMerger(registry.get("en"))  # type: ignore[arg-type]
    bundles_b, _ = negotiator_b.negotiate(locale_code)
    result_b = merger_b.merge(bundles_b)

    assert result_a.entity_configs == result_b.entity_configs
    assert result_a.source_locales == result_b.source_locales
    assert result_a.has_universal == result_b.has_universal


@given(st.lists(locale_code_st, min_size=1, max_size=5, unique=True))
@settings(max_examples=50)
def test_multi_locale_determinism(locale_codes: list[str]) -> None:
    """Same multi-locale header produces identical results each time."""
    header = ", ".join(locale_codes)
    result_a = _negotiate_and_merge(header)
    result_b = _negotiate_and_merge(header)

    assert result_a.entity_configs == result_b.entity_configs
    assert result_a.source_locales == result_b.source_locales


@given(st.sampled_from(LOCALE_CODES))
@settings(max_examples=50)
def test_deterministic_case_insensitive(locale_code: str) -> None:
    """Same locale in different case produces identical results."""
    header_lower = locale_code.lower()
    header_upper = locale_code.upper()
    header_mixed = locale_code[:2].lower() + locale_code[2:].upper()

    result_lower = _negotiate_and_merge(header_lower)
    result_upper = _negotiate_and_merge(header_upper)
    result_mixed = _negotiate_and_merge(header_mixed)

    assert result_lower.entity_configs == result_upper.entity_configs
    assert result_upper.entity_configs == result_mixed.entity_configs


# ---------------------------------------------------------------------------
# LOCALE-03: Union property — adding a locale never reduces coverage
# ---------------------------------------------------------------------------

@given(st.sampled_from(LOCALE_CODES))
@settings(max_examples=50)
def test_adding_locale_preserves_entity_types(single_code: str) -> None:
    """Union property: adding a locale never removes entity types.

    For any locale A, merge(A) ∪ merge(A, B) ⊆ merge(A, B).
    Every entity type present in the single-locale merge must also be
    present in the multi-locale merge when that locale is included.
    """  # noqa: RUF002
    registry = _full_registry()
    universal = registry.get("en")
    assert universal is not None

    single_neg = LocaleNegotiator(registry)
    single_merger = RecognizerMerger(universal)
    bundles_single, _ = single_neg.negotiate(single_code)
    single_result = single_merger.merge(bundles_single)

    for other in [c for c in LOCALE_CODES if c != single_code]:
        multi_neg = LocaleNegotiator(registry)
        multi_merger = RecognizerMerger(universal)
        bundles_multi, _ = multi_neg.negotiate(f"{single_code}, {other}")
        multi_result = multi_merger.merge(bundles_multi)

        # Every entity from single-locale merge must be in multi-locale merge
        for entity_name, config in single_result.entity_configs.items():
            assert entity_name in multi_result.entity_configs, (
                f"Entity {entity_name} from {single_code} lost when adding {other}"
            )
            # Confidence threshold should be at least as high
            assert (
                multi_result.entity_configs[entity_name].confidence_threshold
                >= config.confidence_threshold
            ), (
                f"Confidence threshold for {entity_name} dropped from "
                f"{config.confidence_threshold} to "
                f"{multi_result.entity_configs[entity_name].confidence_threshold}"
            )


@given(
    st.lists(locale_code_st, min_size=1, max_size=3, unique=True),
    st.lists(locale_code_st, min_size=1, max_size=3, unique=True),
)
@settings(max_examples=50)
def test_union_monotonicity(baseline: list[str], added: list[str]) -> None:
    """Union property: merged set with extra locales is a superset.

    For any locale sets A and B, entity_types(merge(A)) ⊆ entity_types(merge(A ∪ B)).
    """  # noqa: RUF002
    combined = sorted(set(baseline + added))
    if not combined:
        return

    result_baseline = _negotiate_and_merge(", ".join(baseline))
    result_combined = _negotiate_and_merge(", ".join(combined))

    baseline_names = set(result_baseline.entity_configs)
    combined_names = set(result_combined.entity_configs)

    assert baseline_names.issubset(combined_names), (
        f"Entity types {baseline_names - combined_names} lost when adding locales"
    )


@given(st.sampled_from(LOCALE_CODES))
@settings(max_examples=50)
def test_universal_always_present(single_code: str) -> None:
    """Universal entity types are always present regardless of locale."""
    registry = _full_registry()
    universal = registry.get("en")
    assert universal is not None

    merger = RecognizerMerger(universal)
    neg = LocaleNegotiator(registry)
    bundles, _ = neg.negotiate(single_code)
    result = merger.merge(bundles)

    universal_names = {et.name for et in universal.entity_types}
    merged_names = set(result.entity_configs)

    assert universal_names.issubset(merged_names), (
        f"Universal entities {universal_names - merged_names} missing when "
        f"using locale {single_code}"
    )
