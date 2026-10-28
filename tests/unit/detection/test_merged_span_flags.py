"""Merged spans keep the secret's protected and irreversible flags.

When an ordinary entity type wins an overlap against a secret or MNPI
span, the union span must still be protected (exempt from exclusions and
checksum drops) and irreversible (never stored in the restore mapping).
"""

from __future__ import annotations

from typing import Any

import pytest

from anonreq.detection.exclusion_list import ExclusionList
from anonreq.detection.regex_detector import RegexDetector
from anonreq.detection.span_arbiter import SpanArbiter
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.detection import DetectionStage
from anonreq.tokenization.restorer import Restorer
from anonreq.tokenization.tokenizer import Tokenizer

_EMAIL = "hunter2pass@corp-db.example.com"
_SECRET = "hunter2pass"


def _span(entity_type: str, start: int, end: int, **extra: Any) -> dict[str, Any]:
    return {"entity_type": entity_type, "start": start, "end": end, "score": 0.9, **extra}


class TestArbiterFlagInheritance:
    def test_ordinary_winner_inherits_from_nested_secret(self) -> None:
        # ENTERPRISE_DB_PASSWORD has no specificity rank, so EMAIL wins.
        merged = SpanArbiter.merge(
            [_span("EMAIL_ADDRESS", 0, 31, source="regex")],
            [],
            [_span("ENTERPRISE_DB_PASSWORD", 0, 11, source="enterprise")],
        )
        assert len(merged) == 1
        span = merged[0]
        assert span["entity_type"] == "EMAIL_ADDRESS"
        assert (span["start"], span["end"]) == (0, 31)
        assert span["protected"] is True
        assert span["irreversible"] is True
        assert span["reversible"] is False

    def test_ordinary_winner_inherits_from_partial_secret(self) -> None:
        merged = SpanArbiter.merge(
            [_span("EMAIL_ADDRESS", 0, 20, source="regex")],
            [],
            [_span("ENTERPRISE_DB_PASSWORD", 15, 30, source="enterprise")],
        )
        assert len(merged) == 1
        assert (merged[0]["start"], merged[0]["end"]) == (0, 30)
        assert merged[0]["protected"]
        assert merged[0]["irreversible"]

    def test_flag_survives_chain_of_merges(self) -> None:
        merged = SpanArbiter.merge(
            [_span("EMAIL_ADDRESS", 0, 20, source="regex"), _span("URL", 18, 40)],
            [_span("PERSON", 35, 50, source="ner")],
            [_span("MNPI_DEAL", 5, 8, source="mnpi")],
        )
        assert len(merged) == 1
        assert merged[0]["protected"]
        assert merged[0]["irreversible"]

    def test_caller_irreversible_flag_is_inherited(self) -> None:
        merged = SpanArbiter.merge(
            [_span("EMAIL_ADDRESS", 0, 20), _span("CUSTOM_PIN", 2, 6, irreversible=True)],
            [],
        )
        assert len(merged) == 1
        assert merged[0]["irreversible"] is True

    def test_ordinary_spans_stay_unprotected(self) -> None:
        merged = SpanArbiter.merge(
            [_span("EMAIL_ADDRESS", 0, 20)],
            [_span("PERSON", 10, 25, source="ner")],
        )
        assert merged[0]["protected"] is False
        assert merged[0]["irreversible"] is False

    def test_merge_does_not_mutate_caller_spans(self) -> None:
        secret = _span("ENTERPRISE_DB_PASSWORD", 0, 11, source="enterprise")
        email = _span("EMAIL_ADDRESS", 0, 31)
        SpanArbiter.merge([email], [], [secret])
        assert "protected" not in email
        assert "protected" not in secret


class _EmptyNer:
    async def analyze_text_nodes(  # type: ignore[no-untyped-def]
        self, text_nodes, language="en", entities=None, score_threshold=0.7
    ):
        return [[] for _ in text_nodes]


class _UnrankedSecret:
    """Enterprise secret detector with a type that has no specificity rank."""

    def analyze(self, text: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        start = text.index(_SECRET)
        return [
            _span("ENTERPRISE_DB_PASSWORD", start, start + len(_SECRET), source="enterprise")
        ]


class _ExcludeAll(ExclusionList):
    def filter_detections(self, detections, text):  # type: ignore[no-untyped-def]
        return []


async def _detect(text: str, exclusion: ExclusionList | None = None) -> list[dict[str, Any]]:
    stage = DetectionStage(
        regex_detector=RegexDetector(),
        presidio_client=_EmptyNer(),
        span_arbiter=SpanArbiter(),
        exclusion_list=exclusion or ExclusionList(),
        enterprise_recognizers={"db": _UnrankedSecret()},
        mnpi_recognizers=[],
    )
    ctx = ProcessingContext(request_id="flags", classification_result={"action": "ANONYMIZE"})
    ctx.text_nodes = [{"path": "messages[0].content", "role": "user", "value": text}]
    result = await stage.execute(ctx)
    assert not result.has_errors()
    return result.detections or []


@pytest.mark.asyncio
async def test_secret_absorbed_into_larger_email_is_never_restored() -> None:
    text = f"Mail {_EMAIL} today"
    detections = await _detect(text)
    assert len(detections) == 1
    span = detections[0]
    assert span["entity_type"] == "EMAIL_ADDRESS"
    assert span["reversible"] is False

    tokenizer = Tokenizer()
    tokenizer.initialize_session()
    tokenized, mapping = tokenizer.tokenize(text, detections)
    assert _SECRET not in tokenized
    assert all(_SECRET not in value for value in mapping.values())
    restored = Restorer.restore_text(tokenized, mapping)
    assert _SECRET not in restored


@pytest.mark.asyncio
async def test_absorbed_secret_is_exempt_from_exclusions() -> None:
    detections = await _detect(f"Mail {_EMAIL} today", exclusion=_ExcludeAll())
    assert len(detections) == 1
    assert detections[0]["reversible"] is False
