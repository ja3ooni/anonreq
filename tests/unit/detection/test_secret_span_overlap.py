"""Regression tests for secret spans that used to bypass overlap resolution.

API-key and secret recognizers used to append their spans after SpanArbiter
had already merged regex and NER. Tokenization then replaced the same
characters twice, which corrupted the prompt and made restoration diverge
from the original text.

Every detector now contributes to one resolution pass. The surviving spans
are disjoint, and tokenizing then restoring those spans returns the original
text exactly.
"""

from __future__ import annotations

import re
from itertools import pairwise
from types import SimpleNamespace
from typing import Any

import pytest

from anonreq.detection.exclusion_list import ExclusionList
from anonreq.detection.recognizers.enterprise import create_enterprise_bundle
from anonreq.detection.regex_detector import RegexDetector
from anonreq.detection.span_arbiter import SpanArbiter
from anonreq.locale.bundle import EntityTypeConfig, RecognizerTier
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.detection import DetectionStage
from anonreq.tokenization.restorer import Restorer
from anonreq.tokenization.tokenizer import Tokenizer

_TOKEN = re.compile(r"\[[A-Z][A-Z_]{0,49}_\d+\]")
_API_KEY = "sk-" + ("a" * 24)


class _EmptyNer:
    """Presidio stand-in that reports no NER spans."""

    async def analyze_text_nodes(
        self,
        text_nodes: list[dict[str, Any]],
        entities: list[str] | None = None,
        score_threshold: float = 0.7,
    ) -> list[list[dict[str, Any]]]:
        return [[] for _ in text_nodes]


