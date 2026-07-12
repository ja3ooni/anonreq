"""CapabilityResolver — startup-cached provider capability lookup.

Per D-73 through D-75:
- ``CapabilityResolver`` loads per-provider capabilities from YAML config
  at startup (authoritative source per D-74)
- Future capability pipeline: ProviderCapabilities -> Platform Policy
  Override -> Tenant Policy Override -> EffectiveCapabilities (D-75)
- MVP is startup-cached only — no runtime discovery (D-74)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
import yaml

from anonreq.providers.adapter import ProviderCapabilities

logger = structlog.get_logger("anonreq.providers.capabilities")


class CapabilityResolver:
    """Startup-cached provider capability lookup.

    Loads per-provider capabilities from ``config/capabilities.yaml``
    at construction time. The cache is static for the lifetime of the
    process in MVP.

    Future phases will add runtime capability discovery (D-74) and
    tenant-specific overrides (D-75).

    Usage::

        resolver = CapabilityResolver()
        caps = resolver.get_capabilities("anthropic")
    """

    def __init__(self, config_path: str = "config/capabilities.yaml") -> None:
        """Initialise the resolver from a YAML config file.

        Args:
            config_path: Path to the YAML configuration file relative
                to the project root.
        """
        self._capabilities: dict[str, ProviderCapabilities] = {}
        self._load_config(config_path)

    def _load_config(self, config_path: str) -> None:
        """Load the YAML config and build the capabilities mapping."""
        path = Path(config_path)
        if not path.exists():
            logger.warning("capability_resolver.config_not_found", path=config_path)
            return

        with open(path) as f:
            raw: dict[str, Any] = yaml.safe_load(f)

        provider_caps = raw.get("capabilities", {})
        for provider_name, caps_data in provider_caps.items():
            self._capabilities[provider_name] = ProviderCapabilities(**caps_data)

    def get_capabilities(
        self,
        provider: str,
        _tenant_id: str = "default",
    ) -> ProviderCapabilities:
        """Return the capabilities for a given provider.

        Args:
            provider: The provider name (e.g. 'anthropic').
            tenant_id: Tenant identifier (reserved for future tenant-specific
                overrides per D-75; currently unused).

        Returns:
            A ``ProviderCapabilities`` instance. If the provider is not
            found in the config, returns a default (all-False) instance.
        """
        return self._capabilities.get(provider, ProviderCapabilities())

    async def discover_capabilities(
        self,
        _provider: str,
    ) -> ProviderCapabilities | None:
        """Optional provider capability discovery.

        MVP: no-op — returns ``None``.

        Future: probe the provider API to discover capabilities and
        validate/enrich the YAML config. Never overrides YAML config
        per D-74.
        """
        return None
