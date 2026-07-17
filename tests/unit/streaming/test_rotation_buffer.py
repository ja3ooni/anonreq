"""Unit tests for the read-only secret rotation buffer."""

from __future__ import annotations

from types import MappingProxyType

from anonreq.providers.registry import resolve_api_key
from anonreq.secrets.rotation import SecretRotationBuffer
from anonreq.secrets.store import (
    SecretSnapshot,
    push_runtime_secret_store,
    reset_runtime_secret_store,
)


def _snapshot(provider_api_keys: dict[str, str], source: str) -> SecretSnapshot:
    return SecretSnapshot(
        provider_api_keys=MappingProxyType(dict(provider_api_keys)),
        source=source,
    )


def test_active_session_keeps_previous_snapshot_across_rotation() -> None:
    buffer = SecretRotationBuffer(_snapshot({"openai": "old-key"}, "initial"))

    session_store = buffer.begin_session("stream-1")
    token = push_runtime_secret_store(session_store)
    try:
        assert resolve_api_key("openai") == "old-key"

        buffer.rotate(_snapshot({"openai": "new-key"}, "rotated"))
        assert resolve_api_key("openai") == "old-key"
        assert buffer.current_snapshot().provider_api_keys["openai"] == "new-key"
        assert buffer.previous_snapshot().provider_api_keys["openai"] == "old-key"
    finally:
        reset_runtime_secret_store(token)
        buffer.end_session("stream-1")


def test_new_session_sees_latest_snapshot() -> None:
    buffer = SecretRotationBuffer(_snapshot({"openai": "old-key"}, "initial"))
    buffer.rotate(_snapshot({"openai": "new-key"}, "rotated"))

    new_session_store = buffer.begin_session("stream-2")
    token = push_runtime_secret_store(new_session_store)
    try:
        assert resolve_api_key("openai") == "new-key"
    finally:
        reset_runtime_secret_store(token)
        buffer.end_session("stream-2")

