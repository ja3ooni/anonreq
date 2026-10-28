"""Negotiated locale must be the Presidio language, and failures stay closed."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anonreq.detection.exclusion_list import ExclusionList
from anonreq.detection.presidio_client import (
    PresidioError,
    PresidioUnsupportedLanguageError,
)
from anonreq.detection.regex_detector import RegexDetector
from anonreq.detection.span_arbiter import SpanArbiter
from anonreq.exceptions import PresidioLanguageUnsupportedError, global_exception_handler
from anonreq.locale.merger import RecognizerMerger
from anonreq.locale.negotiator import LocaleNegotiator
from anonreq.locale.presidio_language import (
    plan_presidio_languages,
    presidio_language_from_locale,
)
from anonreq.locale.registry import LocaleRegistry
from anonreq.logging_config import ALLOWLIST
from anonreq.models.processing_context import ProcessingContext
from anonreq.monitoring.metrics import fail_secure_events, presidio_unsupported_locales
from anonreq.pipeline import detection as detection_module
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


def test_presidio_languages_setting_parses_allowlist() -> None:
    from anonreq.config import Settings

    base = {
        "API_KEY": "a" * 32,
        "VALKEY_URL": "redis://localhost:6379/0",
        "PRESIDIO_URL": "http://localhost:5001",
    }
    assert Settings(**base).configured_presidio_languages() == ("en",)
    both = Settings(**base, PRESIDIO_LANGUAGES="de, en, de")
    assert both.configured_presidio_languages() == ("de", "en")
    with pytest.raises(ValueError, match="ANONREQ_PRESIDIO_LANGUAGES"):
        Settings(**base, PRESIDIO_LANGUAGES="de,!!!")


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


def test_allowlist_uses_every_bundle_and_falls_back_for_the_rest(negotiated) -> None:
    negotiator, merger = negotiated
    french, _ = negotiator.negotiate("fr-FR")
    merged = merger.merge(french)
    assert merged.source_locales[0] == "en"
    french_plan = plan_presidio_languages(french, ("en",))
    assert french_plan.languages == ("en",)
    assert french_plan.unsupported_locales == ("fr-FR",)

    both, _ = negotiator.negotiate("fr-FR, de-DE")
    both_plan = plan_presidio_languages(both, ("en", "de", "fr"))
    assert both_plan.languages == ("fr", "de")
    assert both_plan.unsupported_locales == ()

    german_only, _ = negotiator.negotiate("de-DE")
    configured = plan_presidio_languages(german_only, ("en", "de"))
    assert configured.languages == ("de",)
    assert configured.unsupported_locales == ()
    assert plan_presidio_languages(None, ("en",)).languages == ("en",)


def _stage(
    presidio_client: MagicMock,
    presidio_languages: tuple[str, ...] = ("en",),
) -> DetectionStage:
    regex = MagicMock()
    regex.patterns_from_entity_configs.return_value = {}
    regex.detect.return_value = []
    return DetectionStage(
        regex_detector=regex,
        presidio_client=presidio_client,
        span_arbiter=SpanArbiter(),
        exclusion_list=ExclusionList(),
        presidio_languages=presidio_languages,
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

    result = await _stage(presidio, ("en", "de")).execute(ctx)

    assert not result.has_errors()
    presidio.analyze_text_nodes.assert_awaited_once()
    kwargs = presidio.analyze_text_nodes.await_args.kwargs
    assert kwargs["language"] == "de"
    assert kwargs["entities"] is not None
    assert "PERSON" in kwargs["entities"]
    assert "LOCATION" in kwargs["entities"]


async def test_unconfigured_locales_use_english_and_count_metric(negotiated) -> None:
    negotiator, _merger = negotiated
    bundles, _ = negotiator.negotiate("fr-FR, es, ar")
    presidio = MagicMock()
    presidio.analyze_text_nodes = AsyncMock(return_value=[[]])
    ctx = _ctx(bundles)
    counters = {
        code: presidio_unsupported_locales.labels(locale=code)._value.get()
        for code in ("fr-FR", "es", "ar")
    }

    result = await _stage(presidio, ("en",)).execute(ctx)

    assert not result.has_errors()
    languages = [
        call.kwargs["language"] for call in presidio.analyze_text_nodes.await_args_list
    ]
    assert languages == ["en"]
    for code, before in counters.items():
        assert presidio_unsupported_locales.labels(locale=code)._value.get() == before + 1


async def test_configured_languages_are_all_sent(negotiated) -> None:
    negotiator, _merger = negotiated
    bundles, _ = negotiator.negotiate("fr-FR, de-DE")
    presidio = MagicMock()
    presidio.analyze_text_nodes = AsyncMock(return_value=[[]])

    await _stage(presidio, ("en", "de", "fr")).execute(_ctx(bundles))

    languages = [
        call.kwargs["language"] for call in presidio.analyze_text_nodes.await_args_list
    ]
    assert languages == ["fr", "de"]


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
    assert not isinstance(result.errors[-1], PresidioLanguageUnsupportedError)
    assert presidio.analyze_text_nodes.await_args.kwargs["language"] == "en"


def test_presidio_language_is_log_allowlisted() -> None:
    assert "presidio_language" in ALLOWLIST


async def test_german_request_does_not_fall_back_to_english(negotiated) -> None:
    negotiator, merger = negotiated
    bundles, _ = negotiator.negotiate("de-DE")
    presidio = MagicMock()
    presidio.analyze_text_nodes = AsyncMock(
        side_effect=PresidioUnsupportedLanguageError("de"),
    )
    ctx = _ctx(bundles)
    ctx.merged_recognizers = merger.merge(bundles)
    prompt = ctx.text_nodes[0]["value"]
    counter = fail_secure_events.labels(
        tenant_id="tenant-a",
        failure_type="presidio_unsupported_language",
    )
    before = counter._value.get()

    with patch.object(detection_module.logger, "warning") as warning:
        result = await _stage(presidio, ("en", "de")).execute(ctx)

    assert result.detections is None
    assert presidio.analyze_text_nodes.await_count == 1
    assert presidio.analyze_text_nodes.await_args.kwargs["language"] == "de"
    error = result.errors[-1]
    assert isinstance(error, PresidioLanguageUnsupportedError)
    assert error.language == "de"
    assert error.status_code == 503
    assert "Refusing to fall back to English" in error.message
    assert prompt not in error.message
    matched = [
        call for call in warning.call_args_list
        if call.args and call.args[0] == "detection.presidio_language_unsupported"
    ]
    assert len(matched) == 1
    assert matched[0].kwargs["presidio_language"] == "de"
    assert prompt not in str(matched[0])
    assert counter._value.get() == before + 1


async def test_unsupported_language_http_body_names_language_only() -> None:
    class _State:
        request_id = "req-de"

    class _Request:
        def __init__(self) -> None:
            self.state = _State()
            self.headers: dict[str, str] = {}

    exc = PresidioLanguageUnsupportedError("de", request_id="req-de")
    response = await global_exception_handler(_Request(), exc)  # type: ignore[arg-type]
    payload = json.loads(response.body)
    assert response.status_code == 503
    assert payload["error"]["type"] == "presidio_unsupported_language"
    assert payload["error"]["code"] == "presidio_unsupported_language"
    assert payload["error"]["message"] == (
        "Presidio analyzer does not support language 'de'. "
        "Refusing to fall back to English."
    )
    assert "Hauptstraße" not in response.body.decode()


def test_chat_route_surfaces_unsupported_language() -> None:
    from anonreq.routing.chat import _raise_for_pipeline_errors

    ctx = ProcessingContext(request_id="req-de")
    ctx.fail_secure(PresidioLanguageUnsupportedError("de", request_id="req-de"))
    with pytest.raises(PresidioLanguageUnsupportedError) as exc_info:
        _raise_for_pipeline_errors(ctx)
    assert exc_info.value.status_code == 503
    assert "Hauptstraße" not in exc_info.value.message


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


def test_german_recognizer_yaml_loads_every_pattern() -> None:
    from presidio_analyzer import RecognizerRegistry

    registry = RecognizerRegistry()
    registry.add_recognizers_from_yaml("docker/presidio/german_recognizers.yaml")
    by_name = {recognizer.name: recognizer for recognizer in registry.recognizers}
    assert "German Street Line" in by_name
    assert "German Postal City" in by_name
    text = "Hans Müller, Hauptstraße 12, 60311 Frankfurt"
    covered = []
    for recognizer in by_name.values():
        for hit in recognizer.analyze(text, entities=["LOCATION"]):
            covered.append(text[hit.start:hit.end])
    assert "Hauptstraße 12" in covered
    assert "60311 Frankfurt" in covered


def test_regex_detector_does_not_mask_german_name_or_street() -> None:
    """Names and street addresses are a Presidio concern, not the regex bundle."""
    text = "Hans Müller, Hauptstraße 12, 60311 Frankfurt"
    hits = RegexDetector().detect(text)
    covered = {text[hit["start"]:hit["end"]] for hit in hits}
    assert "Hans Müller" not in covered
    assert "Hauptstraße 12" not in covered
    assert "60311 Frankfurt" not in covered
