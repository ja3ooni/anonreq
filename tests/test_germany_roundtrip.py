"""End-to-end anonymize → forward → restore for German identifiers.

Uses the same detection/tokenize path as production without importing the
HTTP pipeline (httpx import is extremely slow in some local environments).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

from anonreq.locale.checksums.germany import generate_iban_de, generate_steuer_id
from anonreq.services.audit_export import safe_anonymization_row
from anonreq.tokenization.restorer import Restorer
from anonreq.tokenization.tokenizer import Tokenizer
from tests.test_germany_pack import _detect_de


def test_germany_anonymize_forward_restore_roundtrip() -> None:
    steuer = generate_steuer_id("2695437180")
    iban = generate_iban_de("37040044", "0532013000")
    email = "anna.schmidt@sparkasse.de"
    api_key = "sk-" + ("z" * 24)
    content = (
        f"Bitte Kreditakte zu Steuer-ID {steuer} und IBAN {iban} "
        f"an {email} senden. API key {api_key} nicht teilen."
    )
    secrets = [steuer, iban, email, api_key]

    detections = _detect_de(content)
    assert detections, "expected German identifiers to be detected"

    tokenizer = Tokenizer()
    tokenizer.initialize_session()
    tokenizer._seed = 0
    forwarded, mapping = tokenizer.tokenize(content, detections)
    for secret in secrets:
        assert secret not in forwarded, f"leaked {secret!r} in forwarded prompt"

    provider_echo = {
        "id": "chatcmpl-de",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": f"Verstanden: {forwarded}"},
                "finish_reason": "stop",
            }
        ],
    }
    restored = Restorer.restore_response(provider_echo, mapping)
    restored_text = restored["choices"][0]["message"]["content"]
    assert steuer in restored_text
    assert iban in restored_text or iban.replace(" ", "") in restored_text.replace(" ", "")
    assert email in restored_text
    assert api_key not in restored_text


def test_anonymization_export_row_omits_raw_values() -> None:
    raw_iban = "DE89370400440532013000"
    event = SimpleNamespace(
        timestamp=datetime(2026, 8, 14, 9, 0, tzinfo=UTC),
        request_id="req-de-1",
        tenant_id="default",
        operator_id="dpo1",
        provider="gpt-4o",
        decision="ANONYMIZE",
        metadata_json=json.dumps(
            {
                "entity_types": ["TAX_ID_DE", "IBAN_DE"],
                "entity_counts": {"TAX_ID_DE": 1, "IBAN_DE": 1},
                "token_count": 2,
                "locale": "de-DE",
                "model": "gpt-4o",
                "compliance_preset": "germany",
                "raw_iban": raw_iban,
            }
        ),
    )
    row = safe_anonymization_row(event)
    dumped = json.dumps(row)
    assert raw_iban not in dumped
    assert "raw_iban" not in row
    assert "TAX_ID_DE" in row["entity_types"]
    assert row["request_id"] == "req-de-1"
    assert row["compliance_preset"] == "germany"
