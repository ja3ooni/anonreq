"""Startup fail-secure tests for critical-findings Finding 6.

- Startup with a sabotaged dependency (unreachable Valkey) must raise
  ``DependencyUnavailableError`` — the gateway never serves traffic.
- ``assert_middleware_ordering`` must accept the production ordering
  (TenantContext outer / added after Policy) and reject an inverted
  registration that would silently evaluate the wrong tenant.
- Production mode with default credentials must refuse to boot (Finding 7).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from anonreq.exceptions import DependencyUnavailableError
from anonreq.startup_checks import (
    assert_middleware_ordering,
    run_startup_checks,
    validate_production_secrets,
)


def _settings_double(**overrides):
    base = {
        "PRESIDIO_URL": "http://127.0.0.1:9",
        "SINGLE_TENANT": False,
        "ENV": "development",
        "PROVIDER_API_KEY": "test-provider-key",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestSabotagedDependency:
    @pytest.mark.asyncio
    async def test_unreachable_valkey_aborts_startup(self):
        """Unreachable Valkey → DependencyUnavailableError, never serve."""
        from anonreq.cache.manager import CacheManager

        cache_manager = CacheManager("redis://127.0.0.1:9/0", ttl=300)
        try:
            with pytest.raises(DependencyUnavailableError):
                await run_startup_checks(_settings_double(), cache_manager)
        finally:
            await cache_manager.close()


class TestMiddlewareOrdering:
    def _app_with_order(self, names: list[str]):
        from anonreq.middleware.policy import PolicyMiddleware
        from anonreq.middleware.tenant import TenantContextMiddleware

        by_name = {
            "PolicyMiddleware": PolicyMiddleware,
            "TenantContextMiddleware": TenantContextMiddleware,
        }
        stack = [SimpleNamespace(cls=by_name[n]) for n in names]
        return SimpleNamespace(user_middleware=SimpleNamespace(_stack=stack))

    def test_production_ordering_accepted(self):
        """Policy added before Tenant (Tenant runs first) → OK."""
        app = self._app_with_order(["PolicyMiddleware", "TenantContextMiddleware"])
        assert_middleware_ordering(app)  # must not raise

    def test_inverted_ordering_rejected(self):
        """Tenant added before Policy (Policy would run first) → RuntimeError."""
        app = self._app_with_order(["TenantContextMiddleware", "PolicyMiddleware"])
        with pytest.raises(RuntimeError):
            assert_middleware_ordering(app)


class TestProductionSecrets:
    @pytest.mark.asyncio
    async def test_production_with_defaults_refuses_boot(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """ANONREQ_ENV=production + unset secrets → DependencyUnavailableError."""
        for var in ("MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD", "POSTGRES_PASSWORD"):
            monkeypatch.delenv(var, raising=False)
        settings = _settings_double(ENV="production", PROVIDER_API_KEY=None)
        with pytest.raises(DependencyUnavailableError):
            await validate_production_secrets(settings)

    @pytest.mark.asyncio
    async def test_development_mode_does_not_block(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Development mode never refuses on secrets (local ergonomics)."""
        for var in ("MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD", "POSTGRES_PASSWORD"):
            monkeypatch.delenv(var, raising=False)
        await validate_production_secrets(
            _settings_double(ENV="development", PROVIDER_API_KEY=None)
        )
