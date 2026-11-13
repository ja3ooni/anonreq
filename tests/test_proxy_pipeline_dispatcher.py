"""Tests for PipelineContentDispatcher — the proxy-to-pipeline adapter."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from anonreq.exceptions import PresidioLanguageUnsupportedError
from anonreq.models.processing_context import ProcessingContext
from anonreq.proxy.pipeline_dispatcher import (
    FAIL_CLOSED_ERROR,
    UNSUPPORTED_MEDIA_TYPE_ERROR,
    PipelineContentDispatcher,
)

SAMPLE_CHAT_BODY = json.dumps(
    {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "My SSN is 987-65-4320 and email is bob@example.com"},
        ],
    }
).encode("utf-8")


def _make_mock_pipeline(restored_response: dict | None = None, provider_response: dict | None = None, has_errors: bool = False):  # noqa: E501
    pipeline = AsyncMock()
    pipeline.stages = PropertyMock(return_value=[])
    pipeline.register = MagicMock()

    async def fake_run(ctx: ProcessingContext) -> ProcessingContext:
        ctx.restored_response = restored_response
        ctx.provider_response = provider_response
        if has_errors:
            ctx.fail_secure(RuntimeError("pipeline error"))
        return ctx

    pipeline.run = AsyncMock(side_effect=fake_run)
    return pipeline


@pytest.mark.asyncio
async def test_accepts_json_and_returns_restored_response():
    pipeline = _make_mock_pipeline(
        restored_response={
            "id": "chatcmpl-abc123",
            "choices": [{"message": {"content": "Hello, Bob. Your SSN is on file."}}],
        }
    )
    dispatcher = PipelineContentDispatcher(pipeline)

    result = await dispatcher.dispatch(
        "application/json",
        SAMPLE_CHAT_BODY,
        ctx={"request_id": "test-001", "tenant_id": "acme"},
    )

    assert isinstance(result, bytes)
    body = json.loads(result)
    assert body["choices"][0]["message"]["content"] == "Hello, Bob. Your SSN is on file."
    assert pipeline.run.called


@pytest.mark.asyncio
async def test_non_json_content_type_returns_unsupported_media_error():
    pipeline = _make_mock_pipeline()
    dispatcher = PipelineContentDispatcher(pipeline)

    result = await dispatcher.dispatch("text/plain", b"hello", ctx={})

    assert result == UNSUPPORTED_MEDIA_TYPE_ERROR


@pytest.mark.asyncio
async def test_empty_body_returns_unsupported_media_error():
    pipeline = _make_mock_pipeline()
    dispatcher = PipelineContentDispatcher(pipeline)

    result = await dispatcher.dispatch("application/json", b"", ctx={})

    assert result == UNSUPPORTED_MEDIA_TYPE_ERROR


@pytest.mark.asyncio
async def test_malformed_json_returns_fail_closed_error():
    pipeline = _make_mock_pipeline()
    dispatcher = PipelineContentDispatcher(pipeline)

    result = await dispatcher.dispatch("application/json", b"{not json", ctx={})

    assert result == FAIL_CLOSED_ERROR


@pytest.mark.asyncio
async def test_pipeline_errors_return_fail_closed():
    pipeline = _make_mock_pipeline(has_errors=True)
    dispatcher = PipelineContentDispatcher(pipeline)

    result = await dispatcher.dispatch(
        "application/json",
        json.dumps({"model": "gpt-4", "messages": []}).encode(),
        ctx={},
    )

    assert result == FAIL_CLOSED_ERROR


@pytest.mark.asyncio
async def test_provider_response_returned_when_no_restoration():
    pipeline = _make_mock_pipeline(
        provider_response={
            "id": "chatcmpl-xyz",
            "choices": [{"message": {"content": "Token response [PERSON_1]"}}],
        }
    )
    dispatcher = PipelineContentDispatcher(pipeline)

    result = await dispatcher.dispatch(
        "application/json",
        SAMPLE_CHAT_BODY,
        ctx={},
    )

    assert isinstance(result, bytes)
    body = json.loads(result)
    assert body["choices"][0]["message"]["content"] == "Token response [PERSON_1]"


@pytest.mark.asyncio
async def test_synthetic_pii_not_present_in_output():
    pii_value = "987-65-4320"
    pipeline = _make_mock_pipeline(
        restored_response={
            "id": "chatcmpl-abc",
            "choices": [{"message": {"content": "Your SSN is [SSN_0]."}}],
        }
    )
    dispatcher = PipelineContentDispatcher(pipeline)

    result = await dispatcher.dispatch(
        "application/json",
        SAMPLE_CHAT_BODY,
        ctx={},
    )

    body_str = result.decode("utf-8")
    assert pii_value not in body_str
    assert "[SSN_0]" in body_str


@pytest.mark.asyncio
async def test_non_dict_body_returns_fail_closed():
    pipeline = _make_mock_pipeline()
    dispatcher = PipelineContentDispatcher(pipeline)

    result = await dispatcher.dispatch("application/json", json.dumps(["list", "not", "dict"]).encode(), ctx={})  # noqa: E501

    assert result == FAIL_CLOSED_ERROR


@pytest.mark.asyncio
async def test_no_response_fields_returns_fail_closed():
    pipeline = _make_mock_pipeline()
    dispatcher = PipelineContentDispatcher(pipeline)

    result = await dispatcher.dispatch(
        "application/json",
        json.dumps({"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]}).encode(),
        ctx={},
    )

    assert result == FAIL_CLOSED_ERROR


@pytest.mark.asyncio
async def test_unsupported_presidio_language_is_explicit_and_sanitized():
    pipeline = AsyncMock()

    async def fake_run(ctx: ProcessingContext) -> ProcessingContext:
        ctx.fail_secure(PresidioLanguageUnsupportedError("de", request_id=ctx.request_id))
        return ctx

    pipeline.run = AsyncMock(side_effect=fake_run)
    dispatcher = PipelineContentDispatcher(pipeline)

    result = await dispatcher.dispatch("application/json", SAMPLE_CHAT_BODY, ctx={})
    text = result.decode()

    assert "does not support language 'de'" in text
    assert "presidio_unsupported_language" in text
    assert "987-65-4320" not in text
    assert "bob@example.com" not in text


@pytest.mark.asyncio
async def test_bg_coverage_header_and_422_are_returned_through_ctx():
    from anonreq.exceptions import LocaleNerNotClearedError

    pipeline = AsyncMock()

    async def refused(ctx: ProcessingContext) -> ProcessingContext:
        ctx.audit_metadata["ner_coverage"] = "structured_only"
        ctx.fail_secure(LocaleNerNotClearedError(request_id=ctx.request_id))
        return ctx

    pipeline.run = AsyncMock(side_effect=refused)
    dispatch_ctx: dict = {"path": "/v1/chat/completions"}
    result = await PipelineContentDispatcher(pipeline).dispatch(
        "application/json", SAMPLE_CHAT_BODY, ctx=dispatch_ctx
    )
    assert json.loads(result)["error"]["code"] == "bg_ner_not_cleared"
    assert dispatch_ctx["status_code"] == 422
    assert dispatch_ctx["response_headers"] == {"x-anonreq-ner-coverage": "structured_only"}


@pytest.mark.asyncio
async def test_bg_coverage_header_on_success_and_proxies_apply_it():
    from anonreq.proxy.reverse_proxy import ReverseProxy, ReverseProxyRequest
    from anonreq.proxy.transparent_proxy import ProxyRequest, TransparentProxy

    pipeline = AsyncMock()

    async def served(ctx: ProcessingContext) -> ProcessingContext:
        ctx.audit_metadata["ner_coverage"] = "structured_only"
        ctx.restored_response = {"choices": []}
        return ctx

    pipeline.run = AsyncMock(side_effect=served)
    dispatcher = PipelineContentDispatcher(pipeline)

    reverse = await ReverseProxy(dispatcher).handle(
        ReverseProxyRequest(
            method="POST",
            path="/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            body=SAMPLE_CHAT_BODY,
        )
    )
    assert reverse.status_code == 200
    assert reverse.headers["x-anonreq-ner-coverage"] == "structured_only"

    proxy = TransparentProxy.__new__(TransparentProxy)
    proxy.content_dispatcher = dispatcher
    routed = await proxy._route_to_dispatcher(
        ProxyRequest(
            method="POST",
            host="api.openai.com",
            path="/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            body=SAMPLE_CHAT_BODY,
        ),
        MagicMock(classification="ai"),
    )
    assert routed.headers["x-anonreq-ner-coverage"] == "structured_only"
