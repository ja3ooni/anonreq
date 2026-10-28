"""ProviderRegistry — YAML-based adapter resolution and API key resolution.

Per D-70, D-71, D-72:
- Adapters are resolved through ``ProviderRegistry.get_adapter(provider_name)``
- YAML config at ``config/providers.yaml`` maps provider_name -> adapter class
- Dynamically imports adapter classes via ``importlib`` at resolution time
- ``ProviderNotFoundError`` raised for unknown providers (T-03-02-04)
- ``resolve_api_key()`` uses ANONREQ_{PROVIDER}_API_KEY -> {PROVIDER}_API_KEY
  fallback per D-88, then PROVIDER_API_KEY for OpenAI only. The gateway
  client key (ANONREQ_API_KEY) is never a provider credential. Keys are
  never stored in ProcessingContext (AG-09)
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

import structlog
import yaml

from anonreq.providers.adapter import ProviderAdapter
from anonreq.secrets.store import RuntimeSecretStore, get_runtime_secret_store

logger = structlog.get_logger("anonreq.providers.registry")


class ProviderNotFoundError(LookupError):
    """Raised when a requested provider is not configured in the registry.

    Prevents routing to unconfigured endpoints (T-03-02-04).
    """


class ProviderRegistry:
    """Provider adapter registry loaded from YAML configuration.

    Resolves ``provider_name`` to a ``ProviderAdapter`` instance using
    the mapping defined in ``config/providers.yaml``. Adapter classes
    are imported lazily — they are resolved from the YAML path string
    only when ``get_adapter()`` is called.

    Usage::

        registry = ProviderRegistry()
        adapter = registry.get_adapter("anthropic")
    """

    def __init__(
        self,
        config_path: str = "config/providers.yaml",
        secret_store: RuntimeSecretStore | None = None,
    ) -> None:
        """Initialise the registry from a YAML config file.

        Args:
            config_path: Path to the YAML configuration file relative
                to the project root.

        Raises:
            yaml.YAMLError: If the config file is malformed.
        """
        self._adapter_paths: dict[str, str] = {}
        self._adapter_cache: dict[str, type[ProviderAdapter]] = {}
        self._secret_store = secret_store or get_runtime_secret_store()
        self._load_config(config_path)

    def _load_config(self, config_path: str) -> None:
        """Load the YAML config and build the adapter path mapping.

        Uses ``yaml.safe_load()`` to prevent arbitrary code execution
        from untrusted YAML (T-03-02-05). Adapter classes are not
        imported at this point — the module path string is stored and
        resolved lazily in ``get_adapter()``.
        """
        path = Path(config_path)
        if not path.exists():
            logger.warning("provider_registry.config_not_found", path=config_path)
            return

        with open(path) as f:
            raw: dict[str, Any] = yaml.safe_load(f)

        providers = raw.get("providers", {})
        for provider_name, config in providers.items():
            self._adapter_paths[provider_name] = config["adapter"]

    def _import_adapter(self, provider_name: str) -> type[ProviderAdapter]:
        """Dynamically import and return the adapter class for a provider.

        Args:
            provider_name: The canonical provider name.

        Returns:
            The ``ProviderAdapter`` subclass for the given provider.

        Raises:
            ProviderNotFoundError: If the adapter module cannot be
                imported (not yet implemented, import error, etc.).
        """
        adapter_path = self._adapter_paths.get(provider_name)
        if adapter_path is None:
            raise ProviderNotFoundError(
                f"Unknown provider: {provider_name}. "
                f"Configured providers: {', '.join(self.list_providers())}"
            )

        if provider_name in self._adapter_cache:
            return self._adapter_cache[provider_name]

        try:
            module_path, class_name = adapter_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            adapter_class: type[ProviderAdapter] = getattr(module, class_name)
            self._adapter_cache[provider_name] = adapter_class
            return adapter_class
        except (ImportError, AttributeError) as exc:
            raise ProviderNotFoundError(  # noqa: B904
                f"Provider '{provider_name}' adapter not available: {exc}. "
                f"The adapter module may not be implemented yet."
            )

    def get_adapter(self, provider_name: str) -> ProviderAdapter:
        """Resolve and return a ProviderAdapter for the given provider.

        The adapter class is imported lazily on first call and cached
        for subsequent calls.

        Args:
            provider_name: The canonical provider name (e.g. 'anthropic').

        Returns:
            An instantiated ``ProviderAdapter`` for the given provider.

        Raises:
            ProviderNotFoundError: If the provider is not in the registry
                or its adapter module cannot be imported.
        """
        adapter_class = self._import_adapter(provider_name)
        return adapter_class()

    def list_providers(self) -> list[str]:
        """Return sorted list of configured provider names."""
        return sorted(self._adapter_paths.keys())


# Providers that serve without an upstream credential. ``local`` is the
# alias-facing name; ``ollama`` is the adapter. ``mock`` is the in-process
# / stub provider used by demos and tests.
KEYLESS_PROVIDERS = frozenset({"mock", "local", "ollama"})


def is_placeholder_credential(value: str) -> bool:
    """Return True for template values that must not be sent upstream.

    Missing means: starts with ``change-me``, equals or starts with
    ``changeme``, is an angle-bracket template (``<...>``), or matches
    ``your-...-key``. Comparison is case-insensitive.
    """
    stripped = value.strip()
    if not stripped:
        return False
    folded = stripped.casefold()
    if folded.startswith("change-me") or folded.startswith("changeme"):
        return True
    if stripped.startswith("<") and stripped.endswith(">"):
        return True
    return folded.startswith("your-") and folded.endswith("-key")


def _nonblank(value: str | None) -> str | None:
    """Return a stripped credential, or None when missing or a placeholder."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped and not is_placeholder_credential(stripped):
            return stripped
    return None


