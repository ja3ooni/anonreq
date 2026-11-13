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


def _stage(allow_structured_only: bool = True) -> LocaleNegotiationStage:
    return LocaleNegotiationStage(
        LocaleNegotiator(LocaleRegistry("config/locales")),
        MagicMock(spec=RecognizerMerger),
        allow_structured_only=allow_structured_only,
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
        assert fields["bg_structured_only"] is True
    else:
        assert "ner_coverage" not in fields
        assert "bg_structured_only" not in fields


@pytest.mark.asyncio
@pytest.mark.parametrize("header", ["bg", "bg-BG", "en, bg-BG", "de-DE, bg"])
async def test_bg_is_refused_unless_explicitly_allowed(header: str) -> None:
    from anonreq.exceptions import LocaleNerNotClearedError

    ctx = ProcessingContext(request_id="r", tenant_id="t")
    ctx.locale_header = header
    ctx = await _stage(allow_structured_only=False).execute(ctx)
    assert ctx.has_errors()
    error = ctx.errors[-1]
    assert isinstance(error, LocaleNerNotClearedError)
    assert error.status_code == 422
    assert error.code == "bg_ner_not_cleared"
    assert ctx.audit_metadata["ner_coverage"] == STRUCTURED_ONLY
    assert ctx.audit_metadata["bg_structured_only"] is False

    chain = _Chain()
    ctx.audit_chain = chain  # type: ignore[assignment]
    await emit_anonymization_audit(ctx, attempts=1)
    [(_event_type, fields)] = chain.calls
    assert fields["bg_structured_only"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("header", ["de-DE", "en", None])
async def test_gate_does_not_touch_other_locales(header: str | None) -> None:
    ctx = ProcessingContext(request_id="r", tenant_id="t")
    ctx.locale_header = header
    ctx = await _stage(allow_structured_only=False).execute(ctx)
    assert not ctx.has_errors()
    assert "bg_structured_only" not in ctx.audit_metadata


def test_bg_structured_only_setting_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    from anonreq.config import Settings

    monkeypatch.delenv("ANONREQ_BG_STRUCTURED_ONLY", raising=False)
    base = {
        "ANONREQ_API_KEY": "k" * 32,
        "ANONREQ_VALKEY_URL": "redis://x",
        "ANONREQ_PRESIDIO_URL": "http://x",
    }
    for key, value in base.items():
        monkeypatch.setenv(key, value)
    assert Settings().BG_STRUCTURED_ONLY is False  # type: ignore[call-arg]
    monkeypatch.setenv("ANONREQ_BG_STRUCTURED_ONLY", "true")
    assert Settings().BG_STRUCTURED_ONLY is True  # type: ignore[call-arg]
