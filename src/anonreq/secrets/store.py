"""In-memory runtime secret store.

The store keeps provider credentials in memory only and exposes a small
lookup API that runtime code can use without learning the source backend.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar, Token
from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType
from typing import Protocol


class SecretSource(Protocol):
    """Protocol for startup secret sources."""

    def load_provider_api_keys(self) -> Mapping[str, str]:
        """Return provider name -> API key mappings."""


@dataclass(frozen=True, slots=True)
class SecretSnapshot:
    """Immutable snapshot of in-memory secrets."""

    provider_api_keys: Mapping[str, str]
    source: str = "unknown"


class RuntimeSecretStore:
    """Thread-safe in-memory secret snapshot container."""

    def __init__(self, snapshot: SecretSnapshot | None = None) -> None:
        self._lock = RLock()
        self._snapshot = snapshot or SecretSnapshot(provider_api_keys=MappingProxyType({}))

    def replace(self, snapshot: SecretSnapshot) -> None:
        """Atomically replace the current snapshot."""
        with self._lock:
            self._snapshot = SecretSnapshot(
                provider_api_keys=MappingProxyType(dict(snapshot.provider_api_keys)),
                source=snapshot.source,
            )

    def snapshot(self) -> SecretSnapshot:
        """Return the current immutable snapshot."""
        with self._lock:
            return self._snapshot

    def get_provider_api_key(self, provider_name: str) -> str | None:
        """Return the API key for a provider if present."""
        with self._lock:
            return self._snapshot.provider_api_keys.get(provider_name)


_runtime_secret_store: RuntimeSecretStore | None = None
_runtime_secret_store_ctx: ContextVar[RuntimeSecretStore | None] = ContextVar(
    "anonreq_runtime_secret_store",
    default=None,
)


def set_runtime_secret_store(store: RuntimeSecretStore | None) -> None:
    """Set the process-wide runtime secret store."""
    global _runtime_secret_store
    _runtime_secret_store = store


def push_runtime_secret_store(store: RuntimeSecretStore | None) -> Token[RuntimeSecretStore | None]:
    """Bind a request-scoped runtime secret store for the current context."""
    return _runtime_secret_store_ctx.set(store)


def reset_runtime_secret_store(token: Token[RuntimeSecretStore | None]) -> None:
    """Reset the request-scoped runtime secret store binding."""
    _runtime_secret_store_ctx.reset(token)


def get_runtime_secret_store() -> RuntimeSecretStore | None:
    """Return the current process-wide runtime secret store."""
    scoped_store = _runtime_secret_store_ctx.get()
    if scoped_store is not None:
        return scoped_store
    return _runtime_secret_store
