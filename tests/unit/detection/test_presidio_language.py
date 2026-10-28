"""Negotiated locale must be the Presidio language, and failures stay closed."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from anonreq.detection.exclusion_list import ExclusionList
from anonreq.detection.presidio_client import PresidioError
from anonreq.detection.regex_detector import RegexDetector
from anonreq.detection.span_arbiter import SpanArbiter
from anonreq.locale.merger import RecognizerMerger
from anonreq.locale.negotiator import LocaleNegotiator
from anonreq.locale.presidio_language import (
    presidio_language_from_bundles,
    presidio_language_from_locale,
)
from anonreq.locale.registry import LocaleRegistry
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.base import PipelineStage
from anonreq.pipeline.detection import DetectionStage
from anonreq.pipeline.manager import PipelineManager

_ENABLE_GERMAN = Path(__file__).resolve().parents[3] / "docker" / "presidio" / "enable_german.py"


def _load_enable_german():
    spec = importlib.util.spec_from_file_location("enable_german", _ENABLE_GERMAN)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def negotiated():
    registry = LocaleRegistry("config/locales")
    negotiator = LocaleNegotiator(registry)
    merger = RecognizerMerger(registry.get("en"))
    return negotiator, merger


def test_locale_codes_map_to_presidio_languages() -> None:
    assert presidio_language_from_locale("de-DE") == "de"
    assert presidio_language_from_locale("de_DE") == "de"
    assert presidio_language_from_locale("pt-BR") == "pt"
    assert presidio_language_from_locale("fr-FR") == "fr"
    assert presidio_language_from_locale("en") == "en"
    assert presidio_language_from_locale("es") == "es"
    assert presidio_language_from_locale(None) == "en"
    assert presidio_language_from_locale("") == "en"
    assert presidio_language_from_locale("??") == "en"


def test_first_negotiated_bundle_wins_over_sorted_merge(negotiated) -> None:
    negotiator, merger = negotiated
    bundles, _ = negotiator.negotiate("fr-FR")
    merged = merger.merge(bundles)
    # Merged source locales are sorted and always include universal "en",
    # which would hide fr-FR. Presidio must follow header order instead.
    assert merged.source_locales[0] == "en"
    assert presidio_language_from_bundles(bundles) == "fr"
    multi, _ = negotiator.negotiate("fr-FR, de-DE")
    assert presidio_language_from_bundles(multi) == "fr"
    assert presidio_language_from_bundles(None) == "en"
    assert presidio_language_from_bundles([]) == "en"


def _stage(presidio_client: MagicMock) -> DetectionStage:
    regex = MagicMock()
    regex.patterns_from_entity_configs.return_value = {}
    regex.detect.return_value = []
    return DetectionStage(
        regex_detector=regex,
        presidio_client=presidio_client,
        span_arbiter=SpanArbiter(),
        exclusion_list=ExclusionList(),
    )


def _ctx(bundles) -> ProcessingContext:
    return ProcessingContext(
        request_id="req-lang",
        tenant_id="tenant-a",
        text_nodes=[
            {
                "path": "messages.0.content",
                "role": "user",
                "value": "Hans Müller, Hauptstraße 12, 60311 Frankfurt",
            }
        ],
        classification_result={"action": "ANONYMIZE"},
        locale_bundles=bundles,
    )


async def test_detection_passes_german_language(negotiated) -> None:
    negotiator, merger = negotiated
    bundles, _ = negotiator.negotiate("de-DE")
    presidio = MagicMock()
    presidio.analyze_text_nodes = AsyncMock(return_value=[[]])
    ctx = _ctx(bundles)
    ctx.merged_recognizers = merger.merge(bundles)

    result = await _stage(presidio).execute(ctx)

    assert not result.has_errors()
    presidio.analyze_text_nodes.assert_awaited_once()
    kwargs = presidio.analyze_text_nodes.await_args.kwargs
    assert kwargs["language"] == "de"
    assert kwargs["entities"] is not None
    assert "PERSON" in kwargs["entities"]
    assert "LOCATION" in kwargs["entities"]


async def test_detection_defaults_to_english_without_locale() -> None:
    presidio = MagicMock()
    presidio.analyze_text_nodes = AsyncMock(return_value=[[]])

    await _stage(presidio).execute(_ctx(None))

    assert presidio.analyze_text_nodes.await_args.kwargs["language"] == "en"


async def test_detection_fails_closed_when_presidio_errors() -> None:
    class Sentinel(PipelineStage):
        def __init__(self) -> None:
            super().__init__("Sentinel")
            self.called = False

        async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
            self.called = True
            return ctx

    presidio = MagicMock()
    presidio.analyze_text_nodes = AsyncMock(side_effect=PresidioError("HTTP 500"))
    sentinel = Sentinel()
    manager = PipelineManager()
    manager.register(_stage(presidio))
    manager.register(sentinel)

    result = await manager.run(_ctx(None))

    assert result.has_errors()
    assert result.detections is None
    assert sentinel.called is False
    assert presidio.analyze_text_nodes.await_args.kwargs["language"] == "en"


def test_image_patch_enables_german_recognizers() -> None:
    enable_german = _load_enable_german()
    source = "class Server:\n    def __init__(self):\n        self.engine = AnalyzerEngine()\n"
    patched = enable_german.patch_app_source(source)
    assert "supported_languages=['en', 'de']" in patched
    assert "conf/german_recognizers.yaml" in patched
    assert "AnalyzerEngine()" not in patched


def test_image_patch_refuses_unknown_app_layout() -> None:
    enable_german = _load_enable_german()
    with pytest.raises(RuntimeError, match="DevOps review"):
        enable_german.patch_app_source("self.engine = AnalyzerEngineProvider().create()\n")


def test_regex_detector_does_not_mask_german_name_or_street() -> None:
    """Names and street addresses are a Presidio concern, not the regex bundle."""
    text = "Hans Müller, Hauptstraße 12, 60311 Frankfurt"
    hits = RegexDetector().detect(text)
    covered = {text[hit["start"]:hit["end"]] for hit in hits}
    assert "Hans Müller" not in covered
    assert "Hauptstraße 12" not in covered
    assert "60311 Frankfurt" not in covered
