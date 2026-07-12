"""Property-based tests for compliance preset invariants.

Tier 3 tests from 04-TEST-PLAN:

- COMP-01: Preset merge never removes entity types from base config (AG-14)
- COMP-02: Merge(merge(a, b), c) == merge(a, merge(b, c)) — associativity
- COMP-03: Combined preset + customer overrides never disable preset-mandated
  types
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from anonreq.compliance.engine import PresetEngine
from anonreq.compliance.merge import merge_presets
from anonreq.compliance.preset import CompliancePreset

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

ENGINE = PresetEngine("config/compliance")
ALL_PRESETS: list[str] = list(ENGINE.list_presets())
ALL_PRESETS_OBJS: list[CompliancePreset] = [ENGINE.get_preset(pid) for pid in ALL_PRESETS]  # type: ignore[misc]

_MIN_BASE_CONFIG: dict = {
    "entity_types": {
        "EMAIL_ADDRESS": {"tier": "REGEX", "confidence_threshold": 0.9},
        "PERSON": {"tier": "NER", "confidence_threshold": 0.7},
    },
}


def _base() -> dict:
    """Return a fresh copy of the minimal base config."""
    return {
        "entity_types": {
            "EMAIL_ADDRESS": {"tier": "REGEX", "confidence_threshold": 0.9},
            "PERSON": {"tier": "NER", "confidence_threshold": 0.7},
        },
    }


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

preset_id_st = st.sampled_from(ALL_PRESETS)
entity_type_st = st.sampled_from(ALL_PRESETS_OBJS).flatmap(
    lambda p: st.sampled_from(p.mandatory_entity_types if p.mandatory_entity_types else ["EMAIL_ADDRESS"])  # noqa: E501
)


@given(
    st.lists(preset_id_st, min_size=1, max_size=3, unique=True),
)
@settings(max_examples=50)
def test_non_weakening_base_config(preset_ids: list[str]) -> None:
    """COMP-01/AG-14: Preset merge never removes entity types from base config.

    Applying any combination of presets to a base config must preserve all
    base entity types. Entity types can only be added or kept — never removed.
    """
    base = _base()
    presets = [ENGINE.get_preset(pid) for pid in preset_ids if ENGINE.get_preset(pid) is not None]

    base_types = set((base.get("entity_types") or {}).keys())
    result = merge_presets(base, presets)

    result_types = set(result.merged_entity_types.keys())
    missing = base_types - result_types
    assert not missing, (
        f"Base entity types {missing} removed by preset merge with {preset_ids}"
    )


@given(
    st.lists(preset_id_st, min_size=1, max_size=3, unique=True),
)
@settings(max_examples=50)
def test_non_weakening_thresholds(preset_ids: list[str]) -> None:
    """AG-14: Preset merge never lowers confidence thresholds.

    For any entity type present in both the base config and the merged
    result, the merged confidence threshold must be >= the base threshold.
    """
    base = _base()
    presets = [ENGINE.get_preset(pid) for pid in preset_ids if ENGINE.get_preset(pid) is not None]

    result = merge_presets(base, presets)
    for entity_name, config in (base.get("entity_types") or {}).items():
        base_threshold = float(config.get("confidence_threshold", config.get("threshold", 0.7)))
        merged_threshold = result.merged_thresholds.get(entity_name, 0.0)
        assert merged_threshold >= base_threshold, (
            f"Threshold for {entity_name} dropped from {base_threshold} to "
            f"{merged_threshold} with presets {preset_ids}"
        )


@given(
    st.lists(preset_id_st, min_size=1, max_size=3, unique=True),
    st.text(min_size=1, max_size=20),
)
@settings(max_examples=50)
def test_overrides_cannot_weaken_preset_mandated_types(
    preset_ids: list[str],
    _override_name: str,  # noqa: PT019
) -> None:
    """COMP-03: Customer overrides never disable preset-mandated types.

    Even when customer overrides specify a lower threshold for a
    preset-mandated type, the merged result must keep the preset's
    threshold (non-weakening invariant). Overrides are applied through
    the same _apply_preset path which uses ``max()`` for thresholds.
    """
    presets = [ENGINE.get_preset(pid) for pid in preset_ids if ENGINE.get_preset(pid) is not None]
    if not presets:
        return

    # Collect all mandatory types across active presets
    mandatory_types: set[str] = set()
    for p in presets:
        mandatory_types.update(p.mandatory_entity_types)

    if not mandatory_types:
        return  # nothing to test

    # Create an override that tries to weaken every mandatory type
    overrides: dict = {"entity_types": {}}
    for mtype in mandatory_types:
        overrides["entity_types"][mtype] = {
            "tier": "REGEX",
            "confidence_threshold": 0.1,  # try to weaken
        }

    base = _base()
    result = merge_presets(base, presets, overrides=overrides)

    for p in presets:
        for mtype in p.mandatory_entity_types:
            preset_threshold = p.thresholds.get(mtype, 0.7)
            merged_threshold = result.merged_thresholds.get(mtype, 0.0)

            # Override threshold is 0.1, but preset threshold must win
            # Non-weakening means max wins, so merged must be >= preset_threshold
            # (It may be higher if the base config already had a higher threshold)
            assert merged_threshold >= preset_threshold, (
                f"Override weakened threshold for {mtype}: preset={preset_threshold}, "
                f"override=0.1, merged={merged_threshold}"
            )


@given(
    st.lists(preset_id_st, min_size=1, max_size=2, unique=True),
    st.lists(preset_id_st, min_size=1, max_size=2, unique=True),
    st.lists(preset_id_st, min_size=1, max_size=2, unique=True),
)
@settings(max_examples=50)
def test_merge_associativity(
    a_ids: list[str],
    b_ids: list[str],
    c_ids: list[str],
) -> None:
    """COMP-02: Merge associativity — ((a | b) | c) == (a | (b | c)).

    Merging presets in different grouping orders must produce the same
    result. Tests that the merge function is associative:
        merge(merge(a, b), c) == merge(a, merge(b, c))
    """
    a_presets = [ENGINE.get_preset(pid) for pid in a_ids if ENGINE.get_preset(pid) is not None]
    b_presets = [ENGINE.get_preset(pid) for pid in b_ids if ENGINE.get_preset(pid) is not None]
    c_presets = [ENGINE.get_preset(pid) for pid in c_ids if ENGINE.get_preset(pid) is not None]

    if not a_presets or not b_presets or not c_presets:
        return  # at least one preset per group needed for associativity test

    base = _base()

    # Helper: convert PresetMergeResult back to base-config dict format
    def _result_to_base(r) -> dict:
        return {
            "entity_types": {
                name: {
                    "tier": tier.value,
                    "confidence_threshold": r.merged_thresholds.get(name, 0.7),
                }
                for name, tier in r.merged_entity_types.items()
            },
            "requires_checksum": list(r.requires_checksum),
        }

    # (a | b) | c
    ab_result = merge_presets(base, a_presets + b_presets)
    abc_left = merge_presets(_result_to_base(ab_result), c_presets)

    # a | (b | c)
    bc_result = merge_presets(base, b_presets + c_presets)
    abc_right = merge_presets(_result_to_base(bc_result), a_presets + b_presets)

    # Compare: same entity types, same thresholds, same checksums
    assert abc_left.merged_entity_types.keys() == abc_right.merged_entity_types.keys(), (
        f"Associativity violation: entity type keys differ\n"
        f"  Left:  {sorted(abc_left.merged_entity_types)}\n"
        f"  Right: {sorted(abc_right.merged_entity_types)}"
    )

    for entity_name in abc_left.merged_entity_types:
        left_threshold = abc_left.merged_thresholds.get(entity_name, 0.0)
        right_threshold = abc_right.merged_thresholds.get(entity_name, 0.0)
        assert abs(left_threshold - right_threshold) < 1e-9, (
            f"Associativity violation: threshold for {entity_name} differs "
            f"(left={left_threshold}, right={right_threshold})"
        )

    assert abc_left.requires_checksum == abc_right.requires_checksum, (
        f"Associativity violation: checksum sets differ\n"
        f"  Left:  {abc_left.requires_checksum}\n"
        f"  Right: {abc_right.requires_checksum}"
    )


@given(
    st.sampled_from(ALL_PRESETS),
    st.sampled_from(ALL_PRESETS),
)
@settings(max_examples=50)
def test_merge_commutative_same_presets(a_id: str, b_id: str) -> None:
    """Pairwise merge is commutative for individual preset pairs.

    merge(base, [A, B]) == merge(base, [B, A])
    """
    a = ENGINE.get_preset(a_id)
    b = ENGINE.get_preset(b_id)
    if a is None or b is None:
        return

    base = _base()
    ab = merge_presets(base, [a, b])
    ba = merge_presets(base, [b, a])

    assert ab.merged_entity_types.keys() == ba.merged_entity_types.keys()
    for entity_name in ab.merged_entity_types:
        assert abs(
            ab.merged_thresholds.get(entity_name, 0.0)
            - ba.merged_thresholds.get(entity_name, 0.0)
        ) < 1e-9
    assert ab.requires_checksum == ba.requires_checksum
