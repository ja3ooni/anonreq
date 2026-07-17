"""Integration tests for secret hot reload wiring."""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

from anonreq.main import bootstrap_secret_volume_reloader
from anonreq.providers.registry import resolve_api_key
from anonreq.secrets.store import RuntimeSecretStore


def _wait_until(predicate, timeout: float = 5.0, interval: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def test_secret_hot_reload_updates_runtime_store(tmp_path: Path) -> None:
    secret_file = tmp_path / "provider-api-keys.json"
    secret_file.write_text(json.dumps({"openai": "startup-key"}))

    store = RuntimeSecretStore()
    app = SimpleNamespace(
        state=SimpleNamespace(
            secret_store=store,
            secret_volume_path=str(secret_file),
        )
    )

    reloader = bootstrap_secret_volume_reloader(app)

    try:
        assert resolve_api_key("openai", secret_store=store) == "startup-key"

        secret_file.write_text(json.dumps({"openai": "rotated-key"}))
        assert _wait_until(
            lambda: resolve_api_key("openai", secret_store=store) == "rotated-key"
        )
        assert resolve_api_key("openai") == "rotated-key"
    finally:
        reloader.close()
