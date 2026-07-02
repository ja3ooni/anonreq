"""YAML-backed model alias registry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from anonreq.providers.registry import ProviderRegistry
from anonreq.routing.model_alias import ModelAlias


class AliasNotFoundError(Exception):
    """Raised when a request references an unknown model alias."""

    def __init__(self, alias_name: str, available_aliases: list[str]) -> None:
        self.alias_name = alias_name
        self.available_aliases = sorted(available_aliases)
        super().__init__(str(self))

    def __str__(self) -> str:
        aliases = ", ".join(self.available_aliases)
        return f"Alias '{self.alias_name}' not found. Available aliases: {aliases}"


class AliasRegistry:
    """Resolves client-visible aliases to provider/model pairs."""

    def __init__(
        self,
        config_path: str = "config/model_aliases.yaml",
        provider_registry: ProviderRegistry | None = None,
    ) -> None:
        self._aliases: dict[str, ModelAlias] = {}
        self._display_names: dict[str, str] = {}
        self._provider_registry = provider_registry
        self._load_config(config_path)
        self._validate()

    def _load_config(self, config_path: str) -> None:
        path = Path(config_path)
        if not path.exists():
            return
        with path.open() as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}
        for name, data in (raw.get("model_aliases") or {}).items():
            key = name.casefold()
            if key in self._aliases:
                raise ValueError(f"Duplicate model alias: {name}")
            self._aliases[key] = ModelAlias.model_validate(data)
            self._display_names[key] = name

    def _validate(self) -> None:
        if self._provider_registry is None:
            return
        providers = set(self._provider_registry.list_providers())
        for alias_name, alias in self._aliases.items():
            if alias.provider not in providers:
                raise ValueError(
                    f"Alias '{self._display_names[alias_name]}' references unknown provider '{alias.provider}'"
                )

    def resolve(self, alias: str) -> ModelAlias:
        key = alias.casefold()
        if key not in self._aliases:
            raise AliasNotFoundError(alias, self.list_aliases().keys() | set())
        return self._aliases[key]

    def list_aliases(self) -> dict[str, ModelAlias]:
        return {
            self._display_names[key]: self._aliases[key]
            for key in sorted(self._aliases)
        }

    def resolve_provider_and_model(self, alias: str) -> tuple[str, str]:
        resolved = self.resolve(alias)
        return resolved.provider, resolved.model
