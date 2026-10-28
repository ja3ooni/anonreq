"""Hot-path failures must not echo exception text to clients."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from anonreq.exceptions import http_exception_handler
from anonreq.governance.pdp_tool_evaluator import ToolBlockedError
from anonreq.locale.checksums.germany import generate_iban_de
from anonreq.locale.negotiator import LocaleNegotiationError
from anonreq.models.chat import ChatRequest
from anonreq.models.processing_context import ProcessingContext
from anonreq.models.request_context import RequestContext
from anonreq.pipeline.detection import DetectionStage
from anonreq.pipeline.provider import ProviderStage
from anonreq.pipeline.restoration import RestorationStage
from anonreq.pipeline.stages import LocaleNegotiationStage
from anonreq.pipeline.tokenization import TokenizationStage
from anonreq.pipeline.tool_governance import ToolGovernanceStage
from anonreq.routing.alias_registry import AliasNotFoundError
from anonreq.routing.chat import _raise_for_pipeline_errors, _stream_chat_completions

EMAIL = "ada.lovelace@example.com"
IBAN = generate_iban_de()
REQUEST_ID = "req_hotpath_test"


def _leak() -> str:
    return f"failed for {EMAIL} iban {IBAN}"


def _request() -> Request:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/chat/completions",
            "headers": [],
            "query_string": b"",
        }
    )
    request.state.request_id = REQUEST_ID
    return request


async def _response_text(ctx: ProcessingContext) -> str:
    with pytest.raises(HTTPException) as caught:
        _raise_for_pipeline_errors(ctx)
    response = await http_exception_handler(_request(), caught.value)
    body = response.body.decode()
    assert EMAIL not in body
    assert IBAN not in body
    assert REQUEST_ID in body
    assert EMAIL not in str(ctx.errors[-1])
    assert IBAN not in str(ctx.errors[-1])
    return body


def _anonymize_ctx() -> ProcessingContext:
    ctx = ProcessingContext(request_id=REQUEST_ID, tenant_id="tenant-a", context_id=uuid4().hex)
    ctx.classification_result = {"action": "ANONYMIZE"}
    ctx.original_request = {"model": "gpt-4", "messages": [{"role": "user", "content": "x"}]}
    ctx.text_nodes = [{"value": "x", "path": "messages[0].content"}]
    ctx.detections = [{"node_index": 0, "entity_type": "EMAIL_ADDRESS", "start": 0, "end": 1}]
    return ctx


@pytest.mark.asyncio
async def test_tokenization_exception_stays_out_of_the_response() -> None:
    tokenizer = MagicMock()
    tokenizer.initialize_session.side_effect = ValueError(_leak())
    stage = TokenizationStage(cache_manager=MagicMock(), tokenizer=tokenizer)
    ctx = _anonymize_ctx()
    await stage.execute(ctx)
    await _response_text(ctx)


@pytest.mark.asyncio
async def test_detection_exception_stays_out_of_the_response() -> None:
    presidio = MagicMock()
    presidio.analyze_text_nodes.side_effect = ValueError(_leak())
    stage = DetectionStage(
        regex_detector=MagicMock(),
        presidio_client=presidio,
        span_arbiter=MagicMock(),
        exclusion_list=MagicMock(),
    )
    ctx = _anonymize_ctx()
    await stage.execute(ctx)
    await _response_text(ctx)


@pytest.mark.asyncio
async def test_restoration_exception_stays_out_of_the_response() -> None:
    restorer = MagicMock()
    restorer.restore_response.side_effect = ValueError(_leak())
    stage = RestorationStage(restorer=restorer)
    ctx = _anonymize_ctx()
    ctx.provider_response = {"choices": [{"message": {"content": "ok"}}]}
    ctx.token_mappings = {}
    await stage.execute(ctx)
    await _response_text(ctx)


@pytest.mark.asyncio
async def test_provider_alias_and_parse_exceptions_stay_out_of_the_response() -> None:
    registry = MagicMock()
    registry.resolve.side_effect = AliasNotFoundError(EMAIL, [IBAN])
    stage = ProviderStage(
        openai_base_url="https://upstream.example",
        api_key="test-key",
        timeout=1,
        alias_registry=registry,
    )
    ctx = _anonymize_ctx()
    ctx.transformed_request = {"model": EMAIL, "messages": [{"role": "user", "content": "x"}]}
    await stage.execute(ctx)
    body = await _response_text(ctx)
    assert "Unknown model alias" in body

    parse_stage = ProviderStage(
        openai_base_url="https://upstream.example",
        api_key="test-key",
        timeout=1,
    )
    response = MagicMock()
    response.is_error = False
    response.status_code = 200
    response.json.side_effect = ValueError(_leak())
    parse_stage._http_client = AsyncMock()
    parse_stage._http_client.post = AsyncMock(return_value=response)
    parse_ctx = _anonymize_ctx()
    parse_ctx.transformed_request = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "x"}],
    }
    await parse_stage.execute(parse_ctx)
    await _response_text(parse_ctx)


@pytest.mark.asyncio
async def test_locale_negotiation_exception_stays_out_of_the_response() -> None:
    negotiator = MagicMock()
    negotiator.negotiate.side_effect = LocaleNegotiationError(_leak(), status_code=400)
    stage = LocaleNegotiationStage(negotiator=negotiator, merger=MagicMock())
    ctx = _anonymize_ctx()
    ctx.locale_header = "de-DE"
    await stage.execute(ctx)
    body = await _response_text(ctx)
    assert "Locale negotiation failed" in body


@pytest.mark.asyncio
async def test_tool_governance_exception_stays_out_of_the_response() -> None:
    extractor = MagicMock()
    extractor.detect_format.return_value = "openai"
    extractor.extract_calls.side_effect = ValueError(_leak())
    stage = ToolGovernanceStage(app_state=SimpleNamespace(tool_evaluator=object()))
    stage._extractor = extractor
    ctx = _anonymize_ctx()
    ctx.original_request = {
        "model": "gpt-4",
        "messages": [{"role": "assistant", "tool_calls": [{"id": "1"}]}],
    }
    await stage.execute(ctx)
    assert isinstance(ctx.errors[-1], ToolBlockedError)
    await _response_text(ctx)


@pytest.mark.asyncio
async def test_chat_alias_and_provider_errors_hide_exception_text() -> None:
    state = SimpleNamespace(
        cache_manager=object(),
        presidio_client=object(),
        alias_registry=MagicMock(),
        provider_registry=MagicMock(),
        locale_negotiator=None,
        recognizer_merger=None,
        checksum_registry=None,
        secret_rotation_buffer=None,
        secret_store=None,
        audit_chain=None,
        active_compliance_presets=None,
        _cached_pre_provider_pipeline=SimpleNamespace(
            run=AsyncMock(side_effect=lambda ctx: _mark_pass(ctx))
        ),
    )
    state.alias_registry.resolve.side_effect = AliasNotFoundError(EMAIL, [IBAN])
    request = _request()
    request.scope["app"] = SimpleNamespace()

    from unittest.mock import patch

    body = ChatRequest(
        model=EMAIL,
        messages=[{"role": "user", "content": "hello"}],
        stream=True,
    )
    with (
        patch("anonreq.routing.chat.get_app_state", return_value=state),
        pytest.raises(HTTPException) as caught,
    ):
        await _stream_chat_completions(body, request, RequestContext(request_id=REQUEST_ID))
    response = await http_exception_handler(request, caught.value)
    text = response.body.decode()
    assert EMAIL not in text
    assert IBAN not in text
    assert REQUEST_ID in text
    assert "Unknown model alias" in text

    from anonreq.providers.registry import ProviderNotFoundError

    state.alias_registry.resolve.side_effect = None
    state.alias_registry.resolve.return_value = SimpleNamespace(provider="openai", model="gpt-4")
    state.provider_registry.get_adapter.side_effect = ProviderNotFoundError(_leak())
    with (
        patch("anonreq.routing.chat.get_app_state", return_value=state),
        pytest.raises(HTTPException) as caught,
    ):
        await _stream_chat_completions(body, request, RequestContext(request_id=REQUEST_ID))
    text = (await http_exception_handler(request, caught.value)).body.decode()
    assert EMAIL not in text
    assert IBAN not in text
    assert "Unknown provider" in text


def _mark_pass(ctx: ProcessingContext) -> ProcessingContext:
    ctx.classification_result = {"action": "PASS", "matched_rule_ids": []}
    # Only a tokenized body may be forwarded (#15), so the fake pre-provider
    # pipeline must produce one to reach alias/provider resolution.
    ctx.transformed_request = dict(ctx.original_request or {})
    return ctx
