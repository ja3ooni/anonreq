"""Unit tests for model alias routing."""

from __future__ import annotations

from pathlib import Path

import pytest

from anonreq.routing.alias_registry import AliasNotFoundError, AliasRegistry


def write_aliases(path: Path, body: str) -> Path:
    path.write_text(body)
    return path


def test_resolve_alias(tmp_path: Path) -> None:
    config = write_aliases(
        tmp_path / "aliases.yaml",
        "model_aliases:\n  smart:\n    provider: anthropic\n    model: claude-sonnet-4\n",
    )
    registry = AliasRegistry(str(config))
    alias = registry.resolve("smart")
    assert alias.provider == "anthropic"
    assert alias.model == "claude-sonnet-4"


def test_resolve_is_case_insensitive(tmp_path: Path) -> None:
    config = write_aliases(
        tmp_path / "aliases.yaml",
        "model_aliases:\n  Smart:\n    provider: anthropic\n    model: claude-sonnet-4\n",
    )
    registry = AliasRegistry(str(config))
    assert registry.resolve("smart").provider == "anthropic"
    assert registry.resolve("SMART").provider == "anthropic"


def test_unknown_alias_lists_available(tmp_path: Path) -> None:
    config = write_aliases(
        tmp_path / "aliases.yaml",
        "model_aliases:\n  fast:\n    provider: openai\n    model: gpt-4o-mini\n",
    )
    registry = AliasRegistry(str(config))
    with pytest.raises(AliasNotFoundError) as exc:
        registry.resolve("missing")
    assert "fast" in str(exc.value)


def test_list_aliases_sorted(tmp_path: Path) -> None:
    config = write_aliases(
        tmp_path / "aliases.yaml",
        "model_aliases:\n  zed:\n    provider: openai\n    model: a\n  alpha:\n    provider: openai\n    model: b\n",  # noqa: E501
    )
    registry = AliasRegistry(str(config))
    assert list(registry.list_aliases()) == ["alpha", "zed"]


def test_unknown_provider_validation(tmp_path: Path) -> None:
    class Providers:
        def list_providers(self) -> list[str]:
            return ["openai"]

    config = write_aliases(
        tmp_path / "aliases.yaml",
        "model_aliases:\n  smart:\n    provider: missing\n    model: x\n",
    )
    with pytest.raises(ValueError, match="unknown provider"):
        AliasRegistry(str(config), provider_registry=Providers())  # type: ignore[arg-type]
