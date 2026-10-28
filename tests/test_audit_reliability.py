"""Audit reliability: cleanup always runs, audit writes fail closed, streams audited."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from prometheus_client import REGISTRY
from structlog.testing import capture_logs

from anonreq.exceptions import PipelineAbortError
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.base import PipelineStage
from anonreq.pipeline.cleanup import CleanupStage
from anonreq.pipeline.manager import PipelineManager
from anonreq.streaming.cleanup import SessionCleanup


class _Chain:
    def __init__(self, failures: int = 0, message: str = "audit db down") -> None:
        self.failures = failures
        self.message = message
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def log_event(self, event_type: str, **fields: Any) -> None:
        self.calls.append((event_type, fields))
        if self.failures > 0:
            self.failures -= 1
            raise RuntimeError(self.message)


class _Cache:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.deleted: list[tuple[str, str]] = []

    async def delete_mapping(self, tenant_id: str, session_id: str) -> None:
        if self.error is not None:
            raise self.error
        self.deleted.append((tenant_id, session_id))


def _ctx() -> ProcessingContext:
    ctx = ProcessingContext(request_id="req-audit", tenant_id="tenant-a")
    ctx.context_id = "sess-audit"
    ctx.token_mappings = {"[EMAIL_0]": "person@example.com"}
    ctx.detections = [{"entity_type": "EMAIL", "start": 0, "end": 4, "score": 1.0}]
    ctx.classification_result = {"action": "ANONYMIZE", "matched_rule_ids": ["R1"]}
    ctx.provider = "openai"
    ctx.model = "gpt-test"
    ctx.audit_metadata = {"locale": "en", "operator_id": "op-1", "compliance_preset": "gdpr"}
    ctx.processing_overhead_ms = 12
    return ctx


def _failure_count() -> float:
    return REGISTRY.get_sample_value("anonreq_audit_failures_total") or 0.0


class _Boom(PipelineStage):
    def __init__(self) -> None:
        super().__init__("BoomStage")

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        ctx.fail_secure(PipelineAbortError(status_code=403, message="Request blocked by policy"))
        return ctx


class _Explode(PipelineStage):
    def __init__(self) -> None:
        super().__init__("ExplodeStage")

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        raise RuntimeError("detector exploded person@example.com")


class _Provider(PipelineStage):
    def __init__(self) -> None:
        super().__init__("ProviderStage")
        self.called = False

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        self.called = True
        return ctx


@pytest.mark.asyncio
async def test_pipeline_runs_cleanup_and_audit_after_error() -> None:
    ctx = _ctx()
    chain = _Chain()
    ctx.audit_chain = chain
    cache = _Cache()
    provider = _Provider()
    manager = PipelineManager()
    manager.register(_Boom())
    manager.register(provider)
    manager.register(CleanupStage(cache))

    result = await manager.run(ctx)

    assert provider.called is False
    assert cache.deleted == [("tenant-a", "sess-audit")]
    assert [event for event, _fields in chain.calls] == ["anonymization"]
    assert result.errors[-1].status_code == 403
    assert "person@example.com" not in repr(chain.calls)


@pytest.mark.asyncio
async def test_pipeline_keeps_original_error_when_audit_write_fails() -> None:
    ctx = _ctx()
    chain = _Chain(failures=5, message="db refused person@example.com")
    ctx.audit_chain = chain
    provider = _Provider()
    sleeps: list[float] = []

    async def _sleep(delay: float) -> None:
        sleeps.append(delay)

    manager = PipelineManager()
    manager.register(_Explode())
    manager.register(provider)
    manager.register(
        CleanupStage(
            _Cache(),
            audit_attempts=2,
            audit_backoff_seconds=0.05,
            audit_sleep=_sleep,
        )
    )

    before = _failure_count()
    with capture_logs() as logs:
        result = await manager.run(ctx)

    assert provider.called is False
    assert isinstance(result.errors[-1], RuntimeError)
    assert len(result.errors) == 1
    assert len(chain.calls) == 2
    assert sleeps == [0.05]
    assert _failure_count() == before + 1
    rendered = repr(logs)
    assert "person@example.com" not in rendered
    assert any(
        event.get("event") == "cleanup.audit_chain_failed" and event.get("log_level") == "error"
        for event in logs
    )


@pytest.mark.asyncio
async def test_audit_write_retries_then_fails_closed() -> None:
    ctx = _ctx()
    chain = _Chain(failures=3, message="timeout for person@example.com")
    ctx.audit_chain = chain
    sleeps: list[float] = []

    async def _sleep(delay: float) -> None:
        sleeps.append(delay)

    stage = CleanupStage(
        _Cache(),
        audit_attempts=3,
        audit_backoff_seconds=0.05,
        audit_sleep=_sleep,
    )
    before = _failure_count()
    with (
        capture_logs() as logs,
        pytest.raises(PipelineAbortError, match="Audit write failed") as raised,
    ):
        await stage.execute(ctx)

    assert raised.value.status_code == 500
    assert len(chain.calls) == 3
    assert sleeps == [0.05, 0.1]
    assert _failure_count() == before + 1
    assert "person@example.com" not in repr(logs)
    assert all("person@example.com" not in repr(event) for event in logs)


@pytest.mark.asyncio
async def test_audit_write_succeeds_on_retry_without_alert() -> None:
    ctx = _ctx()
    chain = _Chain(failures=1)
    ctx.audit_chain = chain
    stage = CleanupStage(
        _Cache(),
        audit_attempts=3,
        audit_backoff_seconds=0,
        audit_sleep=AsyncMock(),
    )
    before = _failure_count()

    result = await stage.execute(ctx)

    assert not result.has_errors()
    assert len(chain.calls) == 2
    assert _failure_count() == before


@pytest.mark.asyncio
async def test_single_attempt_fails_without_sleep() -> None:
    ctx = _ctx()
    ctx.audit_chain = _Chain(failures=1)
    slept = AsyncMock()
    stage = CleanupStage(_Cache(), audit_attempts=1, audit_backoff_seconds=0, audit_sleep=slept)

    with pytest.raises(PipelineAbortError):
        await stage.execute(ctx)

    slept.assert_not_awaited()


@pytest.mark.asyncio
async def test_mapping_delete_failure_still_writes_audit() -> None:
    ctx = _ctx()
    chain = _Chain()
    ctx.audit_chain = chain
    stage = CleanupStage(_Cache(error=ConnectionError("valkey refused")))

    result = await stage.execute(ctx)

    assert not result.has_errors()
    assert chain.calls[0][0] == "anonymization"
    assert chain.calls[0][1]["token_count"] == 1
    assert "terminal_state" not in chain.calls[0][1]


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_state", ["FINISH", "CLIENT_DISCONNECT", "PROVIDER_ERROR"])
async def test_stream_cleanup_writes_same_audit_event(terminal_state: str) -> None:
    non_stream = _ctx()
    non_stream.audit_chain = _Chain()
    await CleanupStage(_Cache()).execute(non_stream)

    streamed = _ctx()
    streamed.audit_chain = _Chain()
    cleanup = SessionCleanup(
        _Cache(),
        streamed.tenant_id,
        streamed.context_id or "",
        audit_logger=MagicMock(),
        metrics=MagicMock(),
        processing_context=streamed,
    )

    await cleanup.cleanup(terminal_state)

    _event, base_fields = non_stream.audit_chain.calls[0]
    stream_event, stream_fields = streamed.audit_chain.calls[0]
    assert stream_event == "anonymization"
    assert stream_fields["terminal_state"] == terminal_state
    without_terminal = {
        key: value for key, value in stream_fields.items() if key != "terminal_state"
    }
    assert without_terminal == base_fields
    assert "person@example.com" not in repr(stream_fields)


@pytest.mark.asyncio
async def test_stream_cleanup_audits_when_delete_fails_and_is_idempotent() -> None:
    ctx = _ctx()
    chain = _Chain()
    ctx.audit_chain = chain
    metrics = MagicMock()
    cleanup = SessionCleanup(
        _Cache(error=TimeoutError("delete failed")),
        ctx.tenant_id,
        ctx.context_id or "",
        metrics=metrics,
        processing_context=ctx,
    )

    await cleanup.cleanup("CLIENT_DISCONNECT")
    await cleanup.cleanup("FINISH")

    assert len(chain.calls) == 1
    assert chain.calls[0][1]["terminal_state"] == "CLIENT_DISCONNECT"
    metrics.disconnects.inc.assert_called_once()


@pytest.mark.asyncio
async def test_stream_audit_failure_fails_closed_after_retries() -> None:
    ctx = _ctx()
    ctx.audit_chain = _Chain(failures=2, message="stream audit person@example.com")
    sleeps: list[float] = []

    async def _sleep(delay: float) -> None:
        sleeps.append(delay)

    cleanup = SessionCleanup(
        _Cache(),
        ctx.tenant_id,
        ctx.context_id or "",
        metrics=MagicMock(),
        processing_context=ctx,
        audit_attempts=2,
        audit_backoff_seconds=0.05,
        audit_sleep=_sleep,
    )
    before = _failure_count()
    with capture_logs() as logs, pytest.raises(PipelineAbortError, match="Audit write failed"):
        await cleanup.cleanup("PROVIDER_ERROR")

    assert sleeps == [0.05]
    assert _failure_count() == before + 1
    assert cleanup._cleaned is True
    assert "person@example.com" not in repr(logs)
