"""Security regression tests for critical-findings Findings 1, 2, and 4.

- Finding 1: ``verify_api_key`` must route through ``hmac.compare_digest``
  (timing-safe); a future refactor must not silently reintroduce ``!=``.
- Finding 2: admin legacy API-key fallback must also use ``compare_digest``.
- Finding 4: ``ProviderStage`` client errors must be generic — stubbed
  upstream bodies (stack traces, paths, PII) must never appear in
  ``PipelineAbortError.message``.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from anonreq.detection.presidio_client import PresidioClient
from anonreq.exceptions import PipelineAbortError
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.provider import ProviderStage


class TestTimingSafeApiKeyComparison:
    async def test_verify_api_key_routes_through_compare_digest(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """verify_api_key must call hmac.compare_digest (Finding 1)."""
        monkeypatch.setenv("ANONREQ_API_KEY", "a" * 32)
        monkeypatch.setenv("ANONREQ_VALKEY_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("ANONREQ_PRESIDIO_URL", "http://localhost:5001")

        import importlib

        from anonreq import config as config_module

        importlib.reload(config_module)

        from anonreq import dependencies as deps_module

        importlib.reload(deps_module)

        creds = type("Creds", (), {"credentials": "a" * 32})()
        with patch(
            "anonreq.dependencies.hmac.compare_digest",
            wraps=__import__("hmac").compare_digest,
        ) as spy:
            result = await deps_module.verify_api_key(creds)  # type: ignore[arg-type]
            assert result == "a" * 32
            assert spy.called, "verify_api_key must route through hmac.compare_digest"

    def test_verify_api_key_source_has_no_bare_inequality(self):
        """Source guard: no ``token !=`` / ``!= token`` comparison remains."""
        import anonreq.dependencies as deps_module

        source = inspect.getsource(deps_module.verify_api_key)
        assert "compare_digest" in source
        assert "!=" not in source, (
            "verify_api_key must not use bare != for key comparison"
        )


class TestAdminLegacyKeyComparison:
    def test_admin_legacy_path_uses_compare_digest(self):
        """Admin legacy fallback must use compare_digest (Finding 2)."""
        import anonreq.admin.auth as admin_auth

        source = inspect.getsource(admin_auth.verify_admin_api_key)
        assert "compare_digest" in source

    async def test_admin_legacy_wrong_key_is_401(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Wrong admin key → 401, never passthrough."""
        from fastapi import HTTPException, Request

        from anonreq.admin import auth as admin_auth

        monkeypatch.setattr(admin_auth.settings, "OIDC_ISSUER", None)
        monkeypatch.setattr(admin_auth.settings, "OIDC_AUDIENCE", None)
        monkeypatch.setattr(admin_auth.settings, "OIDC_JWKS_URL", None)
        monkeypatch.setattr(
            admin_auth.settings, "ADMIN_API_KEY", "admin-key-" + "x" * 32
        )

        scope = {"type": "http", "method": "GET", "path": "/"}
        request = Request(scope)
        with pytest.raises(HTTPException) as exc_info:
            await admin_auth.verify_admin_api_key(
                request, authorization="Bearer wrong-key"
            )
        assert exc_info.value.status_code == 401


_UPSTREAM_LEAK_BODY = {
    "error": {
        "message": "Traceback /etc/passwd SECRET-LEAK-TOKEN db password=hunter2",
        "type": "internal_stack_trace",
    }
}


def _leak_ctx() -> ProcessingContext:
    return ProcessingContext(
        request_id="leak_test_001",
        tenant_id="default",
        original_request={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        },
    )


class TestProviderErrorGeneric:
    @pytest.mark.asyncio
    async def test_provider_http_error_message_is_generic(self):
        """Upstream body substrings must never reach the client error (Finding 4)."""
        stage = ProviderStage(
            openai_base_url="http://mock-provider.example",
            api_key="test-key",
            timeout=5.0,
        )
        ctx = _leak_ctx()
        with respx.mock:
            respx.post("http://mock-provider.example/v1/chat/completions").mock(
                return_value=httpx.Response(500, json=_UPSTREAM_LEAK_BODY)
            )
            ctx = await stage.execute(ctx)

        assert ctx.has_errors()
        last = ctx.errors[-1]
        assert isinstance(last, PipelineAbortError)
        assert last.status_code == 502
        for secret in ("Traceback", "/etc/passwd", "SECRET-LEAK-TOKEN", "hunter2"):
            assert secret not in last.message, (
                f"upstream content leaked into client error: {secret!r}"
            )
        assert "Provider returned HTTP 500" in last.message

    @pytest.mark.asyncio
    async def test_provider_uses_no_follow_redirects(self):
        """Shared client must not follow redirects (SSRF guard, Finding 4)."""
        stage = ProviderStage(
            openai_base_url="http://mock-provider.example",
            api_key="test-key",
            timeout=5.0,
        )
        client = stage._client
        assert client.follow_redirects is False
        await stage.close()

    @pytest.mark.asyncio
    async def test_provider_source_has_no_error_body_interpolation(self):
        """Source guard: no error_body interpolation into client messages."""
        import anonreq.pipeline.provider as provider_module

        source = inspect.getsource(provider_module.ProviderStage.execute)
        assert "error_body" not in source or "str(error_body)" not in source, (
            "execute() must not interpolate error_body into client messages"
        )
        # Only error_type is logged server-side; client messages stay generic.
        assert "Provider returned HTTP" in source
