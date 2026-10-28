"""SpanArbiter — merges every detector's spans with one overlap resolution.

Per D-39 through D-41:
- Run regex detection and Presidio NER independently
- Merge via overlap resolution: exact→regex wins, nested→most specific wins,
  partial→most specific wins, non-overlapping→both kept
- Entity specificity ranking from D-41 determines which type wins on overlap
- Later detectors (MNPI, API-key and secret recognizers) join the same pass
"""

from __future__ import annotations

from typing import Any

from anonreq.detection.regex_patterns import ENTITY_SPECIFICITY

# Re-export for convenient access from other modules
__all__ = ["ENTITY_SPECIFICITY", "SpanArbiter"]


class SpanArbiter:
    """Merges detection results from every detector with one overlap resolution.

    Usage::

        merged = SpanArbiter.merge(regex_results, ner_results, secret_results)
    """

    @staticmethod
    def merge(
        regex_results: list[dict[str, Any]],
        ner_results: list[dict[str, Any]],
        *additional_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge detection results with a single overlap-resolution pass.

        Each result dict must have ``entity_type``, ``start``, ``end``,
        and ``score`` keys. The first list is the regex detector and wins
        exact overlaps (D-40). Further lists — NER, MNPI, API-key and
        secret recognizers — are resolved in the same pass rather than
        appended afterwards.

        Args:
            regex_results: Detection results from RegexDetector.
            ner_results: Detection results from PresidioClient.
            additional_results: Spans from every other detector. Exact
                overlap still prefers ``regex_results``.

        Returns:
            Merged list sorted by start position, with ``_source`` tags
            stripped. Each result retains its original ``source`` key
            for downstream audit. Overlapping spans are reduced to one
            survivor so tokenization replaces each character at most once.
        """
        if not regex_results and not ner_results and not any(additional_results):
            return []

        # Tag each result with its source (copy dicts to avoid mutating caller data).
        # Only the regex-detector list receives the exact-overlap precedence.
        tagged: list[dict[str, Any]] = [{**r, "_source": "regex"} for r in regex_results]
        tagged.extend({**r, "_source": "ner"} for r in ner_results)
        for extra in additional_results:
            tagged.extend({**r, "_source": "other"} for r in extra)

        combined = tagged
        # Sort by start position ascending, then by score descending
        combined.sort(key=lambda r: (r["start"], -r["score"]))

        merged: list[dict[str, Any]] = []
        for span in combined:
            overlapped = False
            for i, accepted in enumerate(merged):
                overlap = SpanArbiter._overlap_type(span, accepted)
                if overlap is None:
                    continue
                overlapped = True

                if overlap == "exact":
                    # D-40: Exact overlap → regex wins
                    if span["_source"] == "regex":
                        merged[i] = span

                elif overlap == "nested":
                    # D-40: Nested → most specific entity type wins
                    span_spec = ENTITY_SPECIFICITY.get(span.get("entity_type", ""), 0)
                    acc_spec = ENTITY_SPECIFICITY.get(accepted.get("entity_type", ""), 0)
                    if span_spec > acc_spec:
                        merged[i] = span

                elif overlap == "partial":
                    # D-40: Partial → most specific entity type wins
                    span_spec = ENTITY_SPECIFICITY.get(span.get("entity_type", ""), 0)
                    acc_spec = ENTITY_SPECIFICITY.get(accepted.get("entity_type", ""), 0)
                    if span_spec > acc_spec:
                        merged[i] = span
                break

            if not overlapped:
                # D-40: Non-overlapping → both kept
                merged.append(span)

        # Remove temporary _source tag and restore start order. A survivor
        # can have a later start than the span it replaced.
        for r in merged:
            r.pop("_source", None)
        merged.sort(key=lambda r: (r["start"], r["end"]))

        return merged

    @staticmethod
    def _overlap_type(
        a: dict[str, Any],
        b: dict[str, Any],
    ) -> str | None:
        """Determine the type of overlap between two spans.

        Args:
            a: First span dict with ``start`` and ``end``.
            b: Second span dict with ``start`` and ``end``.

        Returns:
            ``"exact"`` if spans have identical start and end,
            ``"nested"`` if one span fully contains the other,
            ``"partial"`` if spans partially overlap,
            ``None`` if there is no overlap.
        """
        a_start, a_end = a["start"], a["end"]
        b_start, b_end = b["start"], b["end"]

        # No overlap
        if a_end <= b_start or b_end <= a_start:
            return None

        # Exact overlap
        if a_start == b_start and a_end == b_end:
            return "exact"

        # Nested (one fully contains the other)
        if (a_start >= b_start and a_end <= b_end) or (
            b_start >= a_start and b_end <= a_end
        ):
            return "nested"

        # Partial overlap
        return "partial"
