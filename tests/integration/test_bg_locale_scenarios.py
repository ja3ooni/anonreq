"""bg-BG locale: detection, masking and exact restore through the real
DetectionStage and TokenizationStage. Synthetic, generator-built values only.

Presidio is replaced by an English-model stand-in that returns nothing for
Cyrillic text: there is no Bulgarian spaCy pipeline, and names/addresses are
out of scope for this bundle.
"""

# Bulgarian test text is Cyrillic on purpose.
# ruff: noqa: RUF001

from __future__ import annotations

import datetime as dt
import re
from typing import Any

import pytest

from anonreq.detection.exclusion_list import ExclusionList
from anonreq.detection.pipeline import load_enterprise_recognizers
from anonreq.detection.regex_detector import RegexDetector
from anonreq.detection.span_arbiter import SpanArbiter
from anonreq.locale.checksum import ChecksumValidatorRegistry
from anonreq.locale.checksums.bulgaria import (
    egn_valid,
    eik_valid,
    generate_egn,
    generate_eik,
    generate_iban_bg,
    generate_lnch,
    lnch_valid,
)
from anonreq.locale.merger import RecognizerMerger
from anonreq.locale.presidio_language import locale_metric_label, plan_presidio_languages
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

EGN = generate_egn(dt.date(1985, 3, 15), serial=456)
EGN_2000S = generate_egn(dt.date(2004, 7, 1), serial=17)
LNCH = generate_lnch("200300400")
EIK = generate_eik("20406080")
EIK_BRANCH = generate_eik("30507090", "002")
IBAN = generate_iban_bg("SYNT", "12345678901234")
IBAN_SPACED = " ".join(IBAN[i:i + 4] for i in range(0, len(IBAN), 4))


def _flip_last(value: str) -> str:
    return value[:-1] + str((int(value[-1]) + 1) % 10)


class _NoNer:
    async def analyze_text_nodes(self, nodes: list[dict[str, Any]], **_kw: Any) -> list[Any]:
        return [[] for _ in nodes]


class _Cache:
    async def store_mapping(self, *_a: Any, **_k: Any) -> bool:
        return True


async def _run(text: str, locales: tuple[str, ...] = ("bg-BG",)) -> ProcessingContext:
    checksums = ChecksumValidatorRegistry()
    registry = LocaleRegistry(checksum_registry=checksums)
    bundles = [registry.get(code) for code in locales]
    assert all(bundles)
    merged = RecognizerMerger(registry.get("en")).merge(bundles)
    stage = DetectionStage(
        RegexDetector(), _NoNer(), SpanArbiter(), ExclusionList(),
        checksum_registry=checksums,
        enterprise_recognizers=load_enterprise_recognizers(),
        mnpi_recognizers=load_mnpi_recognizers(config_path="config/mnpi_recognizers.yaml"),
    )
    ctx = ProcessingContext(
        request_id="bg", context_id="bg",
        classification_result={"action": "ANONYMIZE"},
        original_request={"model": "m", "messages": [{"role": "user", "content": text}]},
        merged_recognizers=merged,
        locale_bundles=bundles,
    )
    await stage.execute(ctx)
    assert not ctx.errors, ctx.errors
    await TokenizationStage(Tokenizer(), _Cache()).execute(ctx)
    assert not ctx.errors, ctx.errors
    assert ctx.transformed_request is not None
    return ctx


def _masked(ctx: ProcessingContext) -> str:
    return ctx.transformed_request["messages"][0]["content"]  # type: ignore[index]


def _types_by_value(ctx: ProcessingContext, text: str) -> dict[str, str]:
    return {
        text[int(d["start"]):int(d["end"])]: str(d["entity_type"])
        for d in ctx.detections or []
    }


