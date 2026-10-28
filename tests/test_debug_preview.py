"""Admin anonymization preview: flag, auth, offsets, and no persistence."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from httpx import ASGITransport, AsyncClient

from anonreq.config import settings
from anonreq.debug.offsets import utf16_len
from anonreq.debug.preview import router as preview_router
from anonreq.exceptions import global_exception_handler, http_exception_handler
from anonreq.policy.models import PolicyAction, PolicyRule
from anonreq.routing.chat import build_preview_pipeline

ADMIN_KEY = "adminkey12345678901234567890"


class _EmptyPresidio:
    async def analyze_text_nodes(self, text_nodes, entities=None, score_threshold=0.7):
        return [[] for _ in text_nodes]


class _PolicyStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    async def get_policy(self, rule_id: str, tenant_id: str | None = None) -> PolicyRule | None:
        self.calls.append((rule_id, tenant_id))
        if rule_id == "block-all":
            return PolicyRule(rule_id=rule_id, action=PolicyAction.BLOCK, enabled=True)
        if rule_id == "allow-external":
            return PolicyRule(rule_id=rule_id, action=PolicyAction.ALLOW, enabled=True)
        return None


@pytest.fixture
def preview_app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "DEBUG_PREVIEW_ENABLED", True)
    app = FastAPI()
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
    app.state.presidio_client = _EmptyPresidio()
    app.state.cache_manager = AsyncMock()
    app.state.audit_chain = AsyncMock()
    app.state.policy_store = _PolicyStore()

    @app.middleware("http")
    async def inject_role(request, call_next):
        request.state.tenant_id = request.headers.get("X-AnonReq-Tenant-ID", "acme")
        role = request.headers.get("X-Test-Role")
        if role:
            request.state.role_principal = {
                "principal_id": "test_admin",
                "role": role,
                "tenant_id": "*",
            }
        return await call_next(request)

    from anonreq.debug.preview import preview_rate_limiter

    preview_rate_limiter.reset()

    app.include_router(preview_router)
    return app


def _headers(**extra: str) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {ADMIN_KEY}"}
    headers.update(extra)
    return headers


@pytest.mark.asyncio
async def test_preview_disabled_is_404_without_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DEBUG_PREVIEW_ENABLED", False)
    app = FastAPI()
    app.include_router(preview_router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/debug/anonymize-preview",
            json={"prompt": "ada@example.com"},
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_preview_disabled_is_404_even_with_admin_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DEBUG_PREVIEW_ENABLED", False)
    app = FastAPI()
    app.include_router(preview_router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/debug/anonymize-preview",
            headers=_headers(),
            json={"prompt": "ada@example.com"},
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_preview_requires_admin_key(preview_app: FastAPI) -> None:
    transport = ASGITransport(app=preview_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        missing = await client.post(
            "/v1/debug/anonymize-preview",
            json={"prompt": "ada@example.com"},
        )
        rejected = await client.post(
            "/v1/debug/anonymize-preview",
            headers={"Authorization": "Bearer not-the-admin-key"},
            json={"prompt": "ada@example.com"},
        )
    assert missing.status_code == 401
    assert rejected.status_code == 401


@pytest.mark.asyncio
async def test_preview_rejects_insufficient_role(preview_app: FastAPI) -> None:
    transport = ASGITransport(app=preview_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/debug/anonymize-preview",
            headers=_headers(**{"X-Test-Role": "operator"}),
            json={"prompt": "ada@example.com"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_preview_prompt_anonymizes_without_persisting(preview_app: FastAPI) -> None:
    prompt = "Reach ada@example.com today"
    transport = ASGITransport(app=preview_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/debug/anonymize-preview",
            headers=_headers(**{"X-AnonReq-Locale": "de-DE"}),
            json={"prompt": prompt, "tenant_id": "acme"},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["locale"] == "de-DE"
    assert body["classification"] == "CONFIDENTIAL"
    assert body["highest_entity"] == "EMAIL_ADDRESS"
    assert body["anonymized_messages"] is None
    assert "ada@example.com" not in body["anonymized_text"]
    assert response.headers["X-AnonReq-Classification"] == body["classification"]
    assert response.headers["X-AnonReq-Highest-Entity"] == body["highest_entity"]
    assert response.headers["X-AnonReq-Request-ID"] == body["request_id"]

    email = next(item for item in body["entities"] if item["span"] == "ada@example.com")
    assert email["entity_type"] == "EMAIL_ADDRESS"
    assert email["message_index"] is None
    assert email["score"] == 1.0
    assert prompt[email["start"]:email["end"]] == "ada@example.com"
    assert body["anonymized_text"][email["token_start"]:email["token_end"]] == email["token"]
    assert email["token"].startswith("[EMAIL_ADDRESS_")
    preview_app.state.cache_manager.store_mapping.assert_not_called()
    preview_app.state.cache_manager.delete_mapping.assert_not_called()
    preview_app.state.audit_chain.log_event.assert_not_called()
    assert preview_app.state.policy_store.calls == []
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_preview_messages_utf16_offsets(preview_app: FastAPI) -> None:
    content = "😀 ada@example.com"
    assert utf16_len("😀") == 2
    transport = ASGITransport(app=preview_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/debug/anonymize-preview",
            headers=_headers(),
            json={"messages": [{"role": "user", "content": content}]},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["anonymized_text"] is None
    assert body["anonymized_messages"][0]["message_index"] == 0
    assert body["anonymized_messages"][0]["role"] == "user"
    email = next(item for item in body["entities"] if item["span"] == "ada@example.com")
    assert email["message_index"] == 0
    assert email["start"] == 2
    assert email["start_utf16"] == 3
    assert email["end_utf16"] == 3 + utf16_len("ada@example.com")
    assert email["token_start"] == 2
    assert email["token_start_utf16"] == 3
    anonymized = body["anonymized_messages"][0]["content"]
    assert anonymized[email["token_start"]:email["token_end"]] == email["token"]
    assert "ada@example.com" not in anonymized


@pytest.mark.asyncio
async def test_preview_policy_block_does_not_persist(preview_app: FastAPI) -> None:
    transport = ASGITransport(app=preview_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        blocked = await client.post(
            "/v1/debug/anonymize-preview",
            headers=_headers(),
            json={"prompt": "ada@example.com", "policy": "block-all", "tenant": "acme"},
        )
        missing = await client.post(
            "/v1/debug/anonymize-preview",
            headers=_headers(),
            json={"prompt": "ada@example.com", "policy": "missing"},
        )
    assert blocked.status_code == 403
    assert missing.status_code == 404
    preview_app.state.cache_manager.store_mapping.assert_not_called()
    preview_app.state.audit_chain.log_event.assert_not_called()
    assert ("block-all", "acme") in preview_app.state.policy_store.calls


@pytest.mark.asyncio
async def test_preview_rejects_foreign_tenant(preview_app: FastAPI) -> None:
    transport = ASGITransport(app=preview_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/debug/anonymize-preview",
            headers=_headers(),
            json={"prompt": "ada@example.com", "tenant_id": "other"},
        )
    assert response.status_code == 403
    preview_app.state.cache_manager.store_mapping.assert_not_called()


@pytest.mark.asyncio
async def test_preview_rate_limit_is_per_admin(
    preview_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DEBUG_PREVIEW_RPM", 2)
    from anonreq.debug.preview import preview_rate_limiter

    preview_rate_limiter.reset()
    transport = ASGITransport(app=preview_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(2):
            ok = await client.post(
                "/v1/debug/anonymize-preview",
                headers=_headers(),
                json={"prompt": "hello"},
            )
            assert ok.status_code == 200
        limited = await client.post(
            "/v1/debug/anonymize-preview",
            headers=_headers(),
            json={"prompt": "hello"},
        )
    assert limited.status_code == 429


@pytest.mark.asyncio
async def test_preview_does_not_log_the_body(preview_app: FastAPI) -> None:
    import structlog

    secret = "ada-secret@example.com"
    with structlog.testing.capture_logs() as captured:
        transport = ASGITransport(app=preview_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/debug/anonymize-preview",
                headers=_headers(),
                json={"prompt": f"Reach {secret} today"},
            )
    assert response.status_code == 200, response.text
    rendered = str(captured)
    assert secret not in rendered


def test_preview_pipeline_reuses_detection_and_skips_provider() -> None:
    pipeline = build_preview_pipeline(cache_manager=None, presidio_client=_EmptyPresidio())
    names = [stage.name for stage in pipeline.stages]
    assert names == [
        "ClassificationStage",
        "LocaleNegotiationStage",
        "DetectionStage",
        "SensitivityClassificationStage",
        "TokenizationStage",
    ]
    tokenization = pipeline.stages[-1]
    detection = pipeline.stages[2]
    assert tokenization._persist_mappings is False
    assert tokenization._run_when_pass is True
    assert detection._run_when_pass is True
