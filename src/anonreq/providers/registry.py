"""ProviderRegistry — YAML-based adapter resolution and API key resolution.

Per D-70, D-71, D-72:
- Adapters are resolved through ``ProviderRegistry.get_adapter(provider_name)``
- YAML config at ``config/providers.yaml`` maps provider_name -> adapter class
- Dynamically imports adapter classes via ``importlib`` at resolution time
- ``ProviderNotFoundError`` raised for unknown providers (T-03-02-04)
- ``resolve_api_key()`` uses ANONREQ_{PROVIDER}_API_KEY -> {PROVIDER}_API_KEY
  fallback per D-88, never storing keys in ProcessingContext (AG-09)
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

import structlog
import yaml

from anonreq.providers.adapter import ProviderAdapter

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

    def __init__(self, config_path: str = "config/providers.yaml") -> None:
        """Initialise the registry from a YAML config file.

        Args:
            config_path: Path to the YAML configuration file relative
                to the project root.

        Raises:
            yaml.YAMLError: If the config file is malformed.
        """
        self._adapter_paths: dict[str, str] = {}
        self._adapter_cache: dict[str, type[ProviderAdapter]] = {}
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


def resolve_api_key(provider_name: str) -> str:
    """Resolve the API key for a provider from environment variables.

    Resolution order per D-88:
    1. ``ANONREQ_{PROVIDER}_API_KEY`` (preferred)
    2. ``{PROVIDER}_API_KEY`` (fallback)
    3. Raise ``ValueError`` if neither is set

    Args:
        provider_name: The provider name (e.g. 'anthropic'), uppercased
            for environment variable lookup.

    Returns:
        The API key string.

    Raises:
        ValueError: If no API key is found for the provider.
    """
    prefix = provider_name.upper()
    env_var = f"ANONREQ_{prefix}_API_KEY"
    key = os.environ.get(env_var)
    if key:
        return key

    fallback_var = f"{prefix}_API_KEY"
    key = os.environ.get(fallback_var)
    if key:
        return key

    raise ValueError(
        f"No API key found for provider '{provider_name}'. "
        f"Set {env_var} or {fallback_var} environment variable."
    )
