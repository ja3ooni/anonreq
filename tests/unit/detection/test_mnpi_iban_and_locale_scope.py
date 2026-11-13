"""MNPI ticker detection around spaced IBANs and bg-BG label exclusions.

Regressions from the #24 review: the spaced-IBAN skip must not hide real
ticker lists, and the Bulgarian label exclusions apply to bg-BG only.
"""

from __future__ import annotations

from typing import Any

import pytest

from anonreq.detection.pipeline import load_mnpi_recognizers
from anonreq.detection.recognizers.mnpi import MNPIRecognizer
from anonreq.locale.checksums.bulgaria import generate_iban_bg


def _recognizer() -> MNPIRecognizer:
    (recognizer,) = load_mnpi_recognizers(config_path="config/mnpi_recognizers.yaml")
    return recognizer


def _tickers(text: str, locales: list[str] | None = None) -> list[str]:
    hits: list[dict[str, Any]] = _recognizer().analyze(text, locales=locales)
    return [text[d["start"]:d["end"]] for d in hits if d["entity_type"] == "MNPI_TICKER"]


@pytest.mark.parametrize(
    ("text", "tickers"),
    [
        ("FY24 AAPL MSFT up", ["AAPL", "MSFT"]),
        ("Buy AB12 NVDA AMZN now", ["NVDA", "AMZN"]),
        ("FY24 AAPL MSFT TSLA NVDA AMZN guidance raised", ["AAPL", "MSFT", "TSLA", "NVDA", "AMZN"]),
    ],
)
@pytest.mark.parametrize("locales", [None, ["en"], ["de-DE"], ["bg-BG"]])
def test_iban_shaped_ticker_lists_keep_their_tickers(
    text: str, tickers: list[str], locales: list[str] | None
) -> None:
    found = _tickers(text, locales)
    for ticker in tickers:
        assert ticker in found, (text, found)


def test_iban_shaped_but_invalid_keeps_ticker() -> None:
    valid = " ".join(generate_iban_bg()[i:i + 4] for i in range(0, 22, 4))
    broken = valid[:-1] + str((int(valid[-1]) + 1) % 10)
    assert "SYNT" not in _tickers(f"IBAN {valid} bitte")
    assert "SYNT" in _tickers(f"IBAN {broken} bitte")


@pytest.mark.asyncio
async def test_ticker_list_stays_irreversible_through_detection_stage() -> None:
    from tests.integration.test_bg_locale_scenarios import _masked, _run

    ctx = await _run("FY24 AAPL MSFT TSLA NVDA AMZN guidance raised", locales=("en",))
    masked = _masked(ctx)
    restorable = set((ctx.token_mappings or {}).values())
    for ticker in ("AAPL", "MSFT", "TSLA", "NVDA", "AMZN"):
        assert ticker not in masked, masked
        assert not any(ticker in value for value in restorable), restorable


LABELS = ["BG", "EGN", "LNCH", "LNC", "EIK", "UIC", "GSM", "OOD", "EOOD", "VAT"]


@pytest.mark.parametrize("locales", [None, [], ["en"], ["de-DE"], ["de-DE", "en"]])
def test_bg_label_exclusions_do_not_apply_outside_bg(locales: list[str] | None) -> None:
    text = " ".join(f"{label} up" for label in LABELS)
    assert _tickers(text, locales) == LABELS


@pytest.mark.parametrize("locales", [["bg-BG"], ["BG-bg"], ["en", "bg-BG"]])
def test_bg_label_exclusions_apply_with_bg(locales: list[str]) -> None:
    text = " ".join(f"{label} up" for label in LABELS) + " AAPL"
    assert _tickers(text, locales) == ["AAPL"]
