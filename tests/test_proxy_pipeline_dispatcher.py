"""Tests for PipelineContentDispatcher — the proxy-to-pipeline adapter."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

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
