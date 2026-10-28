"""Tests for SpanArbiter — regex+NIR merge with specificity-ranked overlap resolution.

Per D-39 through D-41:
- Run regex and NER independently, then merge
- Exact span overlap → regex wins
- Nested overlap → most specific entity type wins
- Partial overlap → most specific entity type wins
- Non-overlapping → both kept
"""

from __future__ import annotations

from anonreq.detection.span_arbiter import ENTITY_SPECIFICITY, SpanArbiter


class TestSpanArbiter:
    """Test suite for SpanArbiter merge logic."""

    def test_exact_overlap_regex_wins(self):
        """Exact span overlap: regex result replaces NER result."""
        regex_results = [
            {"entity_type": "PHONE_NUMBER", "start": 10, "end": 25, "score": 1.0, "source": "regex"},  # noqa: E501
        ]
        ner_results = [
            {"entity_type": "PHONE_NUMBER", "start": 10, "end": 25, "score": 0.85, "source": "ner"},
        ]
        merged = SpanArbiter.merge(regex_results, ner_results)
        assert len(merged) == 1
        assert merged[0]["source"] == "regex"
        assert merged[0]["score"] == 1.0

    def test_exact_overlap_different_types_regex_wins(self):
        """Exact overlap with different types: regex wins regardless of type."""
        regex_results = [
            {"entity_type": "EMAIL_ADDRESS", "start": 5, "end": 20, "score": 1.0, "source": "regex"},  # noqa: E501
        ]
        ner_results = [
            {"entity_type": "PERSON", "start": 5, "end": 20, "score": 0.9, "source": "ner"},
        ]
        merged = SpanArbiter.merge(regex_results, ner_results)
        assert len(merged) == 1
        assert merged[0]["entity_type"] == "EMAIL_ADDRESS"
        assert merged[0]["source"] == "regex"

    def test_nested_overlap_most_specific_wins(self):
        """Nested overlap: most specific entity type wins (EMAIL > PERSON)."""
        regex_results = [
            {"entity_type": "EMAIL_ADDRESS", "start": 10, "end": 25, "score": 1.0, "source": "regex"},  # noqa: E501
        ]
        ner_results = [
            {"entity_type": "PERSON", "start": 12, "end": 22, "score": 0.9, "source": "ner"},
        ]
        merged = SpanArbiter.merge(regex_results, ner_results)
        assert len(merged) == 1
        # EMAIL_ADDRESS (specificity 90) > PERSON (specificity 40)
        assert merged[0]["entity_type"] == "EMAIL_ADDRESS"

    def test_nested_overlap_larger_span_wins_when_more_specific(self):
        """Nested overlap: larger span wins if it is more specific."""
        regex_results = [
            {"entity_type": "EMAIL_ADDRESS", "start": 10, "end": 25, "score": 1.0, "source": "regex"},  # noqa: E501
        ]
        ner_results = [
            {"entity_type": "LOCATION", "start": 15, "end": 25, "score": 0.8, "source": "ner"},
        ]
        merged = SpanArbiter.merge(regex_results, ner_results)
        assert len(merged) == 1
        # EMAIL_ADDRESS (90) > LOCATION (30)
        assert merged[0]["entity_type"] == "EMAIL_ADDRESS"

    def test_partial_overlap_most_specific_wins(self):
        """Partial overlap: most specific entity type wins."""
        regex_results = [
            {"entity_type": "PHONE_NUMBER", "start": 10, "end": 20, "score": 1.0, "source": "regex"},  # noqa: E501
        ]
        ner_results = [
            {"entity_type": "LOCATION", "start": 15, "end": 25, "score": 0.7, "source": "ner"},
        ]
        merged = SpanArbiter.merge(regex_results, ner_results)
        assert len(merged) == 1
        # PHONE_NUMBER (80) > LOCATION (30)
        assert merged[0]["entity_type"] == "PHONE_NUMBER"

    def test_non_overlapping_spans_both_kept(self):
        """Non-overlapping spans: both kept."""
        regex_results = [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 15, "score": 1.0, "source": "regex"},  # noqa: E501
        ]
        ner_results = [
            {"entity_type": "LOCATION", "start": 30, "end": 40, "score": 0.9, "source": "ner"},
        ]
        merged = SpanArbiter.merge(regex_results, ner_results)
        assert len(merged) == 2
        types = {r["entity_type"] for r in merged}
        assert "EMAIL_ADDRESS" in types
        assert "LOCATION" in types

    def test_empty_lists_produce_empty_result(self):
        """Empty regex and NER lists produce empty result."""
        assert SpanArbiter.merge([], []) == []

    def test_only_regex_results_pass_through(self):
        """Only regex results pass through unchanged."""
        results = [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 15, "score": 1.0, "source": "regex"},  # noqa: E501
        ]
        merged = SpanArbiter.merge(results, [])
        assert len(merged) == 1
        assert merged[0]["entity_type"] == "EMAIL_ADDRESS"
        assert merged[0]["source"] == "regex"

    def test_only_ner_results_pass_through(self):
        """Only NER results pass through unchanged."""
        results = [
            {"entity_type": "PERSON", "start": 0, "end": 10, "score": 0.85, "source": "ner"},
        ]
        merged = SpanArbiter.merge([], results)
        assert len(merged) == 1
        assert merged[0]["entity_type"] == "PERSON"
        assert merged[0]["source"] == "ner"

    def test_multiple_non_overlapping_spans_all_kept(self):
        """Multiple non-overlapping spans of different types all kept."""
        regex_results = [
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 15, "score": 1.0, "source": "regex"},  # noqa: E501
            {"entity_type": "PHONE_NUMBER", "start": 30, "end": 45, "score": 1.0, "source": "regex"},  # noqa: E501
        ]
        ner_results = [
            {"entity_type": "PERSON", "start": 50, "end": 60, "score": 0.9, "source": "ner"},
            {"entity_type": "LOCATION", "start": 70, "end": 80, "score": 0.85, "source": "ner"},
        ]
        merged = SpanArbiter.merge(regex_results, ner_results)
        assert len(merged) == 4

    def test_merged_results_sorted_by_start(self):
        """Merged results are sorted by start position ascending."""
        regex_results = [
            {"entity_type": "PHONE_NUMBER", "start": 30, "end": 45, "score": 1.0, "source": "regex"},  # noqa: E501
            {"entity_type": "EMAIL_ADDRESS", "start": 0, "end": 15, "score": 1.0, "source": "regex"},  # noqa: E501
        ]
        ner_results = [
            {"entity_type": "PERSON", "start": 50, "end": 60, "score": 0.9, "source": "ner"},
        ]
        merged = SpanArbiter.merge(regex_results, ner_results)
        starts = [r["start"] for r in merged]
        assert starts == sorted(starts)

    def test_overlap_type_none(self):
        """_overlap_type returns None for non-overlapping spans."""
        a = {"start": 0, "end": 10}
        b = {"start": 15, "end": 25}
        assert SpanArbiter._overlap_type(a, b) is None

    def test_overlap_type_exact(self):
        """_overlap_type returns 'exact' for identical spans."""
        a = {"start": 5, "end": 15}
        b = {"start": 5, "end": 15}
        assert SpanArbiter._overlap_type(a, b) == "exact"

    def test_overlap_type_nested(self):
        """_overlap_type returns 'nested' for one span within another."""
        a = {"start": 5, "end": 20}  # outer
        b = {"start": 8, "end": 15}  # inner
        assert SpanArbiter._overlap_type(a, b) == "nested"

    def test_overlap_type_partial(self):
        """_overlap_type returns 'partial' for overlapping but not contained spans."""
        a = {"start": 5, "end": 15}
        b = {"start": 10, "end": 20}
        assert SpanArbiter._overlap_type(a, b) == "partial"

    def test_entity_specificity_imported(self):
        """ENTITY_SPECIFICITY dict is accessible from span_arbiter module."""
        assert ENTITY_SPECIFICITY["API_KEY"] == 100
        assert ENTITY_SPECIFICITY["EMAIL_ADDRESS"] == 90
        assert ENTITY_SPECIFICITY["ORGANIZATION"] == 25

    def test_source_tag_removed(self):
        """_source tag is stripped from merged results."""
        regex_results = [
            {"entity_type": "EMAIL", "start": 0, "end": 10, "score": 1.0, "source": "regex"},
        ]
        ner_results = [
            {"entity_type": "PERSON", "start": 20, "end": 30, "score": 0.9, "source": "ner"},
        ]
        merged = SpanArbiter.merge(regex_results, ner_results)
        for r in merged:
            assert "_source" not in r, f"Source tag leaked: {r.keys()}"

    def test_adjacent_spans_no_overlap(self):
        """Adjacent spans (end == start of next) do not overlap."""
        a = {"entity_type": "EMAIL", "start": 0, "end": 10, "score": 1.0, "source": "regex"}
        b = {"entity_type": "PHONE", "start": 10, "end": 20, "score": 1.0, "source": "regex"}
        merged = SpanArbiter.merge([a], [b])
        assert len(merged) == 2

    def test_full_overlap_secret_span_keeps_regex(self):
        """Exact overlap of an API key and a secret detector keeps one span."""
        regex_results = [
            {"entity_type": "API_KEY", "start": 18, "end": 45, "score": 1.0, "source": "regex"},
        ]
        secret_results = [
            {
                "entity_type": "ENTERPRISE_API_KEY",
                "start": 18,
                "end": 45,
                "score": 0.85,
                "source": "enterprise",
            },
        ]
        original = [dict(secret_results[0])]
        merged = SpanArbiter.merge(regex_results, [], secret_results)
        assert secret_results == original
        assert len(merged) == 1
        assert merged[0]["entity_type"] == "API_KEY"
        assert merged[0]["source"] == "regex"
        assert "_source" not in merged[0]

    def test_partial_overlap_secret_keeps_more_specific(self):
        """Partial overlap: the secret span wins when it is more specific."""
        regex_results = [
            {
                "entity_type": "EMAIL_ADDRESS",
                "start": 8,
                "end": 30,
                "score": 1.0,
                "source": "regex",
            },
        ]
        secret_results = [
            {
                "entity_type": "ENTERPRISE_API_KEY",
                "start": 13,
                "end": 32,
                "score": 0.9,
                "source": "enterprise",
            },
        ]
        merged = SpanArbiter.merge(regex_results, [], secret_results)
        assert len(merged) == 1
        assert merged[0]["entity_type"] == "ENTERPRISE_API_KEY"
        assert merged[0]["start"] == 13
        assert merged[0]["end"] == 32

    def test_nested_secret_inside_url_keeps_secret(self):
        """A secret nested in a URL survives as the single more-specific span."""
        regex_results = [
            {"entity_type": "URL", "start": 4, "end": 64, "score": 1.0, "source": "regex"},
        ]
        secret_results = [
            {
                "entity_type": "ENTERPRISE_API_KEY",
                "start": 30,
                "end": 57,
                "score": 0.85,
                "source": "enterprise",
            },
        ]
        merged = SpanArbiter.merge(regex_results, [], secret_results)
        assert len(merged) == 1
        assert merged[0]["entity_type"] == "ENTERPRISE_API_KEY"

    def test_secret_overlapping_two_entities_stays_disjoint(self):
        """A secret that meets two other spans resolves to one non-overlapping span."""
        regex_results = [
            {
                "entity_type": "EMAIL_ADDRESS",
                "start": 0,
                "end": 20,
                "score": 1.0,
                "source": "regex",
            },
            {
                "entity_type": "PHONE_NUMBER",
                "start": 25,
                "end": 40,
                "score": 1.0,
                "source": "regex",
            },
        ]
        secret_results = [
            {
                "entity_type": "ENTERPRISE_API_KEY",
                "start": 10,
                "end": 35,
                "score": 0.9,
                "source": "enterprise",
            },
        ]
        merged = SpanArbiter.merge(regex_results, [], secret_results)
        assert len(merged) == 1
        assert merged[0]["entity_type"] == "ENTERPRISE_API_KEY"
        assert merged[0]["start"] == 10
        assert merged[0]["end"] == 35

    def test_non_overlapping_secret_and_email_both_kept(self):
        """A secret away from other entities is kept alongside them."""
        regex_results = [
            {
                "entity_type": "EMAIL_ADDRESS",
                "start": 40,
                "end": 55,
                "score": 1.0,
                "source": "regex",
            },
        ]
        secret_results = [
            {
                "entity_type": "ENTERPRISE_API_KEY",
                "start": 4,
                "end": 31,
                "score": 0.85,
                "source": "enterprise",
            },
        ]
        merged = SpanArbiter.merge(regex_results, [], secret_results)
        assert len(merged) == 2
        assert [item["start"] for item in merged] == [4, 40]
