"""Tenant registry for multi-tenant segregation.

Provides:
- ``TenantRegistry`` — hybrid YAML seed + DB runtime tenant registry

Per D-05, YAML seed is loaded synchronously at startup; the in-memory
dict is the authoritative store for middleware-layer lookups.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from structlog import get_logger

from anonreq.tenant.models import TenantProfile

logger = get_logger("anonreq.tenant.registry")


class TenantRegistry:
    """Hybrid YAML seed + DB runtime tenant registry.

    Per D-05, YAML seed tenants are loaded at startup. The YAML wins on
    conflicts with DB-seeded tenants. The in-memory ``_tenants`` dict is
    the authoritative store for O(1) middleware lookups.

    DB persistence is a placeholder for future admin API integration.
    """

    def __init__(self, yaml_path: str) -> None:
        self._tenants: dict[str, TenantProfile] = {}
        self._yaml_path = yaml_path
        self._load_yaml_seed()

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

        logger.info(
            "tenant_registry.loaded",
            tenant_count=len(self._tenants),
            path=self._yaml_path,
        )

    def get(self, tenant_id: str) -> TenantProfile | None:
        """Look up a tenant profile by ID.

        Returns ``None`` for unknown tenant IDs — the caller (middleware)
        decides the rejection behavior.
        """
        return self._tenants.get(tenant_id)

    def list_all(self) -> list[TenantProfile]:
        """Return all registered tenant profiles."""
        return list(self._tenants.values())

    def register(self, profile: TenantProfile) -> None:
        """Register or update a tenant in the in-memory store.

        Used by the admin API for runtime tenant management.
        The profile replaces any existing entry with the same tenant_id.
        """
        self._tenants[profile.tenant_id] = profile
        logger.info(
            "tenant_registry.registered",
            tenant_id=profile.tenant_id,
        )
