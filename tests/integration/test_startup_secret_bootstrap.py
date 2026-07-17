"""Integration test for startup secret bootstrap wiring."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from anonreq.config import Settings
from anonreq.main import bootstrap_runtime_secrets
from anonreq.providers.registry import resolve_api_key
from anonreq.secrets.store import set_runtime_secret_store


@dataclass
class FakeSecretSource:
    keys: dict[str, str]

    def load_provider_api_keys(self) -> dict[str, str]:
        return dict(self.keys)


@pytest.fixture(autouse=True)
def clear_runtime_secret_store() -> None:
    set_runtime_secret_store(None)
    yield
    set_runtime_secret_store(None)


@pytest.mark.asyncio
async def test_create_app_bootstraps_runtime_secret_store(monkeypatch) -> None:
    settings = Settings(
        API_KEY="a" * 32,
        VALKEY_URL="redis://localhost:6379/0",
        PRESIDIO_URL="http://localhost:9999",
    )

    fake_source = FakeSecretSource({"openai": "startup-openai-key"})

    monkeypatch.setattr("anonreq.main.settings", settings)
    app = SimpleNamespace(state=SimpleNamespace(secret_backend_client=fake_source))

    bootstrap_runtime_secrets(app)
    assert app.state.secret_store is not None
    assert app.state.provider_registry is not None
    assert app.state.provider_registry._secret_store is app.state.secret_store
    assert resolve_api_key("openai") == "startup-openai-key"