class _PartialSecretRecognizer:
    """Secret detector whose span partially overlaps ``user@example.com``."""

    def analyze(self, text: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        del tenant_id
        marker = "user@example.com"
        start = text.index(marker) + 5
        end = text.index(marker) + len(marker) + 8
        return [
            {
                "entity_type": "ENTERPRISE_API_KEY",
                "start": start,
                "end": end,
                "score": 0.9,
                "source": "enterprise",
            }
        ]


class _ExactOverlapMnpi:
    """MNPI detector that reports the same span as an email."""

    def analyze(self, text: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        del tenant_id
        marker = "ada@example.com"
        start = text.index(marker)
        return [
            {
                "entity_type": "MNPI_TICKER",
                "start": start,
                "end": start + len(marker),
                "score": 0.4,
                "source": "mnpi",
            }
        ]


class _SeparateMnpi:
    """MNPI detector that reports a ticker away from other entities."""

    def analyze(self, text: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        del tenant_id
        marker = "AAPL"
        start = text.index(marker)
        return [
            {
                "entity_type": "MNPI_TICKER",
                "start": start,
                "end": start + len(marker),
                "score": 0.85,
                "source": "mnpi",
            }
        ]


def _stage(
    enterprise: dict[str, Any] | None = None,
    mnpi: list[Any] | None = None,
) -> DetectionStage:
    return DetectionStage(
        regex_detector=RegexDetector(),
        presidio_client=_EmptyNer(),
        span_arbiter=SpanArbiter(),
        exclusion_list=ExclusionList(),
        enterprise_recognizers=enterprise or {},
        mnpi_recognizers=mnpi or [],
    )


async def _detect(
    text: str,
    *,
    enterprise: dict[str, Any] | None = None,
    mnpi: list[Any] | None = None,
    with_api_key_pattern: bool = False,
) -> list[dict[str, Any]]:
    ctx = ProcessingContext(
        request_id="secret-overlap",
        classification_result={"action": "ANONYMIZE"},
    )
    ctx.text_nodes = [{"path": "messages[0].content", "role": "user", "value": text}]
    if with_api_key_pattern:
        ctx.merged_recognizers = SimpleNamespace(
            entity_configs={
                "API_KEY": EntityTypeConfig(
                    name="API_KEY",
                    tier=RecognizerTier.REGEX,
                    confidence_threshold=0.95,
                    patterns=[r"\bsk-[a-zA-Z0-9]{20,}\b"],
                    reversible=False,
                )
            }
        )
    result = await _stage(enterprise, mnpi).execute(ctx)
    assert not result.has_errors()
    assert result.detections is not None
    return result.detections


def _assert_disjoint(detections: list[dict[str, Any]]) -> None:
    ordered = sorted(detections, key=lambda item: (item["start"], item["end"]))
    for earlier, later in pairwise(ordered):
        assert later["start"] >= earlier["end"], (earlier, later)


def _gaps(text: str, detections: list[dict[str, Any]]) -> list[str]:
    cursor = 0
    gaps: list[str] = []
    for span in sorted(detections, key=lambda item: (item["start"], item["end"])):
        gaps.append(text[cursor : span["start"]])
        cursor = span["end"]
    gaps.append(text[cursor:])
    return gaps


def _assert_round_trip(text: str, detections: list[dict[str, Any]]) -> None:
    """Tokenize the resolved spans and restore them back to ``text``."""
    _assert_disjoint(detections)
    tokenizer = Tokenizer()
    tokenizer.initialize_session()
    forced = [{**detection, "reversible": True} for detection in detections]
    tokenized, mapping = tokenizer.tokenize(text, forced)
    assert Restorer.restore_text(tokenized, mapping) == text
    assert _TOKEN.sub("\0", tokenized).split("\0") == _gaps(text, detections)
    assert len(_TOKEN.findall(tokenized)) == len(detections)


def _assert_secrets_redacted(
    text: str,
    detections: list[dict[str, Any]],
    secrets: list[str],
) -> None:
    tokenizer = Tokenizer()
    tokenizer.initialize_session()
    tokenized, mapping = tokenizer.tokenize(text, detections)
    assert _TOKEN.sub("\0", tokenized).split("\0") == _gaps(text, detections)
    for secret in secrets:
        assert secret not in tokenized
        assert secret not in mapping.values()


@pytest.mark.asyncio
async def test_full_overlap_of_api_key_and_secret_restores() -> None:
    """Locale API_KEY and the enterprise secret detector share one span."""
    text = f"Deploy OPENAI_KEY={_API_KEY} please"
    detections = await _detect(
        text,
        enterprise=create_enterprise_bundle("config/recognizers.yaml"),
        with_api_key_pattern=True,
    )

    assert len(detections) == 1
    assert detections[0]["entity_type"] == "API_KEY"
    assert text[detections[0]["start"] : detections[0]["end"]] == _API_KEY
    assert detections[0]["reversible"] is False
    _assert_round_trip(text, detections)
    _assert_secrets_redacted(text, detections, [_API_KEY])


@pytest.mark.asyncio
async def test_secret_nested_in_url_restores() -> None:
    """An API key inside a URL is one span, not a second replacement."""
    text = f"See https://files.example.com/{_API_KEY}/report today"
    detections = await _detect(
        text,
        enterprise=create_enterprise_bundle("config/recognizers.yaml"),
    )

    covered = [
        detection
        for detection in detections
        if detection["start"] <= text.index(_API_KEY)
        and detection["end"] >= text.index(_API_KEY) + len(_API_KEY)
    ]
    assert len(covered) == 1
    assert covered[0]["entity_type"] == "ENTERPRISE_API_KEY"
    assert covered[0]["reversible"] is False
    _assert_round_trip(text, detections)
    _assert_secrets_redacted(text, detections, [_API_KEY])


@pytest.mark.asyncio
async def test_partial_overlap_of_secret_and_email_restores() -> None:
    """A secret span that only partly covers an email is resolved once."""
    text = "Contact user@example.comSECRET12 please"
    detections = await _detect(
        text,
        enterprise={"partial_secret": _PartialSecretRecognizer()},
    )

    assert len(detections) == 1
    assert detections[0]["entity_type"] == "ENTERPRISE_API_KEY"
    email = next(
        detection
        for detection in RegexDetector().detect(text)
        if detection["entity_type"] == "EMAIL_ADDRESS"
    )
    secret = detections[0]
    assert secret["start"] < email["end"]
    assert email["start"] < secret["start"]
    assert secret["end"] > email["end"]
    assert detections[0]["reversible"] is False
    _assert_round_trip(text, detections)
    _assert_secrets_redacted(text, detections, [text[secret["start"] : secret["end"]]])


@pytest.mark.asyncio
async def test_non_overlapping_secret_and_email_both_restore() -> None:
    """Distinct secret and email spans are both tokenized and restored."""
    text = f"Use {_API_KEY} and mail ada@example.com today"
    detections = await _detect(
        text,
        enterprise=create_enterprise_bundle("config/recognizers.yaml"),
    )

    types = {detection["entity_type"] for detection in detections}
    assert "ENTERPRISE_API_KEY" in types
    assert "EMAIL_ADDRESS" in types
    _assert_round_trip(text, detections)
    _assert_secrets_redacted(text, detections, [_API_KEY])
    tokenizer = Tokenizer()
    tokenizer.initialize_session()
    tokenized, mapping = tokenizer.tokenize(text, detections)
    assert "ada@example.com" not in tokenized
    restored = Restorer.restore_text(tokenized, mapping)
    assert restored.count("ada@example.com") == 1
    assert _API_KEY not in restored


@pytest.mark.asyncio
async def test_mnpi_full_overlap_uses_the_same_resolution() -> None:
    """MNPI spans that duplicate an email do not survive as a second span."""
    text = "Mail ada@example.com about the ticket"
    detections = await _detect(text, mnpi=[_ExactOverlapMnpi()])

    assert [detection["entity_type"] for detection in detections] == ["EMAIL_ADDRESS"]
    _assert_round_trip(text, detections)


@pytest.mark.asyncio
async def test_non_overlapping_mnpi_is_kept_and_restores() -> None:
    """MNPI spans that do not overlap other entities are still detected."""
    text = "Mail ada@example.com about AAPL."
    detections = await _detect(text, mnpi=[_SeparateMnpi()])

    types = {detection["entity_type"] for detection in detections}
    assert types == {"EMAIL_ADDRESS", "MNPI_TICKER"}
    _assert_round_trip(text, detections)
