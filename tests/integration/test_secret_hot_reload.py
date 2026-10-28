"""Integration tests for secret hot reload wiring."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

from anonreq.main import bootstrap_secret_volume_reloader
from anonreq.providers.registry import resolve_api_key
from anonreq.secrets.store import RuntimeSecretStore

# Production polling stays at the watchdog default (1s). Tests use a short
# interval so the deadline below covers many polls.
_TEST_POLL_INTERVAL = 0.05


def _wait_until(predicate, timeout: float = 5.0, interval: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


def _publish_secret(path: Path, payload: str) -> None:
    """Replace ``path`` with a stat change the polling watcher can see.

    PollingObserver reports a modification only when ``st_mtime`` or
    ``st_size`` changes, and a create/move when the inode changes. The
    startup and rotated payloads are the same length, and mtime on this
    filesystem advances in ~4ms ticks, so a fast in-place rewrite is often
    invisible for the whole deadline. Rename onto the path (new inode) and
    step mtime by one second, which also survives 1s timestamp truncation.
    """
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(payload)
    stamped = time.time_ns() + 1_000_000_000
    os.utime(temporary, ns=(stamped, stamped))
    os.replace(temporary, path)


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

    reloader = bootstrap_secret_volume_reloader(app, poll_interval=_TEST_POLL_INTERVAL)
    assert reloader is not None

    try:
        assert resolve_api_key("openai", secret_store=store) == "startup-key"
        assert reloader.wait_until_baseline(timeout=5.0), (
            "secret watcher did not record a baseline snapshot before the deadline"
        )

        _publish_secret(secret_file, json.dumps({"openai": "rotated-key"}))
        assert _wait_until(
            lambda: resolve_api_key("openai", secret_store=store) == "rotated-key"
        ), "runtime store did not observe the rotated key before the deadline"
        assert resolve_api_key("openai") == "rotated-key"
    finally:
        reloader.close()
