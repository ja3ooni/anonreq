"""Integration tests for classification workflow in the request pipeline (Plan 12-02)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from anonreq.config import settings
from anonreq.exceptions import global_exception_handler, http_exception_handler
from anonreq.middleware.classification import ClassificationMiddleware
from anonreq.models.request_context import RequestContext
from anonreq.routing.chat import build_pipeline
from anonreq.routing.chat import router as chat_router


@pytest.fixture
def mock_presidio_client():
    client = AsyncMock()
    # Mock to return PERSON and EMAIL_ADDRESS detections
    client.analyze.return_value = [
        {"entity_type": "PERSON", "start": 0, "end": 4, "score": 0.95},
        {"entity_type": "EMAIL_ADDRESS", "start": 10, "end": 20, "score": 0.98},
    ]
    return client


@pytest.fixture
def mock_cache_manager():
    cache = AsyncMock()
    cache.get_token.return_value = None
    return cache


@pytest.fixture
def mock_app(mock_cache_manager, mock_presidio_client):
    app = FastAPI()
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # Setup app state expected by pipeline and route handler
    app.state.cache_manager = mock_cache_manager
    app.state.presidio_client = mock_presidio_client
    app.state.alias_registry = None
    app.state.locale_negotiator = None
    app.state.recognizer_merger = None
    app.state.checksum_registry = None

    # Setup PDP and PEP
    pdp = AsyncMock()
    pep = AsyncMock()
    app.state.pdp = pdp
    app.state.pep = pep

    # Add middleware
    app.add_middleware(ClassificationMiddleware)

    # Setup pipeline
    pipeline = build_pipeline(
        cache_manager=mock_cache_manager,
        presidio_client=mock_presidio_client,
        app_state=app.state,
    )
    app.state.pipeline = pipeline

    @app.middleware("http")
    async def inject_auth(request, call_next):
        request.state.request_id = "test-req-123"
        request.state.auth_context = RequestContext(
            request_id="test-req-123",
            tenant_id="default",
        )
        return await call_next(request)

    app.include_router(chat_router)
    return app, pdp, pep


@pytest.mark.asyncio
async def test_pipeline_runs_sensitivity_classification(mock_app):
    app, pdp, pep = mock_app

    # Mock PDP to allow and PEP to allow
    from anonreq.policy.models import PolicyAction, PolicyDecision
    from anonreq.policy.pep import PolicyEnforcementResult

    pdp.evaluate_all.return_value = PolicyDecision(
        action=PolicyAction.ALLOW,
        matched_rule_ids=["allow_all"],
        decision_ts=datetime.now(UTC),
    )
    pep.enforce.return_value = PolicyEnforcementResult(
        action=PolicyAction.ALLOW,
        status_code=None,
        should_forward=True,
    )

    # Mock provider response structure
    mock_response = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-4",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello! I received your message.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 9,
            "completion_tokens": 12,
            "total_tokens": 21,
        },
    }

    async def mock_execute(ctx):
        ctx.provider_response = mock_response
        return ctx

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for stage in app.state.pipeline.stages:
            if stage.name == "ProviderStage":
                stage.execute = AsyncMock(side_effect=mock_execute)

        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "John's email is john@example.com"}],
        }
        headers = {"Authorization": f"Bearer {settings.API_KEY}"}
        response = await client.post("/v1/chat/completions", json=payload, headers=headers)
        assert response.status_code == 200

        # Check response headers populated from ClassificationStage
        assert response.headers.get("x-anonreq-classification") == "CONFIDENTIAL"
        assert response.headers.get("x-anonreq-highest-entity") == "EMAIL_ADDRESS"


@pytest.mark.asyncio
async def test_pipeline_blocks_highly_restricted(mock_app):
    app, pdp, pep = mock_app

    # Mock presidio to return API_KEY (which is HIGHLY_RESTRICTED)
    app.state.presidio_client.analyze.return_value = [
        {"entity_type": "API_KEY", "start": 0, "end": 10, "score": 0.99},
    ]

    from anonreq.policy.models import PolicyAction, PolicyDecision
    from anonreq.policy.pep import PolicyEnforcementResult

    # Mock PDP to block on HIGHLY_RESTRICTED
    pdp.evaluate_all.return_value = PolicyDecision(
        action=PolicyAction.BLOCK,
        matched_rule_ids=["classification_block"],
        reason="Request classified as HIGHLY_RESTRICTED is blocked per policy",
        decision_ts=datetime.now(UTC),
    )
    pep.enforce.return_value = PolicyEnforcementResult(
        action=PolicyAction.BLOCK,
        status_code=451,
        should_forward=False,
        body={"error_type": "classification_block", "reason": "Request classified as HIGHLY_RESTRICTED is blocked per policy"},  # noqa: E501
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "My API key is sk-12345"}],
        }
        headers = {"Authorization": f"Bearer {settings.API_KEY}"}
        response = await client.post("/v1/chat/completions", json=payload, headers=headers)
        assert response.status_code == 451
        body = response.json()
        assert "error" in body
        assert "highly_restricted" in body["error"]["message"].lower() or "blocked" in body["error"]["message"].lower()  # noqa: E501


@pytest.mark.asyncio
async def test_client_override_in_pipeline(mock_app):
    app, pdp, pep = mock_app

    from anonreq.policy.models import PolicyAction, PolicyDecision
    from anonreq.policy.pep import PolicyEnforcementResult

    pdp.evaluate_all.return_value = PolicyDecision(
        action=PolicyAction.ALLOW,
        matched_rule_ids=["allow_all"],
        decision_ts=datetime.now(UTC),
    )
    pep.enforce.return_value = PolicyEnforcementResult(
        action=PolicyAction.ALLOW,
        status_code=None,
        should_forward=True,
    )

    # Mock provider response structure
    mock_response = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-4",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello! I received your message.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 9,
            "completion_tokens": 12,
            "total_tokens": 21,
        },
    }

    async def mock_execute(ctx):
        ctx.provider_response = mock_response
        return ctx

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for stage in app.state.pipeline.stages:
            if stage.name == "ProviderStage":
                stage.execute = AsyncMock(side_effect=mock_execute)

        # Client asserts RESTRICTED, which is higher than detected CONFIDENTIAL
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "John's email is john@example.com"}],
        }
        headers = {
            "Authorization": f"Bearer {settings.API_KEY}",
            "X-AnonReq-Classification": "RESTRICTED",
        }
        response = await client.post("/v1/chat/completions", json=payload, headers=headers)
        assert response.status_code == 200

        # Assert client override took effect (RESTRICTED wins)
        assert response.headers.get("x-anonreq-classification") == "RESTRICTED"
        assert response.headers.get("x-anonreq-highest-entity") == "EMAIL_ADDRESS"
