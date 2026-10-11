"""Tenant registry for multi-tenant segregation.

Provides:
- ``TenantRegistry`` — YAML seed tenants plus a database-backed runtime registry

Per D-05, YAML seed tenants are loaded at startup, are read-only, and win over
database rows with the same id. Runtime tenants live in the shared ``tenant``
table so every replica sees them and they survive restarts. Each replica keeps
a short-lived cache in front of the table; a change made on one replica reaches
the others within ``TENANT_CACHE_TTL_SECONDS``. If the table cannot be read the
registry raises ``TenantStoreError`` and the middleware rejects the request.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import yaml
from structlog import get_logger

from anonreq.tenant.models import TenantProfile
from anonreq.tenant.store import TenantStore, TenantStoreError

logger = get_logger("anonreq.tenant.registry")


class SeedTenantError(Exception):
    """The tenant comes from the YAML seed file and cannot be changed at runtime."""


class TenantRegistry:
    """Hybrid YAML seed + DB runtime tenant registry.

    Per D-05, YAML seed tenants are loaded at startup. The YAML wins on
    conflicts with DB-seeded tenants. The in-memory ``_tenants`` dict is
    the authoritative store for O(1) middleware lookups.

    DB persistence is a placeholder for future admin API integration.
    """

    def __init__(
        self,
        yaml_path: str,
        *,
        store: TenantStore | None = None,
        cache_ttl: float = 10.0,
        negative_ttl: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._tenants: dict[str, TenantProfile] = {}
        self._seed_ids: set[str] = set()
        self._fetched_at: dict[str, float] = {}
        self._misses: dict[str, float] = {}
        self._yaml_path = yaml_path
        self._store = store
        self._cache_ttl = cache_ttl
        self._negative_ttl = negative_ttl
        self._clock = clock
        self._load_yaml_seed()

    def attach_store(self, store: TenantStore) -> None:
        """Enable database-backed lookups. Called once the database engine exists."""
        self._store = store

    @property
    def has_store(self) -> bool:
        return self._store is not None

    def is_seed(self, tenant_id: str) -> bool:
        return tenant_id in self._seed_ids

    def _load_yaml_seed(self) -> None:
        """Load seed tenants from YAML config file.

        Uses ``yaml.safe_load()`` to prevent code injection from
        malicious YAML (per T-01-SC in the threat model).
        """
        path = Path(self._yaml_path)
        if not path.exists():
            logger.warning(
                "tenant_registry.yaml_not_found",
                path=self._yaml_path,
            )
            return

        with open(path) as f:
            data = yaml.safe_load(f)

        if not data or "tenants" not in data:
            logger.warning(
                "tenant_registry.yaml_no_tenants",
                path=self._yaml_path,
            )
            return

        for entry in data["tenants"]:
            profile = TenantProfile(
                tenant_id=entry["tenant_id"],
                display_name=entry.get("display_name", entry["tenant_id"]),
                enabled=entry.get("enabled", True),
                kms_key_arn=entry.get("kms_key_arn"),
                spend_limits=entry.get("spend_limits") or {},
                rate_limits=entry.get("rate_limits") or {},
                allowed_providers=entry.get("allowed_providers") or [],
                allowed_models=entry.get("allowed_models") or [],
            )
            self._tenants[profile.tenant_id] = profile
            self._seed_ids.add(profile.tenant_id)

        logger.info(
            "tenant_registry.loaded",
            tenant_count=len(self._tenants),
            path=self._yaml_path,
        )

    def get(self, tenant_id: str) -> TenantProfile | None:
        """Cache-only lookup by ID (seed tenants and anything already fetched).

        The request path uses ``aget`` instead, which also consults the database.
        Returns ``None`` for unknown tenant IDs.
        """
        return self._tenants.get(tenant_id)

    def list_all(self) -> list[TenantProfile]:
        """Return all registered tenant profiles."""
        return list(self._tenants.values())

    def register(self, profile: TenantProfile) -> None:
        """Add a tenant to this process's memory only.

        Not shared with other replicas and lost on restart. Kept for tests and
        single-process tooling; the admin API uses ``upsert`` instead.
        """
        self._tenants[profile.tenant_id] = profile
        logger.info(
            "tenant_registry.registered",
            tenant_id=profile.tenant_id,
        )

    # ── Database-backed API ────────────────────────────────────────────

    async def aget(self, tenant_id: str) -> TenantProfile | None:
        """Look up a tenant, reading the database when the cache is stale.

        Raises ``TenantStoreError`` if the database is needed and unavailable.
        """
        if tenant_id in self._seed_ids or self._store is None:
            return self._tenants.get(tenant_id)

        now = self._clock()
        cached = self._tenants.get(tenant_id)
        fetched = self._fetched_at.get(tenant_id)
        if cached is not None and fetched is not None and now - fetched < self._cache_ttl:
            return cached
        missed = self._misses.get(tenant_id)
        if cached is None and missed is not None and now - missed < self._negative_ttl:
            return None

        profile = await self._store.get(tenant_id)
        if profile is None:
            self._tenants.pop(tenant_id, None)
            self._fetched_at.pop(tenant_id, None)
            self._misses[tenant_id] = now
            return None
        self._remember(profile, now)
        return profile

    async def upsert(self, profile: TenantProfile) -> tuple[TenantProfile, bool]:
        """Create or update a runtime tenant. Returns ``(profile, created)``."""
        if profile.tenant_id in self._seed_ids:
            raise SeedTenantError(profile.tenant_id)
        store = self._require_store()
        stored, created = await store.upsert(profile)
        self._remember(stored, self._clock())
        return stored, created

    async def set_enabled(self, tenant_id: str, enabled: bool) -> TenantProfile | None:
        """Enable or disable a runtime tenant. ``None`` if it does not exist."""
        if tenant_id in self._seed_ids:
            raise SeedTenantError(tenant_id)
        store = self._require_store()
        stored = await store.set_enabled(tenant_id, enabled)
        if stored is not None:
            self._remember(stored, self._clock())
        return stored

    async def list_with_source(self) -> list[tuple[TenantProfile, str]]:
        """All tenants as ``(profile, source)``; source is ``seed`` or ``database``."""
        rows: dict[str, tuple[TenantProfile, str]] = {}
        if self._store is not None:
            for profile in await self._store.list_all():
                rows[profile.tenant_id] = (profile, "database")
        for tenant_id in self._seed_ids:
            rows[tenant_id] = (self._tenants[tenant_id], "seed")
        return [rows[key] for key in sorted(rows)]

    def _remember(self, profile: TenantProfile, now: float) -> None:
        self._tenants[profile.tenant_id] = profile
        self._fetched_at[profile.tenant_id] = now
        self._misses.pop(profile.tenant_id, None)

    def _require_store(self) -> TenantStore:
        if self._store is None:
            raise TenantStoreError("tenant database is not configured")
        return self._store
