"""German names and street addresses are masked when the Presidio sidecar is up.

Marked ``presidio``. Skips when the sidecar at ``ANONREQ_PRESIDIO_URL`` is
down. The demo analyzer listens on port 3000. Run it against an image built
from ``docker/presidio/Dockerfile`` (pinned ``en_core_web_lg`` and
``de_core_news_lg``):

    ANONREQ_PRESIDIO_URL=http://localhost:3000 uv run pytest -m presidio
"""

from __future__ import annotations

import os

import httpx
import pytest

from anonreq.detection.exclusion_list import ExclusionList
from anonreq.detection.presidio_client import PresidioClient
from anonreq.detection.regex_detector import RegexDetector
from anonreq.detection.span_arbiter import SpanArbiter
from anonreq.locale.checksum import ChecksumValidatorRegistry
from anonreq.locale.merger import RecognizerMerger
from anonreq.locale.negotiator import LocaleNegotiator
from anonreq.locale.registry import LocaleRegistry
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.detection import DetectionStage
from anonreq.restore.engine import RestoreEngine
from anonreq.tokenization.tokenizer import Tokenizer

pytestmark = pytest.mark.presidio

GERMAN_TEXT = "Hans Müller, Hauptstraße 12, 60311 Frankfurt"
MASKED_VALUES = ("Hans Müller", "Hauptstraße 12", "60311 Frankfurt")


@pytest.fixture
def presidio_url() -> str:
    url = os.environ.get("ANONREQ_PRESIDIO_URL", "http://localhost:3000").rstrip("/")
    try:
        response = httpx.get(f"{url}/health", timeout=2.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        pytest.skip(f"Presidio sidecar not reachable at {url}: {exc}")
    return url


def _covers(text: str, needle: str, detections: list[dict]) -> bool:
    start = text.index(needle)
    end = start + len(needle)
    return any(
        detection["start"] <= start and detection["end"] >= end
        for detection in detections
    )


async def test_german_name_and_address_are_masked_and_restored(presidio_url: str) -> None:
    checksum = ChecksumValidatorRegistry()
    registry = LocaleRegistry("config/locales", checksum_registry=checksum)
    negotiator = LocaleNegotiator(registry)
    bundles, _ = negotiator.negotiate("de-DE")
    merged = RecognizerMerger(registry.get("en")).merge(bundles)

    client = PresidioClient(base_url=presidio_url, timeout=30.0)
    try:
        ctx = ProcessingContext(
            request_id="req-de",
            tenant_id="default",
            text_nodes=[
                {"path": "messages.0.content", "role": "user", "value": GERMAN_TEXT}
            ],
            classification_result={"action": "ANONYMIZE"},
            locale_header="de-DE",
            locale_bundles=bundles,
            merged_recognizers=merged,
        )
        stage = DetectionStage(
            regex_detector=RegexDetector(),
            presidio_client=client,
            span_arbiter=SpanArbiter(),
            exclusion_list=ExclusionList(),
            checksum_registry=checksum,
        )
        result = await stage.execute(ctx)
    finally:
        await client.close()

    assert not result.has_errors(), result.errors
    detections = [item for item in result.detections or [] if item.get("node_index") == 0]
    assert _covers(GERMAN_TEXT, "Hans Müller", detections)
    assert _covers(GERMAN_TEXT, "Hauptstraße 12", detections)
    assert _covers(GERMAN_TEXT, "60311 Frankfurt", detections)
    assert any(item["entity_type"] == "PERSON" for item in detections)
    assert any(item["entity_type"] == "LOCATION" for item in detections)

    tokenizer = Tokenizer()
    tokenizer.initialize_session()
    tokenized, mapping = tokenizer.tokenize(GERMAN_TEXT, detections)
    for value in MASKED_VALUES:
        assert value not in tokenized
    restored = RestoreEngine().restore_with_paths(tokenized, mapping)
    assert restored == GERMAN_TEXT
