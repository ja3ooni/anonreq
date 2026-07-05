"""Property-based tests for fairness invariants.

Per REQ-44, REQ-47, TEST-04:
- Determinism: same inputs → same outputs
- Recall disparity bounded in [0, 1]
- ci/cd gate invariants: should_fail_build matches threshold
- DemographicResult.recall == detected / total
- FairnessEvaluation.overall_passed == all(results.passed)
"""

from __future__ import annotations

from hypothesis import assume, given, strategies as st
from anonreq.models.fairness import (
    DemographicResult,
    FairnessEvaluation,
    FairnessResult,
)
from anonreq.fairness.evaluation import FairnessEvaluator


# ── Strategy helpers ──────────────────────────────────────────────

_group_names = st.sampled_from([
    "group_a", "group_b", "group_c", "group_d",
    "asian", "black", "hispanic", "white", "other",
])
_entity_types = st.sampled_from([
    "PERSON", "EMAIL", "PHONE", "CREDIT_CARD", "SSN",
    "IBAN", "IP_ADDRESS", "DATE_TIME", "LOCATION", "NRP",
])

# A DemographicResult with a valid total > 0
_demographic_result = st.builds(
    DemographicResult,
    group=_group_names,
    total=st.integers(min_value=1, max_value=10_000),
    detected=st.integers(min_value=0, max_value=10_000),
).filter(lambda r: r.total >= r.detected)  # detected <= total invariant


# ── Determinism invariants ────────────────────────────────────────


class TestDisparityDeterminism:
    """compute_recall_disparity is a pure deterministic function."""

    @given(st.lists(_demographic_result, min_size=2, max_size=20))
    def test_disparity_deterministic(self, results: list[DemographicResult]) -> None:
        """Same inputs produce same disparity value."""
        evaluator = FairnessEvaluator()
        d1 = evaluator.compute_recall_disparity(results)
        d2 = evaluator.compute_recall_disparity(results)
        assert d1 == d2, "disparity must be deterministic"


# ── Boundedness invariants ────────────────────────────────────────


class TestDisparityBounds:
    """Recall disparity is always in [0, 1]."""

    @given(st.lists(_demographic_result, min_size=0, max_size=20))
    def test_disparity_between_zero_and_one(
        self, results: list[DemographicResult]
    ) -> None:
        """Disparity is always >= 0 and <= 1."""
        evaluator = FairnessEvaluator()
        d = evaluator.compute_recall_disparity(results)
        assert 0.0 <= d <= 1.0, f"disparity {d} outside [0, 1]"

    @given(st.lists(_demographic_result, min_size=0, max_size=1))
    def test_single_group_disparity_zero(
        self, results: list[DemographicResult]
    ) -> None:
        """0 or 1 groups → disparity = 0."""
        evaluator = FairnessEvaluator()
        assert evaluator.compute_recall_disparity(results) == 0.0

    @given(
        _demographic_result,
        _demographic_result,
    )
    def test_disparity_equals_recall_diff(
        self, r1: DemographicResult, r2: DemographicResult
    ) -> None:
        """Disparity equals |recall1 - recall2| for two groups."""
        evaluator = FairnessEvaluator()
        d = evaluator.compute_recall_disparity([r1, r2])
        expected = abs(r1.recall - r2.recall)
        assert d == expected, f"disparity {d} != expected {expected}"


# ── DemographicResult invariants ──────────────────────────────────


class TestDemographicResultInvariants:
    """DemographicResult.recall is always detected / total."""

    @given(detected=st.integers(min_value=0, max_value=10_000))
    def test_perfect_recall(self, detected: int) -> None:
        """detected == total → recall == 1.0."""
        r = DemographicResult(group="test", total=detected, detected=detected)
        if detected == 0:
            assert r.recall == 0.0
        else:
            assert r.recall == 1.0

    @given(
        total=st.integers(min_value=1, max_value=10_000),
        detected=st.integers(min_value=0, max_value=10_000),
    )
    def test_recall_bounded(self, total: int, detected: int) -> None:
        """Recall is always in [0, 1]."""
        assume(detected <= total)
        r = DemographicResult(group="t", total=total, detected=detected)
        assert 0.0 <= r.recall <= 1.0

    @given(total=st.integers(min_value=1, max_value=10_000))
    def test_zero_detected(self, total: int) -> None:
        """detected == 0 → recall == 0.0."""
        r = DemographicResult(group="t", total=total, detected=0)
        assert r.recall == 0.0


# ── should_fail_build invariants ──────────────────────────────────


class TestBuildGateInvariants:
    """should_fail_build matches threshold comparison."""

    @given(
        results=st.lists(
            st.builds(
                FairnessResult,
                entity_type=_entity_types,
                overall_recall=st.floats(min_value=0.0, max_value=1.0),
                demographic_results=st.lists(
                    _demographic_result, min_size=0, max_size=5
                ),
                max_disparity=st.floats(min_value=0.0, max_value=1.0),
                # threshold is not used by should_fail_build;
                # it uses evaluator.threshold
                threshold=st.just(0.05),
            ),
            min_size=1,
            max_size=10,
        ),
    )
    def test_fail_build_matches_threshold(
        self, results: list[FairnessResult]
    ) -> None:
        """should_fail_build iff any max_disparity > evaluator.threshold."""
        evaluator = FairnessEvaluator()
        should_fail = evaluator.should_fail_build(
            FairnessEvaluation(id="test", results=results)
        )
        any_exceeded = any(r.max_disparity > evaluator.threshold for r in results)
        assert should_fail == any_exceeded, (
            f"should_fail_build={should_fail} ≠ any_exceeded={any_exceeded}"
        )


# ── FairnessEvaluation invariants ─────────────────────────────────


class TestFairnessEvaluationInvariants:
    """overall_passed == all(results.passed)."""

    @given(
        results=st.lists(
            st.builds(
                FairnessResult,
                entity_type=_entity_types,
                overall_recall=st.floats(min_value=0.0, max_value=1.0),
                demographic_results=st.lists(
                    _demographic_result, min_size=0, max_size=5
                ),
                max_disparity=st.floats(min_value=0.0, max_value=1.0),
                threshold=st.floats(min_value=0.0, max_value=1.0),
            ),
            min_size=0,
            max_size=10,
        ),
    )
    def test_overall_passed_invariant(self, results: list[FairnessResult]) -> None:
        """overall_passed is True iff all individual results passed."""
        evaluation = FairnessEvaluation(id="invariant-test", results=results)
        expected = all(r.passed for r in results) if results else True
        assert evaluation.overall_passed == expected, (
            f"overall_passed={evaluation.overall_passed} ≠ expected={expected}"
        )

    @given(
        results=st.lists(
            st.builds(
                FairnessResult,
                entity_type=_entity_types,
                overall_recall=st.floats(min_value=0.0, max_value=1.0),
                demographic_results=st.lists(
                    _demographic_result, min_size=0, max_size=5
                ),
                max_disparity=st.floats(min_value=0.0, max_value=1.0),
                threshold=st.floats(min_value=0.0, max_value=1.0),
            ),
            min_size=0,
            max_size=10,
        ),
    )
    def test_result_passed_invariant(self, results: list[FairnessResult]) -> None:
        """Each result.passed == (max_disparity <= threshold)."""
        for r in results:
            expected = r.max_disparity <= r.threshold
            assert r.passed == expected, (
                f"result {r.entity_type}: passed={r.passed} ≠ expected={expected}"
            )

    def test_empty_evaluation_passes(self) -> None:
        """Empty results → overall_passed."""
        evaluation = FairnessEvaluation(id="empty", results=[])
        assert evaluation.overall_passed is True
