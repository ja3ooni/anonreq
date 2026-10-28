"""SpanArbiter — merges every detector's spans with one overlap resolution.

Per D-39 through D-41:
- Run regex detection and Presidio NER independently
- Merge via overlap resolution: exact→regex wins, nested→most specific wins,
  partial→most specific wins, non-overlapping→both kept
- Nested and partial overlaps mask the union of every overlapping range
  with the winning span's type, so leftover characters are not left in clear text
- Entity specificity ranking from D-41 determines which type wins on overlap
- Later detectors (MNPI, API-key and secret recognizers) join the same pass
"""

from __future__ import annotations

from typing import Any

from anonreq.detection.regex_patterns import ENTITY_SPECIFICITY, IRREVERSIBLE_ENTITY_TYPES

# Re-export for convenient access from other modules
__all__ = ["ENTITY_SPECIFICITY", "SpanArbiter"]

# Detector sources whose spans must never be unmasked or restored.
_PROTECTED_SOURCES = frozenset({"enterprise", "mnpi"})


def _with_flags(span: dict[str, Any], source_tag: str) -> dict[str, Any]:
    """Copy ``span`` and set its ``protected`` and ``irreversible`` flags.

    A span is protected when it comes from a secret or MNPI detector, has
    an irreversible or MNPI type, or was already flagged by the caller.
    Protected spans are irreversible: they are never restored.
    """
    entity_type = str(span.get("entity_type", ""))
    irreversible = (
        bool(span.get("irreversible"))
        or span.get("reversible") is False
        or entity_type in IRREVERSIBLE_ENTITY_TYPES
    )
    protected = (
        bool(span.get("protected"))
        or span.get("source") in _PROTECTED_SOURCES
        or entity_type.startswith("MNPI_")
        or irreversible
    )
    return {
        **span,
        "_source": source_tag,
        "protected": protected,
        "irreversible": irreversible or protected,
    }


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
            for downstream audit. Overlapping spans collapse to one span
            whose bounds are the union of every range in the cluster and
            whose type is the winner, so tokenization replaces each
            detected character exactly once.
        """
        if not regex_results and not ner_results and not any(additional_results):
            return []

        # Tag each result with its source (copy dicts to avoid mutating caller data).
        # Only the regex-detector list receives the exact-overlap precedence.
        tagged: list[dict[str, Any]] = [_with_flags(r, "regex") for r in regex_results]
        tagged.extend(_with_flags(r, "ner") for r in ner_results)
        for extra in additional_results:
            tagged.extend(_with_flags(r, "other") for r in extra)

        combined = tagged
        # Sort by start position ascending, then by score descending
        combined.sort(key=lambda r: (r["start"], -r["score"]))

        merged: list[dict[str, Any]] = []
        for span in combined:
            pending = span
            while True:
                overlap_at: tuple[int, dict[str, Any], str] | None = None
                for index, accepted in enumerate(merged):
                    overlap = SpanArbiter._overlap_type(pending, accepted)
                    if overlap is None:
                        continue
                    overlap_at = (index, accepted, overlap)
                    break
                if overlap_at is None:
                    # D-40: Non-overlapping → both kept
                    merged.append(pending)
                    break
                index, accepted, overlap = overlap_at
                winner = SpanArbiter._preferred_span(pending, accepted, overlap)
                other = accepted if winner is pending else pending
                merged.pop(index)
                # Exact overlaps already share bounds. Nested and partial
                # overlaps keep the winner's type and mask the union, then
                # rescan because the wider span may meet another survivor.
                pending = SpanArbiter._cover_union(winner, other)

        # Remove temporary _source tag and restore start order. A survivor
        # can have a later start than the span it replaced.
        for r in merged:
            r.pop("_source", None)
        merged.sort(key=lambda r: (r["start"], r["end"]))

        return merged

    @staticmethod
    def _preferred_span(
        incoming: dict[str, Any],
        accepted: dict[str, Any],
        overlap: str,
    ) -> dict[str, Any]:
        """Choose which span's metadata survives an overlap.

        Exact overlap prefers the regex-detector list (D-40). Nested and
        partial overlaps prefer the higher specificity ranking.
        """
        if overlap == "exact":
            if incoming.get("_source") == "regex":
                return incoming
            return accepted
        incoming_spec = ENTITY_SPECIFICITY.get(str(incoming.get("entity_type", "")), 0)
        accepted_spec = ENTITY_SPECIFICITY.get(str(accepted.get("entity_type", "")), 0)
        if incoming_spec > accepted_spec:
            return incoming
        return accepted

    @staticmethod
    def _cover_union(winner: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
        """Return ``winner`` expanded to the union of both ranges.

        The merged span inherits ``protected`` and ``irreversible`` from
        either side, so a secret absorbed by an ordinary type that wins
        the overlap is still never unmasked or restored.
        """
        covered = {**winner}
        covered["protected"] = bool(winner.get("protected")) or bool(other.get("protected"))
        covered["irreversible"] = bool(winner.get("irreversible")) or bool(
            other.get("irreversible")
        )
        if covered["irreversible"]:
            covered["reversible"] = False
        covered["start"] = min(int(winner["start"]), int(other["start"]))
        covered["end"] = max(int(winner["end"]), int(other["end"]))
        return covered

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
