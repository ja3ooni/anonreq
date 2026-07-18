"""Tenant data models for multi-tenant segregation.

Provides:
- ``TenantProfile`` — denormalized dataclass for fast middleware-layer lookup
- ``TenantRegistryModel`` — SQLAlchemy model mapping to the ``tenant`` table

Per D-06, TenantProfile duplicates some policy engine data for O(1)
middleware access without cross-tenant bleed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


@dataclass
class TenantProfile:
    """Denormalized tenant profile for fast middleware-layer lookup.

    Per D-06, this carries all tenant-specific configuration needed by
    middleware, cache, and policy evaluation without hitting the database
    on every request.
    """

    tenant_id: str
    display_name: str
    enabled: bool = True
    kms_key_arn: str | None = None
    spend_limits: dict[str, Any] = field(default_factory=dict)
    rate_limits: dict[str, Any] = field(default_factory=dict)
    allowed_providers: list[str] = field(default_factory=list)
    allowed_models: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class TenantRegistryModel(Base):
    """SQLAlchemy model for the ``tenant`` table.

    Maps to the same schema defined in the Alembic migration
    ``003_create_tenant_table.py``. Provides bidirectional conversion
    with ``TenantProfile`` via ``from_model`` and ``to_profile``.
    """

    __tablename__ = "tenant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    kms_key_arn: Mapped[str | None] = mapped_column(String(512), nullable=True)
    spend_limits_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    rate_limits_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_providers_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_models_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    @classmethod
    def from_model(cls, profile: TenantProfile) -> TenantRegistryModel:
        """Convert a ``TenantProfile`` dataclass to a ``TenantRegistryModel``."""
        return cls(
            tenant_id=profile.tenant_id,
            display_name=profile.display_name,
            enabled=profile.enabled,
            kms_key_arn=profile.kms_key_arn,
            spend_limits_json=json.dumps(profile.spend_limits) if profile.spend_limits else None,
            rate_limits_json=json.dumps(profile.rate_limits) if profile.rate_limits else None,
            allowed_providers_json=(
                json.dumps(profile.allowed_providers)
                if profile.allowed_providers else None
            ),
            allowed_models_json=(
                json.dumps(profile.allowed_models)
                if profile.allowed_models else None
            ),
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    def to_profile(self) -> TenantProfile:
        """Convert this ``TenantRegistryModel`` to a ``TenantProfile`` dataclass."""
        return TenantProfile(
            tenant_id=self.tenant_id,
            display_name=self.display_name,
            enabled=self.enabled,
            kms_key_arn=self.kms_key_arn,
            spend_limits=json.loads(self.spend_limits_json) if self.spend_limits_json else {},
            rate_limits=json.loads(self.rate_limits_json) if self.rate_limits_json else {},
            allowed_providers=(
                json.loads(self.allowed_providers_json)
                if self.allowed_providers_json else []
            ),
            allowed_models=(
                json.loads(self.allowed_models_json)
                if self.allowed_models_json else []
            ),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