SCENARIOS: dict[str, tuple[str, dict[str, str], list[str]]] = {
    # text, {value: expected entity type}, words that must stay readable
    "cyrillic_client_file": (
        f"Моля, обработи досието на клиент с ЕГН {EGN}, ЛНЧ: {LNCH} и "
        f"лична карта № AB1234567. Фирма ЕИК {EIK}, клон БУЛСТАТ {EIK_BRANCH}. "
        f"Плащане по IBAN {IBAN_SPACED}, тел. +359 88 123 4567.",
        {
            EGN: "EGN", LNCH: "LNCH", "AB1234567": "BG_ID_CARD", EIK: "EIK",
            EIK_BRANCH: "EIK", IBAN_SPACED: "IBAN_BG", "+359 88 123 4567": "PHONE",
        },
        ["Моля", "обработи", "досието", "ЕГН", "ЛНЧ", "лична карта", "ЕИК", "БУЛСТАТ",
         "IBAN", "тел."],
    ),
    "old_id_card_and_sofia_landline": (
        f"Лична карта № 645123456, издадена на лице с ЕГН {EGN_2000S}. "
        "Офис: 02 987 6543, мобилен 0888 123 456.",
        {
            "645123456": "BG_ID_CARD", EGN_2000S: "EGN",
            "02 987 6543": "PHONE", "0888 123 456": "PHONE",
        },
        ["Лична карта", "издадена", "Офис", "мобилен"],
    ),
    "mixed_bg_en": (
        f"Please draft a reply to Иван about his account. EGN {EGN}, "
        f"IBAN {IBAN}, VAT BG{EIK}, phone +359 2 987 6543. "
        f"Благодаря, екипът.",
        {EGN: "EGN", IBAN: "IBAN_BG", f"BG{EIK}": "EIK", "+359 2 987 6543": "PHONE"},
        ["Please draft a reply", "account", "EGN", "IBAN", "VAT", "phone",
         "Благодаря, екипът."],
    ),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("name", list(SCENARIOS))
async def test_bg_scenario_masks_and_restores_exactly(name: str) -> None:
    text, expected, keep = SCENARIOS[name]
    ctx = await _run(text)
    masked = _masked(ctx)
    clear = _TOKEN.sub(" ", masked)
    types = _types_by_value(ctx, text)
    for value, entity_type in expected.items():
        assert value not in clear, f"{name}: {value!r} left in clear: {masked}"
        if entity_type == "PHONE":
            # PHONE_BG and the universal PHONE_NUMBER tie on the same span.
            assert types.get(value) in {"PHONE_BG", "PHONE_NUMBER"}, (name, value, types)
        else:
            assert types.get(value) == entity_type, (name, value, types)
    # Every masked value comes back, so nothing was flagged irreversible.
    assert all(d.get("reversible") for d in ctx.detections or []), ctx.detections
    for word in keep:
        assert word in clear, f"{name}: false positive on {word!r}: {masked}"
    restored = Restorer.restore_text(masked, ctx.token_mappings or {})
    assert restored == text
    assert restored.encode("utf-8") == text.encode("utf-8")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "value", "entity_type"),
    [
        (f"ЕГН {_flip_last(EGN)} е сгрешен.", _flip_last(EGN), "EGN_UNVERIFIED"),
        # No label, but the digits still encode a plausible birth date.
        (f"Номер {_flip_last(EGN)} за проверка.", _flip_last(EGN), "EGN_UNVERIFIED"),
        (f"ЛНЧ № {_flip_last(LNCH)} е сгрешен.", _flip_last(LNCH), "LNCH_UNVERIFIED"),
        (f"ЕИК: {_flip_last(EIK)} е сгрешен.", _flip_last(EIK), "EIK_UNVERIFIED"),
        (f"БУЛСТАТ {_flip_last(EIK_BRANCH)}.", _flip_last(EIK_BRANCH), "EIK_UNVERIFIED"),
        (f"Сметка {IBAN.lower()} за плащане.", IBAN.lower(), "IBAN_BG_UNVERIFIED"),
        (f"Сметка {_flip_last(IBAN)} за плащане.", _flip_last(IBAN), "IBAN_BG_UNVERIFIED"),
    ],
)
async def test_checksum_failures_are_masked_unverified(
    text: str, value: str, entity_type: str
) -> None:
    ctx = await _run(text)
    masked = _masked(ctx)
    assert value not in masked, masked
    detection = next(
        d for d in ctx.detections or [] if text[d["start"]:d["end"]] == value
    )
    if entity_type != "IBAN_BG_UNVERIFIED" or value != _flip_last(IBAN):
        assert detection["entity_type"] == entity_type, detection
    else:
        # An uppercase IBAN with a bad checksum is also caught by the
        # universal IBAN_UNVERIFIED pattern; either label masks it.
        assert detection["entity_type"] in {"IBAN_BG_UNVERIFIED", "IBAN_UNVERIFIED"}
    assert float(detection["score"]) <= 0.6
    assert Restorer.restore_text(masked, ctx.token_mappings or {}) == text


@pytest.mark.parametrize("value", ["1234567890", "1000012345", "123456789", "1234567890123"])
def test_false_positive_fixtures_fail_every_checksum(value: str) -> None:
    assert not egn_valid(value)
    assert not lnch_valid(value)
    assert not eik_valid(value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "Поръчка № 1234567890 е изпратена.",
        "Фактура 1000012345, сума 1 500,00 лв.",
        "Заявка 123456789 и партида 1234567890123.",
        "Срещата е на 15.03.2024 г. в 10:30 ч.",
        "Дата на доставка: 2024-03-15.",
        "Сума: 1234567,89 лв.",
    ],
)
async def test_no_false_positives_on_order_numbers_and_dates(text: str) -> None:
    ctx = await _run(text)
    bg_types = {
        "EGN", "EGN_UNVERIFIED", "LNCH", "LNCH_UNVERIFIED", "EIK", "EIK_UNVERIFIED",
        "IBAN_BG", "IBAN_BG_UNVERIFIED", "BG_ID_CARD", "PHONE_BG",
    }
    found = [d for d in ctx.detections or [] if d["entity_type"] in bg_types]
    assert not found, found
    if "15.03.2024" not in text:  # DATE_DE from the universal bundle masks dd.mm.yyyy
        assert _masked(ctx) == text


@pytest.mark.asyncio
async def test_id_card_needs_context() -> None:
    ctx = await _run("Код на продукта AB1234567 и артикул 645123456.")
    assert not [d for d in ctx.detections or [] if d["entity_type"] == "BG_ID_CARD"]


@pytest.mark.asyncio
async def test_labels_are_not_masked_as_tickers() -> None:
    ctx = await _run(f"EGN {EGN}, EIK {EIK}, LNCH {LNCH}, GSM +359 88 765 4321")
    masked = _masked(ctx)
    for label in ("EGN", "EIK", "LNCH", "GSM"):
        assert f"{label} " in masked, masked


def test_bg_locale_falls_back_to_english_presidio_and_is_counted() -> None:
    registry = LocaleRegistry("config/locales")
    plan = plan_presidio_languages([registry.get("bg-BG")], ("en", "de"))
    assert plan.languages == ("en",)
    assert plan.unsupported_locales == ("bg-BG",)
    assert locale_metric_label("bg-bg") == "bg-BG"
