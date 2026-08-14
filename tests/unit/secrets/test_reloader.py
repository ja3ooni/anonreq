"""Unit tests for secret volume reload behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anonreq.providers.registry import resolve_api_key
from anonreq.secrets.reloader import SecretReloadError, SecretVolumeReloader, load_secret_snapshot
from anonreq.secrets.store import RuntimeSecretStore, set_runtime_secret_store


@pytest.fixture(autouse=True)
def clear_runtime_secret_store() -> None:
    set_runtime_secret_store(None)
    yield
    set_runtime_secret_store(None)


def test_load_secret_snapshot_reads_json_mapping(tmp_path: Path) -> None:
    secret_file = tmp_path / "provider-api-keys.json"
    secret_file.write_text(
        json.dumps(
            {
                "provider_api_keys": {
                    "openai": "snapshot-openai-key",
                    "anthropic": "snapshot-anthropic-key",
                }
            }
        )
    )

    snapshot = load_secret_snapshot(secret_file)

    assert snapshot.provider_api_keys["openai"] == "snapshot-openai-key"
    assert snapshot.provider_api_keys["anthropic"] == "snapshot-anthropic-key"


def test_reload_replaces_snapshot_atomically(tmp_path: Path) -> None:
    secret_file = tmp_path / "provider-api-keys.json"
    secret_file.write_text(json.dumps({"openai": "initial-key"}))

    store = RuntimeSecretStore()
    reloader = SecretVolumeReloader(secret_file, store=store)

    try:
        assert reloader.snapshot().provider_api_keys["openai"] == "initial-key"
        assert resolve_api_key("openai", secret_store=store) == "initial-key"

        secret_file.write_text(json.dumps({"openai": "rotated-key"}))
        old_snapshot, new_snapshot = reloader.reload()

        assert old_snapshot.provider_api_keys["openai"] == "initial-key"
        assert new_snapshot.provider_api_keys["openai"] == "rotated-key"
        assert resolve_api_key("openai", secret_store=store) == "rotated-key"
        assert resolve_api_key("openai") == "rotated-key"
    finally:
        reloader.close()


def test_reload_failure_keeps_previous_snapshot(tmp_path: Path) -> None:
    secret_file = tmp_path / "provider-api-keys.json"
    secret_file.write_text(json.dumps({"openai": "stable-key"}))

    store = RuntimeSecretStore()
    reloader = SecretVolumeReloader(secret_file, store=store)
    try:
        assert reloader.snapshot().provider_api_keys["openai"] == "stable-key"

        secret_file.write_text("{broken")
        with pytest.raises(SecretReloadError):
            reloader.reload()

        assert resolve_api_key("openai", secret_store=store) == "stable-key"
    finally:
        reloader.close()
