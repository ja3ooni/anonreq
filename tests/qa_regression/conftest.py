"""Shared fixtures for QA regression tests (synthetic data only)."""
from __future__ import annotations

import pytest

from anonreq.detection.exclusion_list import ExclusionList
from anonreq.detection.pipeline import load_enterprise_recognizers
from anonreq.detection.regex_detector import RegexDetector
from anonreq.detection.span_arbiter import SpanArbiter
from anonreq.locale.checksum import ChecksumValidatorRegistry
from anonreq.locale.merger import RecognizerMerger
from anonreq.locale.registry import LocaleRegistry
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.detection import DetectionStage
from anonreq.pipeline.tokenization import TokenizationStage
from anonreq.tokenization.tokenizer import Tokenizer


class _NoNER:
    async def analyze_text_nodes(self, nodes, **_kw):
        return [[] for _ in nodes]


class _Cache:
    async def store_mapping(self, *_a, **_k):
        return True


@pytest.fixture
def de_pipeline():
    """Return an async callable running de-DE detection + tokenization on a request."""
    checksums = ChecksumValidatorRegistry()
    registry = LocaleRegistry(checksum_registry=checksums)
    merged = RecognizerMerger(registry.get("en")).merge([registry.get("de-DE")])
    detection = DetectionStage(
        RegexDetector(), _NoNER(), SpanArbiter(), ExclusionList(),
        checksum_registry=checksums,
        enterprise_recognizers=load_enterprise_recognizers(),
    )

    async def run(request: dict) -> ProcessingContext:
        ctx = ProcessingContext(
            request_id="qa", context_id="qa-ctx",
            original_request=request, merged_recognizers=merged,
        )
        await detection.execute(ctx)
        await TokenizationStage(Tokenizer(), _Cache()).execute(ctx)
        return ctx

    return run


def user(text: str) -> dict:
    return {"model": "gpt-4o", "messages": [{"role": "user", "content": text}]}
