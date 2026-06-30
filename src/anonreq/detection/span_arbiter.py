"""SpanArbiter — merges regex and NER detection results with overlap resolution.

Per D-39 through D-41:
- Run regex detection and Presidio NER independently
- Merge via overlap resolution: exact→regex wins, nested→most specific wins,
  partial→most specific wins, non-overlapping→both kept
- Entity specificity ranking from D-41 determines which type wins on overlap
"""

from __future__ import annotations

from typing import Any

from anonreq.detection.regex_patterns import ENTITY_SPECIFICITY

# Re-export for convenient access from other modules
__all__ = ["SpanArbiter", "ENTITY_SPECIFICITY"]


class SpanArbiter:
    """Merges regex and NER detection results with overlap resolution.

    Usage::

        merged = SpanArbiter.merge(regex_results, ner_results)
    """

    @staticmethod
    def merge(
        regex_results: list[dict[str, Any]],
        ner_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge two detection result lists.

        Each result dict must have ``entity_type``, ``start``, ``end``,
        and ``score`` keys. Results with a ``source`` key of ``"regex"``
        or ``"ner"`` are used for overlap resolution.

        Args:
            regex_results: Detection results from RegexDetector.
            ner_results: Detection results from PresidioClient.

        Returns:
            Merged list sorted by start position, with ``_source`` tags
            stripped. Each result retains its original ``source`` key
            (``"regex"`` or ``"ner"``) for downstream audit.
        """
        if not regex_results and not ner_results:
            return []

        # Tag each result with its source
        for r in regex_results:
            r["_source"] = "regex"
        for r in ner_results:
            r["_source"] = "ner"

        combined = regex_results + ner_results
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

        # Remove temporary _source tag
        for r in merged:
            r.pop("_source", None)

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
