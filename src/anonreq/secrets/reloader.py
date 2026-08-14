"""Watchdog-backed in-memory secret volume reloader."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import yaml

from anonreq.secrets.rotation import SecretRotationBuffer
from anonreq.secrets.store import (
    RuntimeSecretStore,
    SecretSnapshot,
    get_runtime_secret_store,
    set_runtime_secret_store,
)

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers.polling import PollingObserver as Observer
except ImportError:  # pragma: no cover - watchdog is a runtime dependency
    Observer = None  # type: ignore[assignment,misc]
    FileSystemEventHandler = object  # type: ignore[assignment,misc]

if TYPE_CHECKING:
    from watchdog.observers.polling import PollingObserver as _PollingObserverType


class SecretReloadError(RuntimeError):
    """Raised when a secret volume cannot be loaded or reloaded."""


def load_secret_snapshot(secret_path: str | Path) -> SecretSnapshot:
    """Load provider API keys from a YAML secret volume."""
    path = Path(secret_path)
    with path.open() as f:
        raw = yaml.safe_load(f) or {}

    if isinstance(raw, dict) and "provider_api_keys" in raw:
        raw = raw["provider_api_keys"]

    if not isinstance(raw, dict):
        raise SecretReloadError("secret volume must contain a mapping of provider keys")

    return SecretSnapshot(
        provider_api_keys=MappingProxyType(
            {
                str(provider): str(api_key)
                for provider, api_key in raw.items()
                if api_key is not None
            }
        ),
        source=path.name,
    )


class _SecretFileHandler(FileSystemEventHandler):
    """Watchdog event handler that debounces file updates."""

    def __init__(self, reloader: SecretVolumeReloader, debounce: float = 0.5) -> None:
        self._reloader = reloader
        self._debounce = debounce
        self._last_trigger = 0.0

    def on_created(self, event: Any) -> None:  # pragma: no cover - integration exercised
        self._maybe_reload(event)

    def on_modified(self, event: Any) -> None:  # pragma: no cover - integration exercised
        self._maybe_reload(event)

    def on_moved(self, event: Any) -> None:  # pragma: no cover - integration exercised
        self._maybe_reload(event)

    def _maybe_reload(self, event: Any) -> None:
        if getattr(event, "is_directory", False):
            return

        target = self._reloader.secret_path.resolve()
        paths = [getattr(event, "src_path", None), getattr(event, "dest_path", None)]
        if not any(path and Path(path).resolve() == target for path in paths):
            return

        now = time.monotonic()
        if now - self._last_trigger < self._debounce:
            return
        self._last_trigger = now
        self._reloader.reload()


class SecretVolumeReloader:
    """Reload a mounted secret file into the in-memory runtime store."""

    def __init__(
        self,
        secret_path: str | Path,
        store: RuntimeSecretStore | None = None,
        rotation_buffer: SecretRotationBuffer | None = None,
        debounce: float = 0.5,
    ) -> None:
        self.secret_path = Path(secret_path)
        self._store = store or get_runtime_secret_store() or RuntimeSecretStore()
        set_runtime_secret_store(self._store)
        self._lock = threading.RLock()
        self._rotation_buffer = rotation_buffer
        self._snapshot = load_secret_snapshot(self.secret_path)
        self._store.replace(self._snapshot)
        self._observer: _PollingObserverType | None = None
        self._start_watcher(debounce)

    def _start_watcher(self, debounce: float) -> None:
        if Observer is None:
            return
        handler = _SecretFileHandler(self, debounce=debounce)
        observer = Observer()
        observer.schedule(handler, str(self.secret_path.parent), recursive=False)
        observer.daemon = True
        observer.start()
        self._observer = observer

    def reload(self) -> tuple[SecretSnapshot, SecretSnapshot]:
        """Load the latest secrets and atomically replace the runtime snapshot."""
        old_snapshot = self.snapshot()
        try:
            snapshot = load_secret_snapshot(self.secret_path)
        except Exception as exc:
            raise SecretReloadError(str(exc)) from exc

        with self._lock:
            self._snapshot = snapshot
            self._store.replace(snapshot)
            if self._rotation_buffer is not None:
                self._rotation_buffer.rotate(snapshot)
            return old_snapshot, self._snapshot

    def snapshot(self) -> SecretSnapshot:
        """Return the current immutable snapshot."""
        with self._lock:
            return self._snapshot

    def close(self) -> None:
        """Stop the watchdog observer if one was started."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None


def bootstrap_runtime_secret_reloader(
    app: Any,
    secret_path: str | None = None,
) -> SecretVolumeReloader | None:
    """Attach a secret volume reloader when the app exposes a secret path."""
    path = secret_path or getattr(app.state, "secret_volume_path", None)
    if not path:
        app.state.secret_reloader = None
        return None

    reloader = SecretVolumeReloader(
        secret_path=path,
        store=getattr(app.state, "secret_store", None),
        rotation_buffer=getattr(app.state, "secret_rotation_buffer", None),
    )
    app.state.secret_reloader = reloader
    return reloader
