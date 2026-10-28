"""QA demo scenarios 1-5 (de-DE), regex/MNPI/enterprise detection plus a
Presidio stand-in that returns what the German model returned in QA's run
(/workspace/anonreq-qa/demo-scenarios.md, PR #4 column). Synthetic data only.

PASS = every PII value masked, no false positives on the listed words,
exact restore.
"""

from __future__ import annotations

import re
from typing import Any

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
from anonreq.tokenization.restorer import Restorer
from anonreq.tokenization.tokenizer import Tokenizer

try:
    from anonreq.detection.pipeline import load_mnpi_recognizers
except ImportError:  # pragma: no cover
    from anonreq.detection.recognizers.mnpi import load_mnpi_recognizers  # type: ignore

_TOKEN = re.compile(r"\[[A-Z][A-Z_]*_\d+\]")

# (text, ner spans as (substring, type), PII that must be masked, words that must stay)
SCENARIOS: dict[str, tuple[str, list[tuple[str, str]], list[str], list[str]]] = {
    "1_iban_name": (
        "IBAN DE89370400440532013000 für Anna prüfen",
        [],  # German model missed "Anna" in QA's run
        ["DE89370400440532013000", "Anna"],
        ["IBAN", "für", "prüfen"],
    ),
    "1_iban_name_en_model": (
        "IBAN DE89370400440532013000 für Anna prüfen",
        [("Anna prüfen", "PERSON")],  # English model: span too wide
        ["DE89370400440532013000", "Anna"],
        ["IBAN", "prüfen"],
    ),
    "2_versicherung": (
        "Schadensmeldung: Versicherte Frau Katharina Brenner, KVNR A123456780, "
        "wohnhaft Lindenallee 14, 50667 Köln, meldet einen Wasserschaden vom "
        "12.03.2026. Bitte Regulierung prüfen.",
        [("Katharina Brenner", "PERSON"), ("Lindenallee 14", "LOCATION")],
        ["Katharina", "Brenner", "A123456780", "Lindenallee", "50667", "Köln", "12.03.2026"],
        ["KVNR", "Schadensmeldung", "Wasserschaden", "Regulierung"],
    ),
    "3_hr_cv": (
        "Lebenslauf: Maximilian Hoffmann, geboren am 14.07.1991, Telefon +49 151 23456789, "
        "E-Mail max.hoffmann@beispiel-mail.example, Personalausweis L01X00T471. "
        "Bitte fasse die Berufserfahrung zusammen.",
        [("Maximilian Hoffmann", "PERSON")],
        ["Maximilian", "Hoffmann", "14.07.1991", "+49", "151 23456789",
         "max.hoffmann@beispiel-mail.example", "L01X00T471"],
        ["Telefon", "Berufserfahrung", "Personalausweis"],
    ),
    "4_energie": (
        "Störung am Standort UW-NORD-0417: Trafo ausgefallen. Monteur Jonas Becker "
        "erreichbar unter 0171 9876543. Abrechnung über Kundenkonto 4711-0815-22. "
        "Bitte Einsatzbericht entwerfen.",
        [("Jonas Becker", "PERSON")],
        ["UW-NORD-0417", "NORD", "0417", "Jonas", "Becker", "0171 9876543", "4711-0815-22"],
        ["Standort", "Trafo", "Monteur", "Kundenkonto", "Einsatzbericht"],
    ),
    "5_tool_call": (
        '{"api_key": "sk-QaDemo0Synthetic1Key2Xyz3Abc4", "name": "Sophie Wagner", '
        '"email": "sophie.wagner@beispiel-mail.example", "iban": "DE89370400440532013000", '
        '"telefon": "+49 30 12345678", "strasse": "Goethestraße 7, 10115 Berlin"}',
        [("Sophie Wagner", "PERSON"), ("Goethestraße", "LOCATION"), ("Berlin", "LOCATION")],
        ["sk-QaDemo0Synthetic1Key2Xyz3Abc4", "Sophie", "Wagner",
         "sophie.wagner@beispiel-mail.example", "DE89370400440532013000", "+49",
         "30 12345678", "Goethestraße 7", "10115", "Berlin"],
        ["api_key", "telefon", "strasse"],
    ),
    "5b_tool_call_no_key": (
        '{"name": "Sophie Wagner", "email": "sophie.wagner@beispiel-mail.example", '
        '"telefon": "+49 30 12345678", "strasse": "Goethestraße 7, 10115 Berlin"}',
        [("Sophie Wagner", "PERSON"), ("Goethestraße", "LOCATION"), ("Berlin", "LOCATION")],
        ["Sophie", "Wagner", "sophie.wagner@beispiel-mail.example", "+49",
         "30 12345678", "Goethestraße 7", "10115", "Berlin"],
        ["telefon", "strasse"],
    ),
    "crm_instruction": (
        "Lege den Kunden im CRM an.",
        [],
        [],
        ["CRM", "Kunden"],
    ),
}


