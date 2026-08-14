"""Ticket adapter extracts Jira/Zendesk/generic bodies without calling a model."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "forward_ticket",
    ROOT / "examples" / "connectors" / "tickets" / "forward_ticket.py",
)
assert _SPEC and _SPEC.loader
_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mod)


def test_extract_jira_ticket() -> None:
    payload = json.loads(
        (ROOT / "examples/connectors/tickets/sample-jira.json").read_text(encoding="utf-8")
    )
    key, text = _mod.extract_ticket(payload)
    assert key == "BANK-1042"
    assert "26954371802" in text
    assert "DE89370400440532013000" in text


def test_extract_zendesk_ticket() -> None:
    payload = json.loads(
        (ROOT / "examples/connectors/tickets/sample-zendesk.json").read_text(encoding="utf-8")
    )
    key, text = _mod.extract_ticket(payload)
    assert key == "8811"
    assert "A123456780" in text


def test_extract_generic_ticket() -> None:
    payload = json.loads(
        (ROOT / "examples/connectors/tickets/sample-generic.json").read_text(encoding="utf-8")
    )
    key, text = _mod.extract_ticket(payload)
    assert key == "Meldebescheinigung"
    assert "15 020649 M 003" in text
