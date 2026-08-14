"""Unit tests for startup secret bootstrap."""

from __future__ import annotations

import os
from dataclasses import dataclass

import pytest

from anonreq.config import Settings
from anonreq.providers.registry import resolve_api_key
from anonreq.secrets.bootstrap import bootstrap_runtime_secret_store
from anonreq.secrets.store import get_runtime_secret_store, set_runtime_secret_store


@pytest.fixture(autouse=True)
def clear_runtime_secret_store() -> None:
    set_runtime_secret_store(None)
    yield
    set_runtime_secret_store(None)


@dataclass
class FakeSecretSource:
    keys: dict[str, str]

    def load_provider_api_keys(self) -> dict[str, str]:
        return dict(self.keys)


def test_bootstrap_populates_runtime_store(monkeypatch) -> None:
    set_runtime_secret_store(None)
    monkeypatch.delenv("ANONREQ_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    settings = Settings(
        API_KEY="a" * 32,
        VALKEY_URL="redis://localhost:6379/0",
        PRESIDIO_URL="http://localhost:9999",
    )
    store = bootstrap_runtime_secret_store(
        settings,
        source=FakeSecretSource({"openai": "vault-openai-key"}),
    )

    assert get_runtime_secret_store() is store
    assert store.get_provider_api_key("openai") == "vault-openai-key"
    assert resolve_api_key("openai") == "vault-openai-key"
    assert "vault-openai-key" not in settings.model_dump().values()


def test_bootstrap_does_not_mutate_env(monkeypatch) -> None:
    set_runtime_secret_store(None)
    monkeypatch.delenv("ANONREQ_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    settings = Settings(
        API_KEY="a" * 32,
        VALKEY_URL="redis://localhost:6379/0",
        PRESIDIO_URL="http://localhost:9999",
    )
    bootstrap_runtime_secret_store(
        settings,
        source=FakeSecretSource({"anthropic": "vault-anthropic-key"}),
    )

    assert "ANONREQ_OPENAI_API_KEY" not in os.environ


def test_runtime_store_precedence_over_env(monkeypatch) -> None:
    set_runtime_secret_store(None)
    monkeypatch.setenv("ANONREQ_OPENAI_API_KEY", "env-openai-key")
    monkeypatch.setenv("OPENAI_API_KEY", "fallback-openai-key")

    settings = Settings(
        API_KEY="a" * 32,
        VALKEY_URL="redis://localhost:6379/0",
        PRESIDIO_URL="http://localhost:9999",
    )
    store = bootstrap_runtime_secret_store(
        settings,
        source=FakeSecretSource({"openai": "vault-openai-key"}),
    )

    assert resolve_api_key("openai", secret_store=store) == "vault-openai-key"
    assert resolve_api_key("openai") == "vault-openai-key"
