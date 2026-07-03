"""Property-based tests for classification invariants (Plan 12-03).

Covers:
- Classification level is always set (never None, never empty)
- Classification never drops below detected level (monotonic)
- Client override is always ≥ detected level (increase-only invariant)
- Same input → same classification (deterministic)
- Handling action is always one of the three known values
"""

from __future__ import annotations

from hypothesis import assume, given, settings, strategies as st

from anonreq.models.classification import ClassificationLevel, ENTITY_CLASSIFICATION_MAP
from anonreq.services.classification import ClassificationService

KNOWN_ENTITY_TYPES = sorted(ENTITY_CLASSIFICATION_MAP.keys())

svc = ClassificationService()

classification_strategy = st.sampled_from(list(ClassificationLevel))
entity_list_strategy = st.lists(
    st.sampled_from(KNOWN_ENTITY_TYPES),
    min_size=0,
    max_size=10,
    unique=True,
)


@given(entity_list_strategy)
@settings(max_examples=500, deadline=None)
async def test_classification_level_always_set(entity_types):
    """Invariant: classification level is always set, never drops below PUBLIC."""
    result = await svc.classify(entity_types, client_level=None)
    assert result.highest is not None
    assert isinstance(result.highest, ClassificationLevel)
    assert result.highest >= ClassificationLevel.PUBLIC


@given(entity_list_strategy, classification_strategy)
@settings(max_examples=500, deadline=None)
async def test_classification_never_drops_below_detected(entity_types, client_level):
    """Invariant: final classification never drops below detected level.

    The higher-wins rule ensures client can only increase, never decrease.
    """
    result = await svc.classify(entity_types, client_level=client_level)
    # Determine detected level from entity types
    detected = ClassificationLevel.PUBLIC
    for et in entity_types:
        mapped = ENTITY_CLASSIFICATION_MAP.get(et.upper())
        if mapped is not None and mapped > detected:
            detected = mapped
    assert result.highest >= detected, (
        f"Classification {result.highest.name} dropped below detected {detected.name} "
        f"for entities {entity_types}"
    )


@given(entity_list_strategy)
@settings(max_examples=500, deadline=None)
async def test_deterministic_classification(entity_types):
    """Invariant: same input → same classification (deterministic)."""
    result1 = await svc.classify(entity_types, client_level=None)
    for _ in range(50):
        result_n = await svc.classify(entity_types, client_level=None)
        assert result_n.highest == result1.highest
        assert result_n.labels == result1.labels
        assert result_n.detected_levels == result1.detected_levels
        assert result_n.handling_action == result1.handling_action


@given(entity_list_strategy)
@settings(max_examples=500, deadline=None)
async def test_handling_action_is_known(entity_types):
    """Invariant: handling_action is always one of the three known values."""
    result = await svc.classify(entity_types, client_level=None)
    assert result.handling_action in (
        "allow_and_anonymize",
        "anonymize_and_flag",
        "block",
    )


@given(entity_list_strategy)
@settings(max_examples=500, deadline=None)
async def test_highest_entity_matches_highest_level(entity_types):
    """Invariant: highest_entity has a classification level matching highest."""
    assume(len(entity_types) > 0)
    result = await svc.classify(entity_types, client_level=None)
    if result.highest_entity is not None:
        mapped_level = ENTITY_CLASSIFICATION_MAP.get(result.highest_entity)
        if mapped_level is not None:
            assert mapped_level == result.highest, (
                f"highest_entity {result.highest_entity} has level {mapped_level.name} "
                f"but highest is {result.highest.name}"
            )


@given(st.lists(st.sampled_from(KNOWN_ENTITY_TYPES + ["UNKNOWN_TYPE"]), min_size=0, max_size=10, unique=True))
@settings(max_examples=500, deadline=None)
async def test_unknown_entity_does_not_crash(entity_types):
    """Invariant: unknown entity types never cause crash."""
    result = await svc.classify(entity_types, client_level=None)
    assert result.highest is not None
    assert result.handling_action in (
        "allow_and_anonymize",
        "anonymize_and_flag",
        "block",
    )


@given(entity_list_strategy)
@settings(max_examples=500, deadline=None)
async def test_client_override_monotonic(entity_types):
    """Invariant: client override is monotonic increase-only.

    Asserting a higher level increases result; asserting lower does nothing.
    """
    base_result = await svc.classify(entity_types, client_level=None)

    # Try to increase with HIGHLY_RESTRICTED
    high_result = await svc.classify(
        entity_types, client_level=ClassificationLevel.HIGHLY_RESTRICTED,
    )
    assert high_result.highest >= base_result.highest

    # Try to decrease with PUBLIC
    low_result = await svc.classify(
        entity_types, client_level=ClassificationLevel.PUBLIC,
    )
    assert low_result.highest == base_result.highest
