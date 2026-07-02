"""Model alias schema for provider-independent routing."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from anonreq.providers.adapter import ProviderCapabilities


class ModelAlias(BaseModel):
    """Maps a client-visible model alias to a provider-specific model."""

    provider: str
    model: str
    capabilities: ProviderCapabilities | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    fallback: dict[str, str] | None = None
    routes: list[dict[str, Any]] | None = None

    model_config = {"extra": "ignore"}
