"""bg-BG has no NER model: requests say so in the audit event and a header."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from anonreq.locale.merger import RecognizerMerger
from anonreq.locale.negotiator import LocaleNegotiator
from anonreq.locale.registry import LocaleRegistry
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.audit_emit import emit_anonymization_audit
from anonreq.pipeline.stages import STRUCTURED_ONLY, LocaleNegotiationStage


def _stage() -> LocaleNegotiationStage:
    return LocaleNegotiationStage(
        LocaleNegotiator(LocaleRegistry("config/locales")), MagicMock(spec=RecognizerMerger)
    )


def test_only_bg_bundle_declares_structured_only() -> None:
    registry = LocaleRegistry("config/locales")
    coverage = {code: registry.get(code).ner_coverage for code in registry.list_locales()}
    assert coverage.pop("bg-BG") == STRUCTURED_ONLY
    assert set(coverage.values()) == {None}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("bg", STRUCTURED_ONLY),
        ("bg-BG", STRUCTURED_ONLY),
        ("de-DE, bg-BG", STRUCTURED_ONLY),  # any structured-only bundle marks it
        ("de-DE", None),
        (None, None),
    ],
)
async def test_negotiation_records_ner_coverage(header: str | None, expected: str | None) -> None:
    ctx = ProcessingContext(request_id="r", tenant_id="t")
    ctx.locale_header = header
    ctx = await _stage().execute(ctx)
    assert ctx.audit_metadata.get("ner_coverage") == expected


class _Chain:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def log_event(self, event_type: str, **fields: Any) -> None:
        self.calls.append((event_type, fields))


@pytest.mark.asyncio
@pytest.mark.parametrize("header", ["bg", "de-DE"])
async def test_audit_event_carries_ner_coverage(header: str) -> None:
    ctx = ProcessingContext(request_id="r", tenant_id="t")
    ctx.locale_header = header
    ctx = await _stage().execute(ctx)
    chain = _Chain()
    ctx.audit_chain = chain  # type: ignore[assignment]
    await emit_anonymization_audit(ctx, attempts=1)
    [(event_type, fields)] = chain.calls
    assert event_type == "anonymization"
    if header == "bg":
        assert fields["ner_coverage"] == STRUCTURED_ONLY
        assert fields["locale"] == "bg-BG"
    else:
        assert "ner_coverage" not in fields
