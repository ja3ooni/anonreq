"""Nested PII and exception messages must not reach logs or SIEM payloads.

The allowlist only drops unknown top-level keys. These tests prove values
nested under allowlisted keys, stdlib ``extra`` fields, and exception args
are scrubbed before formatting, and that webhook (and the other SIEM sinks)
do not emit those values.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest

from anonreq.logging_config import setup_logging
from anonreq.models.processing_context import ProcessingContext
from anonreq.soc.event import NormalizedEvent, SeverityLevel

EMAIL = "ada.lovelace@example.com"
SSN = "219-09-9999"
PHONE = "+1-415-555-0134"
CARD = "4111111111111111"
SENTINEL = "do-not-leak-sentinel"
PII_VALUES = (EMAIL, SSN, PHONE, CARD, SENTINEL)


def _stderr_text(capsys: pytest.CaptureFixture[str]) -> str:
    captured = capsys.readouterr()
    return captured.err


def _assert_pii_absent(text: str) -> None:
    for value in PII_VALUES:
        assert value not in text, f"{value!r} leaked into: {text}"


def _pii_event() -> NormalizedEvent:
    return NormalizedEvent(
        severity=SeverityLevel.HIGH,
        event_type="dlp_violation",
        tenant_id="tenant-abc",
        session_id="sess-123",
        timestamp="2026-06-26T14:30:00.123456Z",
        gateway_version="1.5.0",
        appliance_instance_id="anonreq-test-1",
        mitre_technique_id="T1048",
        metadata={
            "nested": {
                "contact": EMAIL,
                "ssn": SSN,
                "phones": [PHONE],
                "payment": {"card": CARD},
                "cause": ValueError(f"{SENTINEL} {EMAIL}"),
            }
        },
    )


class TestGermanIdentifierRedaction:
    """de-DE recognizers and their checksum validators apply to log text."""

    def test_each_german_id_and_iban_are_scrubbed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import structlog

        from anonreq.locale.checksums.germany import (
            generate_iban_de,
            generate_kvnr,
            generate_personalausweis,
            generate_steuer_id,
        )
        from anonreq.locale.checksums.iso7064 import ISO7064Mod11_2Validator

        steuer_id = generate_steuer_id()
        ausweis = generate_personalausweis()
        kvnr = generate_kvnr()
        iban = generate_iban_de()
        svnr = "65 150682 M 007"
        invalid_steuer = "11111111111"
        invalid_iban = "DE00370400440532013000"
        assert not ISO7064Mod11_2Validator().validate(invalid_steuer)

        setup_logging(level="INFO")
        log = structlog.get_logger()
        log.info(
            "german-ids",
            error=(
                f"steuer {steuer_id} ausweis {ausweis} kvnr {kvnr} "
                f"svnr {svnr} iban {iban} bad {invalid_steuer} {invalid_iban}"
            ),
        )

        rendered = _stderr_text(capsys)
        for secret in (steuer_id, ausweis, kvnr, svnr, iban):
            assert secret not in rendered, secret
        assert invalid_steuer in rendered
        assert invalid_iban in rendered
        assert "[REDACTED]" in rendered


class TestBulgarianIdentifierRedaction:
    """bg-BG EGN, LNCh, IBAN and phone numbers are scrubbed from log text."""

    def test_bulgarian_ids_are_scrubbed_and_counters_kept(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import datetime as dt

        import structlog

        from anonreq.locale.checksums.bulgaria import (
            egn_valid,
            generate_egn,
            generate_iban_bg,
            generate_lnch,
            lnch_valid,
        )

        egn = generate_egn(dt.date(1985, 3, 15), serial=456)
        lnch = generate_lnch("200300400")
        iban = generate_iban_bg()
        spaced_iban = " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))
        phones = ("+359 88 123 4567", "+359 2 987 6543", "0888 123 456", "02 987 6543")
        # Unvalidated 10-digit values (counters, epoch seconds) stay readable.
        counter, epoch = "1234567890", "1763035200"
        for value in (counter, epoch):
            assert not egn_valid(value)
            assert not lnch_valid(value)

        setup_logging(level="INFO")
        log = structlog.get_logger()
        log.info(
            "bulgarian-ids",
            error=(
                f"ЕГН {egn} ЛНЧ {lnch} IBAN {iban} / {spaced_iban} "
                f"тел. {', '.join(phones)} request {counter} at {epoch}"
            ),
        )

        rendered = _stderr_text(capsys)
        for secret in (egn, lnch, iban, spaced_iban, *phones):
            assert secret not in rendered, secret
        assert counter in rendered
        assert epoch in rendered
        assert "[REDACTED]" in rendered


def _bad_check_digit(value: str) -> str:
    return value[:-1] + str((int(value[-1]) + 1) % 10)


def _bg_leak_cases() -> list[tuple[str, str]]:
    import datetime as dt

    from anonreq.locale.checksums.bulgaria import (
        egn_valid,
        generate_egn,
        generate_iban_bg,
        generate_lnch,
        iban_bg_valid,
        lnch_valid,
    )

    bad_egn = _bad_check_digit(generate_egn(dt.date(1985, 3, 15), serial=456))
    bad_lnch = _bad_check_digit(generate_lnch("200300400"))
    iban = generate_iban_bg("SYNT", "12345678901234")
    bad_iban = iban[:2] + f"{(int(iban[2:4]) + 1) % 100:02d}" + iban[4:]
    assert not egn_valid(bad_egn)
    assert not lnch_valid(bad_lnch)
    assert not iban_bg_valid(bad_iban)
    return [
        # (secret, log text) — the Reviewer's leak cases at 56c7f43.
        (bad_egn, f"ЕГН {bad_egn}"),
        (bad_egn, f"EGN: {bad_egn}"),
        (bad_lnch, f"ЛНЧ {bad_lnch}"),
        (bad_iban, f"IBAN {bad_iban}"),
        (iban.lower(), f"iban {iban.lower()}"),
        ("AB1234567", "лична карта № AB1234567"),
        ("645123456", "лична карта № 645123456"),
        ("645123456", "ЛК: 645123456"),
    ]


class TestBulgarianLogScrubberFailsClosed:
    """Labelled or format-valid bg IDs are scrubbed even when unverified."""

    @pytest.mark.parametrize("case", range(8))
    def test_unverified_and_unchecked_bg_ids_are_scrubbed(self, case: int) -> None:
        from anonreq.logging_config import _redact_text

        secret, text = _bg_leak_cases()[case]
        redacted = _redact_text(f"lookup failed: {text}; retry later")
        assert secret not in redacted, redacted
        assert secret.upper() not in redacted.upper(), redacted
        assert "[REDACTED]" in redacted

    @pytest.mark.parametrize(
        "value",
        ["1234567890", "1712345678", "1763035200", "8503154561"],
    )
    def test_unlabelled_counters_survive(self, value: str) -> None:
        from anonreq.locale.checksums.bulgaria import egn_valid, lnch_valid
        from anonreq.logging_config import _redact_text

        assert not egn_valid(value)
        assert not lnch_valid(value)
        assert value in _redact_text(f"request {value} done")


class TestBulgarianLooseIbanAndEikInLogs:
    """Loose-shape IBANs and EIK/BULSTAT numbers are scrubbed from logs."""

    @pytest.mark.parametrize(
        "text_and_secret",
        [
            ("IBAN BG80SYNT1A3456789012AB", "BG80SYNT1A3456789012AB"),
            ("iban bg80 synt 1a34 5678 9012 ab", "bg80 synt 1a34 5678 9012 ab"),
        ],
    )
    def test_loose_shape_iban_is_scrubbed(self, text_and_secret: tuple[str, str]) -> None:
        from anonreq.logging_config import _redact_text

        text, secret = text_and_secret
        redacted = _redact_text(f"payment failed: {text}")
        assert secret not in redacted, redacted
        assert "[REDACTED]" in redacted

    def test_eik_forms_are_scrubbed(self) -> None:
        from anonreq.locale.checksums.bulgaria import eik_valid, generate_eik
        from anonreq.logging_config import _redact_text

        eik9 = generate_eik("20406080")
        eik13 = generate_eik("20406080", branch3="123")
        bad_eik = _bad_check_digit(eik9)
        assert not eik_valid(bad_eik)
        cases = [
            (eik9, f"company {eik9} onboarded"),  # unlabelled, checksum-valid
            (eik13, f"branch {eik13} onboarded"),
            (f"BG{eik9}", f"VAT BG{eik9} onboarded"),
            (bad_eik, f"ЕИК {bad_eik} rejected"),  # labelled, bad checksum
            (bad_eik, f"БУЛСТАТ: {bad_eik} rejected"),
            (bad_eik, f"EIK {bad_eik} rejected"),
        ]
        for secret, text in cases:
            redacted = _redact_text(text)
            assert secret not in redacted, (text, redacted)
            assert "[REDACTED]" in redacted

    def test_unlabelled_invalid_nine_digits_survive(self) -> None:
        from anonreq.locale.checksums.bulgaria import eik_valid
        from anonreq.logging_config import _redact_text

        value = "123456780"
        assert not eik_valid(value)
        assert value in _redact_text(f"batch {value} done")



class TestPersonalVatBgEgnInLogs:
    """BG + EGN personal VAT numbers are scrubbed from logs, EIK VAT is unchanged."""

    def test_bg_plus_valid_egn_is_scrubbed(self) -> None:
        import datetime as dt

        from anonreq.locale.checksums.bulgaria import egn_valid, generate_egn
        from anonreq.logging_config import _redact_text

        egn = generate_egn(dt.date(1985, 3, 15), serial=456)
        vat = f"BG{egn}"
        assert egn_valid(vat)
        for text in (
            f"ДДС № {vat} на ЕТ Иванов",  # noqa: RUF001
            f"VAT {vat}",
            f"VAT bg{egn}",
            vat,
        ):
            redacted = _redact_text(text)
            assert vat not in redacted, (text, redacted)
            assert egn not in redacted, (text, redacted)
            assert "[REDACTED]" in redacted

    def test_bg_plus_eik_vat_still_scrubbed_and_not_as_egn_collision(self) -> None:
        from anonreq.locale.checksums.bulgaria import (
            egn_valid,
            eik_valid,
            generate_eik,
        )
        from anonreq.logging_config import _redact_text

        eik9 = generate_eik("20406080")
        eik13 = generate_eik("20406080", branch3="123")
        assert eik_valid(f"BG{eik9}")
        assert eik_valid(f"BG{eik13}")
        assert not egn_valid(f"BG{eik9}")
        assert not egn_valid(f"BG{eik13}")
        for secret in (f"BG{eik9}", f"BG{eik13}"):
            redacted = _redact_text(f"VAT {secret} onboarded")
            assert secret not in redacted, (secret, redacted)
            assert "[REDACTED]" in redacted

    def test_bg_plus_invalid_egn_without_label_survives(self) -> None:
        import datetime as dt

        from anonreq.locale.checksums.bulgaria import egn_valid, generate_egn
        from anonreq.logging_config import _redact_text

        egn = generate_egn(dt.date(1985, 3, 15), serial=456)
        bad = "BG" + egn[:-1] + str((int(egn[-1]) + 1) % 10)
        assert not egn_valid(bad)
        assert bad in _redact_text(f"ref {bad} done")


class TestFormattedLogRedaction:
    """Formatted JSON from structlog and stdlib must not contain PII."""

    def test_nested_pii_and_exception_args_are_scrubbed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import structlog

        setup_logging(level="DEBUG")
        log = structlog.get_logger()
        log.error(
            "nested-pii %s",
            ValueError(f"{SENTINEL} {EMAIL}"),
            error={
                "detail": [
                    EMAIL,
                    {"ssn": SSN, "note": f"call {PHONE}"},
                ]
            },
            data={"profile": {"emails": [EMAIL], "card": CARD}},
            extra={"items": [{"phone": PHONE, "cause": RuntimeError(SENTINEL)}]},
        )

        rendered = _stderr_text(capsys)
        _assert_pii_absent(rendered)
        entry = json.loads(rendered.strip().splitlines()[-1])
        assert entry["event"].startswith("nested-pii")
        assert "ValueError" in entry["event"]
        assert entry["error"]["detail"][1]["ssn"] == "[REDACTED]"
        assert "[REDACTED]" in json.dumps(entry["data"])
        assert entry["extra"]["items"][0]["phone"] == "[REDACTED]"
        assert entry["extra"]["items"][0]["cause"] == "RuntimeError"
        assert "T" in entry["timestamp"]
        assert "[REDACTED]" not in entry["timestamp"]

    def test_stdlib_extra_exception_and_exc_info(self, capsys: pytest.CaptureFixture[str]) -> None:
        setup_logging(level="DEBUG")
        stdlib = logging.getLogger("anonreq.test.pii")
        stdlib.error(
            "stdlib-failed %s",
            ValueError(f"{SENTINEL} {EMAIL}"),
            extra={
                "extra": {"nested": [EMAIL, {"ssn": SSN}]},
                "data": {"card": CARD, "phone": PHONE},
            },
        )
        try:
            raise RuntimeError(f"{SENTINEL} exploded")
        except RuntimeError:
            stdlib.exception("exploded")

        rendered = _stderr_text(capsys)
        _assert_pii_absent(rendered)
        entries = [json.loads(line) for line in rendered.splitlines() if line.strip()]
        assert any("ValueError" in entry["event"] for entry in entries)
        assert any(entry.get("error_type") == "RuntimeError" for entry in entries)
        nested = entries[0]["extra"]["nested"]
        assert EMAIL not in json.dumps(nested)
        assert entries[0]["data"]["phone"] == "[REDACTED]"

    def test_exc_info_keeps_raise_site_without_message(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import sys

        setup_logging(level="ERROR")
        try:
            _raise_for_log()
        except RuntimeError:
            tb = sys.exc_info()[2]
            assert tb is not None
            while tb.tb_next is not None:
                tb = tb.tb_next
            expected_line = tb.tb_lineno
            expected_file = tb.tb_frame.f_code.co_filename
            logging.getLogger("anonreq.test.site").error("exploded", exc_info=True)

        rendered = _stderr_text(capsys)
        _assert_pii_absent(rendered)
        entry = json.loads(rendered.strip().splitlines()[-1])
        assert entry["error_type"] == "RuntimeError"
        assert entry["error_function"] == "_raise_for_log"
        assert entry["error_line"] == expected_line
        assert entry["error_file"] == expected_file

    def test_oversized_value_skips_regex_past_the_cap(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import structlog

        from anonreq.logging_config import LOG_SCRUB_MAX_CHARS

        setup_logging(level="INFO")
        log = structlog.get_logger()
        log.info("capped-tail", error=("x" * LOG_SCRUB_MAX_CHARS) + EMAIL)
        tail_rendered = _stderr_text(capsys)
        assert EMAIL not in tail_rendered
        assert "[TRUNCATED]" in tail_rendered

        log.info("capped-head", error=EMAIL + ("y" * LOG_SCRUB_MAX_CHARS))
        head_rendered = _stderr_text(capsys)
        assert EMAIL not in head_rendered
        assert "[REDACTED]" in head_rendered
        assert "[TRUNCATED]" in head_rendered


def _raise_for_log() -> None:
    raise RuntimeError(f"{SENTINEL} {EMAIL}")


class TestUvicornHandlerRedaction:
    """uvicorn.access and uvicorn.error do not propagate to the root handler."""

    def test_handlers_scrub_pii(self, capsys: pytest.CaptureFixture[str]) -> None:
        from anonreq.logging_config import PiiRedactingFilter

        setup_logging(level="INFO")
        access = logging.getLogger("uvicorn.access")
        error = logging.getLogger("uvicorn.error")
        access.handlers.clear()
        error.handlers.clear()
        access.propagate = False
        error.propagate = False
        access.setLevel(logging.INFO)
        error.setLevel(logging.INFO)
        access.addHandler(logging.StreamHandler())
        error.addHandler(logging.StreamHandler())

        assert any(isinstance(item, PiiRedactingFilter) for item in access.handlers[0].filters)
        assert any(isinstance(item, PiiRedactingFilter) for item in error.handlers[0].filters)

        access.info("GET /search?q=%s", EMAIL)
        error.error("listener failed for %s", EMAIL)
        rendered = _stderr_text(capsys)
        assert EMAIL not in rendered
        assert "[REDACTED]" in rendered


class TestCleanupExceptionLogging:
    """Mapping-delete failures log the exception type and nothing else."""

    @pytest.mark.asyncio
    async def test_exception_message_is_not_logged(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from anonreq.pipeline.cleanup import CleanupStage

        class BoomCache:
            async def delete_mapping(self, _tenant_id: str, _context_id: str) -> None:
                raise ValueError(f"{SENTINEL} mapping for {EMAIL}")

        setup_logging(level="DEBUG")
        ctx = ProcessingContext(
            request_id="req-cleanup",
            tenant_id="tenant-abc",
            context_id="ctx-1",
            token_mappings={"[EMAIL_0]": EMAIL},
        )
        await CleanupStage(BoomCache()).execute(ctx)

        rendered = _stderr_text(capsys)
        _assert_pii_absent(rendered)
        assert "ValueError" in rendered
        assert "cleanup.mapping_delete_failed" in rendered


class TestSinkPayloadRedaction:
    """SIEM payloads are scrubbed before they are rendered or sent."""

    @pytest.mark.asyncio
    async def test_webhook_payload_and_error_log(self, capsys: pytest.CaptureFixture[str]) -> None:
        from anonreq.soc.sinks.webhook import WebhookSink

        setup_logging(level="DEBUG")
        sink = WebhookSink(name="webhook_test", url="https://hooks.example.com/events")
        await sink.start()
        event = _pii_event()
        captured: dict[str, Any] = {}

        async def request(*_args: Any, **kwargs: Any) -> None:
            captured["content"] = kwargs.get("content")
            raise RuntimeError(f"{SENTINEL} {EMAIL}")

        assert sink._client is not None
        sink._client.request = request  # type: ignore[method-assign]
        try:
            delivered = await sink.send_event(event)
        finally:
            await sink.stop()

        assert delivered is False
        body = captured["content"]
        assert isinstance(body, str)
        _assert_pii_absent(body)
        assert "ValueError" in body
        assert event.timestamp in body
        assert event.tenant_id in body

        rendered = _stderr_text(capsys)
        _assert_pii_absent(rendered)
        assert "RuntimeError" in rendered

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("factory", "kwargs"),
        [
            ("anonreq.soc.sinks.datadog_logs.DatadogLogsSink", {"api_key": "dd-test"}),
            (
                "anonreq.soc.sinks.elastic_bulk.ElasticBulkSink",
                {"endpoint": "https://elastic.example:9200", "api_key": "elastic-test"},
            ),
            (
                "anonreq.soc.sinks.splunk_hec.SplunkHECSink",
                {
                    "endpoint": "https://splunk.example:8088/services/collector/event",
                    "token": "hec",
                },
            ),
            (
                "anonreq.soc.sinks.sentinel_dcr.SentinelDCRSink",
                {
                    "tenant_id": "azure-tenant",
                    "client_id": "client",
                    "client_secret": "secret",
                    "dcr_endpoint": "https://eastus.ingest.monitor.azure.com",
                    "dcr_immutable_id": "dcr-1",
                    "stream_name": "Custom-AnonReq",
                },
            ),
            ("anonreq.soc.sinks.qradar_cef.QRadarCEFSink", {"host": "qradar.example", "port": 514}),
        ],
    )
    async def test_similar_sinks_scrub_nested_pii(
        self,
        factory: str,
        kwargs: dict[str, Any],
    ) -> None:
        module_name, class_name = factory.rsplit(".", 1)
        module = __import__(module_name, fromlist=[class_name])
        sink_cls = getattr(module, class_name)
        sink = sink_cls(name="pii-sink", **kwargs)
        payload = await sink.format_event(_pii_event())
        rendered = payload if isinstance(payload, str) else json.dumps(payload, default=str)
        _assert_pii_absent(rendered)
        assert "ValueError" in rendered
