# ruff: noqa: E501, PT018
"""QA regression tests for detection/tokenization bugs (synthetic data only).

Marked xfail(strict=True): they document known bugs and will XPASS -> fail
once a fix lands, prompting removal of the marker.
"""
from __future__ import annotations

import copy
import json

import pytest

from anonreq.tokenization.restorer import Restorer
from anonreq.tokenization.tokenizer import Tokenizer
from tests.qa_regression.conftest import user

FAKE_KEY = "sk-" + "QaSynthetic0Key1Abc2Def3Ghi4"
FAKE_IBAN = "DE89370400440532013000"  # public documentation example IBAN


def _content(ctx, i=0):
    return ctx.transformed_request["messages"][i]["content"]


@pytest.mark.xfail(strict=True, reason="BUG: overlapping/duplicate spans double-replaced by Tokenizer")
def test_tokenizer_overlapping_spans_restore_exactly():
    tok = Tokenizer()
    tok.initialize_session()
    text = f"Konto {FAKE_IBAN} Ende"
    out, mapping = tok.tokenize(text, [
        {"entity_type": "IBAN_DE", "start": 6, "end": 28, "score": 1.0},
        {"entity_type": "MNPI_TICKER", "start": 10, "end": 14, "score": 1.0},
    ])
    assert Restorer.restore_text(out, mapping) == text


@pytest.mark.xfail(strict=True, reason="BUG: API_KEY + ENTERPRISE_API_KEY on same span eat following text")
async def test_api_key_duplicate_span_does_not_corrupt_prompt(de_pipeline):
    text = f"Mein Key ist {FAKE_KEY} bitte nicht teilen"
    ctx = await de_pipeline(user(text))
    masked = _content(ctx)
    assert FAKE_KEY not in masked
    assert masked.endswith(" bitte nicht teilen")


@pytest.mark.xfail(strict=True, reason="BUG: PHONE_NUMBER matches postcodes")
@pytest.mark.parametrize("text", ["Postleitzahl 10115 ist Berlin-Mitte.", "Lieferung nach 80331 München."])
async def test_phone_no_false_positive_on_postcode(de_pipeline, text):
    ctx = await de_pipeline(user(text))
    assert not [d for d in ctx.detections or [] if d["entity_type"] == "PHONE_NUMBER"]


@pytest.mark.xfail(strict=True, reason="BUG: PHONE_NUMBER matches dates / version numbers")
@pytest.mark.parametrize("text", ["Rechnung vom 03.05.2024 über 12 EUR.", "Version 3.11.4 ist installiert."])
async def test_phone_no_false_positive_on_dates(de_pipeline, text):
    ctx = await de_pipeline(user(text))
    assert not [d for d in ctx.detections or [] if d["entity_type"] == "PHONE_NUMBER"]


@pytest.mark.xfail(strict=True, reason="BUG: leading '+' of international number left outside the token")
async def test_phone_plus_prefix_inside_token(de_pipeline):
    ctx = await de_pipeline(user("Ruf an: +49 30 1234567"))
    masked = _content(ctx)
    assert "+[" not in masked and "+49" not in masked


async def test_original_request_not_mutated(de_pipeline):
    req = user("Mail an lea.weber@beispiel-mail.example bitte")
    snapshot = copy.deepcopy(req)
    ctx = await de_pipeline(req)
    assert "[EMAIL_ADDRESS_" in _content(ctx)
    assert req == snapshot


@pytest.mark.xfail(strict=True, reason="BUG: IBAN patterns are uppercase-only")
async def test_lowercase_iban_detected(de_pipeline):
    ctx = await de_pipeline(user(f"iban {FAKE_IBAN.lower()} bitte"))
    assert FAKE_IBAN.lower() not in _content(ctx)


async def test_tool_call_arguments_are_tokenized(de_pipeline):
    args = json.dumps({"email": "sophie.wagner@beispiel-mail.example", "iban": FAKE_IBAN})
    req = {"model": "gpt-4o", "messages": [
        {"role": "user", "content": "Lege den Kunden an."},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "crm", "arguments": args}}]},
    ]}
    ctx = await de_pipeline(req)
    assert ctx.detections, "precondition: entities detected in tool args"
    forwarded = ctx.transformed_request["messages"][1]["tool_calls"][0]["function"]["arguments"]
    assert "sophie.wagner@beispiel-mail.example" not in forwarded
    assert FAKE_IBAN not in forwarded
