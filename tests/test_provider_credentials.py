"""Provider credentials must never fall back to the gateway client key.

Startup refuses to boot when a configured provider that needs a key has
none. mock, local, and ollama stay usable without one.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.provider import ProviderStage
from anonreq.providers.registry import resolve_api_key
from anonreq.secrets.store import get_runtime_secret_store, set_runtime_secret_store
from anonreq.startup_checks import (
    run_startup_checks,
    validate_provider_credentials,
)

_PROVIDER_ENV = (
    "ANONREQ_OPENAI_API_KEY",
    "OPENAI_API_KEY",
    "PROVIDER_API_KEY",
    "ANONREQ_ANTHROPIC_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANONREQ_GEMINI_API_KEY",
    "GEMINI_API_KEY",
    "ANONREQ_OLLAMA_API_KEY",
    "OLLAMA_API_KEY",
)

_GATEWAY_KEY = "g" * 32


@pytest.fixture(autouse=True)
def isolated_secrets(monkeypatch: pytest.MonkeyPatch):
    """Drop provider credentials for one test and restore the secret store."""
    previous = get_runtime_secret_store()
    for name in _PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)
    set_runtime_secret_store(None)
    yield
    set_runtime_secret_store(previous)


def _settings(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "ENV": "development",
        "PROVIDER_API_KEY": None,
        "API_KEY": _GATEWAY_KEY,
        "SINGLE_TENANT": False,
        "PRESIDIO_URL": "http://127.0.0.1:9",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _only(names: list[str]):
    return lambda _path="config/model_aliases.yaml": names


class TestStartupProviderKeys:
    def test_gateway_client_key_does_not_satisfy_openai(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ANONREQ_API_KEY / settings.API_KEY is not an upstream credential."""
        monkeypatch.setenv("ANONREQ_API_KEY", _GATEWAY_KEY)
        monkeypatch.setattr(
            "anonreq.startup_checks.configured_provider_names",
            _only(["openai"]),
        )
        with pytest.raises(RuntimeError, match="PROVIDER_API_KEY") as exc_info:
            validate_provider_credentials(_settings())
        message = str(exc_info.value)
        assert "Refusing to start" in message
        assert _GATEWAY_KEY not in message
        assert "ANONREQ_API_KEY" in message

    def test_provider_api_key_does_not_satisfy_other_providers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PROVIDER_API_KEY covers OpenAI only, not Anthropic."""
        monkeypatch.setattr(
            "anonreq.startup_checks.configured_provider_names",
            _only(["anthropic"]),
        )
        with pytest.raises(RuntimeError, match="ANONREQ_ANTHROPIC_API_KEY") as exc_info:
            validate_provider_credentials(
                _settings(PROVIDER_API_KEY="upstream-openai-key")
            )
        assert "upstream-openai-key" not in str(exc_info.value)

    def test_explicit_provider_api_key_allows_openai(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "anonreq.startup_checks.configured_provider_names",
            _only(["openai"]),
        )
        validate_provider_credentials(_settings(PROVIDER_API_KEY="upstream-key"))

    @pytest.mark.parametrize("provider", ["mock", "local", "ollama"])
    def test_keyless_provider_starts_without_a_key(
        self, monkeypatch: pytest.MonkeyPatch, provider: str
    ) -> None:
        monkeypatch.setattr(
            "anonreq.startup_checks.configured_provider_names",
            _only([provider]),
        )
        validate_provider_credentials(_settings(API_KEY=_GATEWAY_KEY))

    def test_shipped_aliases_require_keyed_providers_only(self) -> None:
        """Default aliases: openai, anthropic, and gemini need keys; ollama does not."""
        with pytest.raises(RuntimeError) as exc_info:
            validate_provider_credentials(_settings())
        message = str(exc_info.value)
        assert "missing for: openai, anthropic, gemini" in message
        assert "ollama" not in message.split(".", 1)[0]
        assert _GATEWAY_KEY not in message

    def test_shipped_aliases_pass_when_keys_are_explicit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PROVIDER_API_KEY", "upstream-key")
        monkeypatch.setenv("ANONREQ_ANTHROPIC_API_KEY", "anthropic-key")
        monkeypatch.setenv("ANONREQ_GEMINI_API_KEY", "gemini-key")
        validate_provider_credentials(
            _settings(PROVIDER_API_KEY="upstream-key", API_KEY=_GATEWAY_KEY)
        )

    @pytest.mark.parametrize(
        "placeholder",
        [
            "change-me-customer-model-key",
            "CHANGE-ME-anthropic-key",
            "changeme",
            "changeme-placeholder",
            "<your-provider-api-key>",
            "your-openai-key",
            "Your-Gemini-Key",
        ],
    )
    def test_placeholder_provider_key_is_missing(
        self, monkeypatch: pytest.MonkeyPatch, placeholder: str
    ) -> None:
        """Template values fail closed at startup instead of a provider 401."""
        monkeypatch.setattr(
            "anonreq.startup_checks.configured_provider_names",
            _only(["openai"]),
        )
        monkeypatch.setenv("PROVIDER_API_KEY", placeholder)
        with pytest.raises(RuntimeError, match="missing for: openai"):
            validate_provider_credentials(_settings(PROVIDER_API_KEY=placeholder))

    def test_blank_provider_api_key_is_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "anonreq.startup_checks.configured_provider_names",
            _only(["openai"]),
        )
        with pytest.raises(RuntimeError, match="missing for: openai"):
            validate_provider_credentials(_settings(PROVIDER_API_KEY="   "))

    @patch("anonreq.startup_checks.check_cache_health", new_callable=AsyncMock)
    async def test_startup_fails_before_dependencies_when_key_missing(
        self,
        mock_cache_health: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "anonreq.startup_checks.configured_provider_names",
            _only(["openai"]),
        )
        with pytest.raises(RuntimeError, match="Refusing to start"):
            await run_startup_checks(_settings(), MagicMock())
        mock_cache_health.assert_not_awaited()

    @patch("anonreq.startup_checks.check_presidio", new_callable=AsyncMock)
    @patch("anonreq.startup_checks.check_cache_health", new_callable=AsyncMock)
    async def test_keyless_providers_pass_startup(
        self,
        mock_cache_health: AsyncMock,
        mock_presidio: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "anonreq.startup_checks.configured_provider_names",
            _only(["mock", "local", "ollama"]),
        )
        # PR #4's language probe also runs at startup; stub it here.
        monkeypatch.setattr(
            "anonreq.startup_checks.check_presidio_language",
            AsyncMock(return_value=True),
        )
        mock_cache_health.return_value = {
            "reachable": True,
            "persistence_disabled": True,
            "healthy": True,
        }
        mock_presidio.return_value = True
        for var, value in (
            ("MINIO_ROOT_USER", "minio-user-unique"),
            ("MINIO_ROOT_PASSWORD", "minio-pass-unique"),
            ("POSTGRES_PASSWORD", "pg-pass-unique"),
        ):
            monkeypatch.setenv(var, value)
        await run_startup_checks(
            _settings(ENV="production", PROVIDER_API_KEY=None),
            MagicMock(),
        )


class TestNoGatewayKeyFallback:
    def test_resolve_api_key_ignores_gateway_client_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANONREQ_API_KEY", _GATEWAY_KEY)
        with pytest.raises(ValueError, match="not a provider key"):
            resolve_api_key("openai")

    def test_resolve_api_key_openai_uses_provider_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PROVIDER_API_KEY", "explicit-upstream")
        assert resolve_api_key("openai") == "explicit-upstream"

    def test_resolve_api_key_does_not_reuse_provider_api_key_for_anthropic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PROVIDER_API_KEY", "explicit-upstream")
        with pytest.raises(ValueError, match="anthropic"):
            resolve_api_key("anthropic")

    def test_build_pipeline_does_not_use_gateway_client_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from anonreq.routing import chat as chat_mod

        monkeypatch.setattr(chat_mod.settings, "API_KEY", _GATEWAY_KEY)
        monkeypatch.setattr(chat_mod.settings, "PROVIDER_API_KEY", None)
        pipeline = chat_mod.build_pipeline(MagicMock(), MagicMock())
        stage = next(item for item in pipeline.stages if item.name == "ProviderStage")
        assert stage._api_key == ""
        assert _GATEWAY_KEY not in (stage._api_key or "")

    def test_build_pipeline_uses_explicit_provider_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from anonreq.routing import chat as chat_mod

        monkeypatch.setattr(chat_mod.settings, "API_KEY", _GATEWAY_KEY)
        monkeypatch.setattr(chat_mod.settings, "PROVIDER_API_KEY", "upstream-key")
        pipeline = chat_mod.build_pipeline(MagicMock(), MagicMock())
        stage = next(item for item in pipeline.stages if item.name == "ProviderStage")
        assert stage._api_key == "upstream-key"
        assert stage._api_key != _GATEWAY_KEY

    def test_source_has_no_gateway_key_fallback(self) -> None:
        offenders: list[str] = []
        for path in Path("src/anonreq").rglob("*.py"):
            if "or settings.API_KEY" in path.read_text():
                offenders.append(str(path))
        assert offenders == []

        watched = [Path("src/anonreq/routing/chat.py"), Path("src/anonreq/pipeline/provider.py")]
        watched.extend(Path("src/anonreq/providers").rglob("*.py"))
        for path in watched:
            for lineno, line in enumerate(path.read_text().splitlines(), start=1):
                code = line.split("#", 1)[0]
                assert "settings.API_KEY" not in code, f"{path}:{lineno}"

    async def test_blank_upstream_key_is_not_sent(self) -> None:
        stage = ProviderStage(
            openai_base_url="http://mock-provider.example",
            api_key="",
            timeout=5.0,
        )
        ctx = ProcessingContext(request_id="req", tenant_id="default")
        ctx.classification_result = {"action": "PASS"}
        ctx.original_request = {
            "model": "local",
            "messages": [{"role": "user", "content": "hi"}],
        }
        # PR #15: only the tokenized body is ever forwarded.
        ctx.transformed_request = dict(ctx.original_request)
        with respx.mock:
            route = respx.post(
                "http://mock-provider.example/v1/chat/completions"
            ).mock(return_value=httpx.Response(200, json={"choices": []}))
            await stage.execute(ctx)
        sent = route.calls[0].request.headers
        assert "authorization" not in {key.lower() for key in sent}
        assert _GATEWAY_KEY not in str(sent)
