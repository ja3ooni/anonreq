"""Secret bootstrap helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from anonreq.config import Settings
from anonreq.secrets.store import (
    RuntimeSecretStore,
    SecretSnapshot,
    SecretSource,
    set_runtime_secret_store,
)


class SecretBootstrapError(RuntimeError):
    """Raised when startup secret bootstrap fails."""


@dataclass(slots=True)
class VaultSecretSource:
    """Vault-backed secret source using hvac."""

    secret_path: str
    mount_point: str = "secret"
    vault_addr: str | None = None
    vault_token: str | None = None

    def load_provider_api_keys(self) -> Mapping[str, str]:
        try:
            import hvac  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover - covered by integration tests when installed
            raise SecretBootstrapError("hvac is required for Vault secret bootstrap") from exc

        addr = self.vault_addr or os.environ.get("VAULT_ADDR")
        token = self.vault_token or os.environ.get("VAULT_TOKEN")
        if not addr or not token:
            raise SecretBootstrapError("Vault address/token are required for secret bootstrap")

        client = hvac.Client(url=addr, token=token)
        if not client.is_authenticated():
            raise SecretBootstrapError("Vault authentication failed")

        secret = client.secrets.kv.v2.read_secret_version(
            path=self.secret_path,
            mount_point=self.mount_point,
        )
        data = secret.get("data", {}).get("data", {})
        return {str(key): str(value) for key, value in data.items() if value is not None}


def build_secret_source(settings: Settings) -> SecretSource:
    """Build the configured secret source."""
    backend = settings.SECRET_BACKEND.strip().casefold()
    if backend == "vault":
        return VaultSecretSource(secret_path=settings.SECRET_BACKEND_PATH)
    raise SecretBootstrapError(f"Unsupported secret backend: {settings.SECRET_BACKEND}")


def bootstrap_runtime_secret_store(
    settings: Settings,
    source: SecretSource | None = None,
) -> RuntimeSecretStore:
    """Load provider secrets into the process-wide in-memory store."""
    secret_source = source or build_secret_source(settings)
    snapshot = SecretSnapshot(
        provider_api_keys=MappingProxyType(dict(secret_source.load_provider_api_keys())),
        source=secret_source.__class__.__name__,
    )
    store = RuntimeSecretStore(snapshot)
    set_runtime_secret_store(store)
    return store