def provider_requires_api_key(
    provider_name: str,
    flags: dict[str, bool] | None = None,
) -> bool:
    """Return whether ``provider_name`` must have its own upstream key.

    ``mock`` and ``local`` never require a key. Other providers use
    ``requires_api_key`` from ``config/providers.yaml`` when present,
    and otherwise require a key unless they are in ``KEYLESS_PROVIDERS``.
    """
    normalized = provider_name.strip().casefold()
    if not normalized or normalized in {"mock", "local"}:
        return False
    if flags is not None and normalized in flags:
        return bool(flags[normalized])
    return normalized not in KEYLESS_PROVIDERS


def resolve_api_key(
    provider_name: str,
    secret_store: RuntimeSecretStore | None = None,
) -> str:
    """Resolve the API key for a provider from environment variables.

    Resolution order per D-88:
    0. runtime secret store if bootstrap has populated it
    1. ``ANONREQ_{PROVIDER}_API_KEY`` (preferred)
    2. ``{PROVIDER}_API_KEY`` (provider credential fallback)
    3. For OpenAI only, ``PROVIDER_API_KEY`` (explicit upstream key)
    4. Raise ``ValueError`` if none is set

    The gateway client key (``ANONREQ_API_KEY``) is never consulted.
    Blank values are treated as unset.

    Args:
        provider_name: The provider name (e.g. 'anthropic'), uppercased
            for environment variable lookup.

    Returns:
        The API key string.

    Raises:
        ValueError: If no API key is found for the provider.
    """
    runtime_store = secret_store or get_runtime_secret_store()
    if runtime_store is not None:
        key = _nonblank(runtime_store.get_provider_api_key(provider_name))
        if key:
            return key

    prefix = provider_name.upper()
    env_var = f"ANONREQ_{prefix}_API_KEY"
    key = _nonblank(os.environ.get(env_var))
    if key:
        return key

    fallback_var = f"{prefix}_API_KEY"
    key = _nonblank(os.environ.get(fallback_var))
    if key:
        return key

    # OpenAI-compatible upstreams share one explicit credential. This is
    # not applied to other providers, and it is never the gateway client key.
    if prefix == "OPENAI":
        shared = _nonblank(os.environ.get("PROVIDER_API_KEY"))
        if shared:
            return shared

    extra = " or PROVIDER_API_KEY" if prefix == "OPENAI" else ""
    raise ValueError(
        f"No API key found for provider '{provider_name}'. "
        f"Set {env_var} or {fallback_var}{extra}. "
        "ANONREQ_API_KEY is the gateway client credential and is not a provider key."
    )


def resolve_upstream_api_key(
    secret_store: RuntimeSecretStore | None = None,
    *,
    provider_api_key: str | None = None,
) -> str | None:
    """Resolve the OpenAI-compatible upstream key, or None when unset.

    Order matches ``resolve_api_key('openai')``, then the explicit
    ``provider_api_key`` argument (``settings.PROVIDER_API_KEY``) when the
    environment variable is unset. Never returns the gateway client key.
    """
    try:
        return resolve_api_key("openai", secret_store=secret_store)
    except ValueError:
        return _nonblank(provider_api_key)


def provider_has_credential(
    provider_name: str,
    *,
    provider_api_key: str | None = None,
    secret_store: RuntimeSecretStore | None = None,
) -> bool:
    """Return whether a non-blank upstream credential is configured.

    ``provider_api_key`` (``PROVIDER_API_KEY``) counts only for OpenAI.
    The gateway client key is not a credential for any provider.
    """
    try:
        key = resolve_api_key(provider_name, secret_store=secret_store)
    except ValueError:
        key = None
    if key:
        return True
    if provider_name.strip().casefold() == "openai":
        return _nonblank(provider_api_key) is not None
    return False
