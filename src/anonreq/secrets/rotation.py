"""Read-only secret rotation buffer for long-lived streams."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType

from anonreq.secrets.store import RuntimeSecretStore, SecretSnapshot


def _readonly_snapshot(
    provider_api_keys: Mapping[str, str],
    source: str,
) -> SecretSnapshot:
    return SecretSnapshot(
        provider_api_keys=MappingProxyType(dict(provider_api_keys)),
        source=source,
    )


@dataclass(frozen=True, slots=True)
class RotationView:
    """Immutable view of the active and previous secret snapshots."""

    current: SecretSnapshot
    previous: SecretSnapshot | None = None


class SecretRotationBuffer:
    """Keep the current secret snapshot plus per-session read-only views."""

    def __init__(self, snapshot: SecretSnapshot | None = None) -> None:
        self._lock = RLock()
        self._current = snapshot or _readonly_snapshot({}, "empty")
        self._previous: SecretSnapshot | None = None
        self._sessions: dict[str, SecretSnapshot] = {}

    def snapshot(self) -> RotationView:
        """Return the current and previous snapshots."""
        with self._lock:
            return RotationView(current=self._current, previous=self._previous)

    def current_snapshot(self) -> SecretSnapshot:
        """Return the current snapshot."""
        with self._lock:
            return self._current

    def previous_snapshot(self) -> SecretSnapshot | None:
        """Return the previous snapshot if one is retained."""
        with self._lock:
            return self._previous

    def rotate(self, snapshot: SecretSnapshot) -> tuple[SecretSnapshot, SecretSnapshot]:
        """Atomically publish a new current snapshot and retain the old one."""
        new_snapshot = _readonly_snapshot(snapshot.provider_api_keys, snapshot.source)
        with self._lock:
            old_snapshot = self._current
            self._previous = old_snapshot
            self._current = new_snapshot
            return old_snapshot, new_snapshot

    def begin_session(self, session_id: str) -> RuntimeSecretStore:
        """Bind a session to the current read-only snapshot."""
        with self._lock:
            bound_snapshot = self._current
            self._sessions[session_id] = bound_snapshot
            return RuntimeSecretStore(bound_snapshot)

    def snapshot_for_session(self, session_id: str) -> SecretSnapshot:
        """Return the snapshot bound to a session, or the current snapshot."""
        with self._lock:
            return self._sessions.get(session_id, self._current)

    def current_store(self) -> RuntimeSecretStore:
        """Return a runtime store exposing the current snapshot."""
        return RuntimeSecretStore(self.current_snapshot())

    def store_for_session(self, session_id: str) -> RuntimeSecretStore:
        """Return a runtime store bound to a stream session snapshot."""
        return RuntimeSecretStore(self.snapshot_for_session(session_id))

    def end_session(self, session_id: str) -> None:
        """Release the session-bound snapshot."""
        with self._lock:
            self._sessions.pop(session_id, None)
            if not self._sessions:
                self._previous = None

