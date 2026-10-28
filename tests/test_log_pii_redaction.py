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