class _GermanNer:
    def __init__(self, spans: list[tuple[str, str]]) -> None:
        self._spans = spans

    async def analyze_text_nodes(self, nodes: list[dict[str, Any]], **_kw: Any) -> list[Any]:
        out = []
        for node in nodes:
            value = node["value"]
            found = []
            for text, entity in self._spans:
                start = value.find(text)
                if start >= 0:
                    found.append({"entity_type": entity, "start": start,
                                  "end": start + len(text), "score": 0.85})
            out.append(found)
        return out


class _Cache:
    async def store_mapping(self, *_a: Any, **_k: Any) -> bool:
        return True


async def _run(text: str, ner: list[tuple[str, str]]) -> tuple[str, dict[str, str]]:
    checksums = ChecksumValidatorRegistry()
    registry = LocaleRegistry(checksum_registry=checksums)
    merged = RecognizerMerger(registry.get("en")).merge([registry.get("de-DE")])
    stage = DetectionStage(
        RegexDetector(), _GermanNer(ner), SpanArbiter(), ExclusionList(),
        checksum_registry=checksums,
        enterprise_recognizers=load_enterprise_recognizers(),
        mnpi_recognizers=load_mnpi_recognizers(config_path="config/mnpi_recognizers.yaml"),
    )
    ctx = ProcessingContext(
        request_id="scenario", context_id="scenario",
        classification_result={"action": "ANONYMIZE"},
        original_request={"model": "m", "messages": [{"role": "user", "content": text}]},
        merged_recognizers=merged,
    )
    await stage.execute(ctx)
    assert not ctx.errors, ctx.errors
    await TokenizationStage(Tokenizer(), _Cache()).execute(ctx)
    assert not ctx.errors, ctx.errors
    assert ctx.transformed_request is not None
    return ctx.transformed_request["messages"][0]["content"], ctx.token_mappings or {}


@pytest.mark.asyncio
@pytest.mark.parametrize("name", list(SCENARIOS))
async def test_demo_scenario(name: str) -> None:
    text, ner, pii, keep = SCENARIOS[name]
    masked, mapping = await _run(text, ner)
    clear = _TOKEN.sub(" ", masked)
    for value in pii:
        assert value not in clear, f"{name}: {value!r} left in clear: {masked}"
    for word in keep:
        assert word in clear, f"{name}: false positive on {word!r}: {masked}"
    assert "+[" not in masked
    if "sk-" not in text:
        assert Restorer.restore_text(masked, mapping) == text


@pytest.mark.asyncio
async def test_anna_has_exact_boundaries() -> None:
    text = "IBAN DE89370400440532013000 für Anna prüfen"
    masked, mapping = await _run(text, [("Anna prüfen", "PERSON")])
    assert masked.endswith(" prüfen")
    assert "für [" in masked
    name_tokens = [t for t, v in mapping.items() if v == "Anna"]
    assert len(name_tokens) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value",
    [
        "DE89370400440532013001",  # one wrong digit: checksum fails
        "de89370400440532013000",  # lowercase
        "DE89 3704 0044 0532 0130 01",
    ],
)
async def test_iban_masked_on_format(value: str) -> None:
    masked, _ = await _run(f"Bitte auf {value} überweisen", [])
    assert value not in masked


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["86095742719", "86095742710"])  # valid / wrong digit
async def test_steuer_id_masked_on_format(value: str) -> None:
    masked, _ = await _run(f"Steuer-ID {value} liegt vor", [])
    assert value not in masked


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "Postleitzahl 10115 ist Berlin-Mitte.",
        "Rechnung vom 03.05.2024 über 12 EUR.",
        "Version 3.11.4 ist installiert.",
        "Kundenkonto 4711-0815-22 belastet.",
        "Wir haben 10000 Mitarbeiter.",
    ],
)
async def test_no_phone_false_positives(text: str) -> None:
    checksums = ChecksumValidatorRegistry()
    registry = LocaleRegistry(checksum_registry=checksums)
    merged = RecognizerMerger(registry.get("en")).merge([registry.get("de-DE")])
    detector = RegexDetector()
    patterns = detector.patterns_from_entity_configs(list(merged.entity_configs.values()))
    found = detector.detect(text, extra_patterns=patterns)
    assert not [d for d in found if d["entity_type"] == "PHONE_NUMBER"], found
    if "Mitarbeiter" in text:
        assert not found, found


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "number", ["+49 30 1234567", "+49 170 1234567", "0171 9876543", "+1-555-123-4567",
               "555-123-4567", "(030) 1234567", "+49 (0)30 1234567"]
)
async def test_phone_numbers_include_plus(number: str) -> None:
    masked, mapping = await _run(f"Ruf an: {number} bitte", [])
    assert masked.startswith("Ruf an: [")
    assert masked.endswith("] bitte")
    assert number in mapping.values()
