from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_serializer


class PolicyAction(str, Enum):
    BLOCK = "BLOCK"
    ALLOW = "ALLOW"
    ROUTE_LOCAL = "ROUTE_LOCAL"
    FLAG_AND_FORWARD = "FLAG_AND_FORWARD"
    MONITOR = "MONITOR"


_REGION_PATTERN = re.compile(r"^[a-z]{2}(-[a-z0-9]+)+-\d+$")


class PolicyRule(BaseModel):
    model_config = {"extra": "forbid"}

    rule_id: str = Field(min_length=1)
    enabled: bool = True
    version: int = 1
    name: str = ""
    description: str | None = None
    action: PolicyAction
    priority: int = 0
    conditions: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str | None = None


class PolicyDecision(BaseModel):
    model_config = {"extra": "forbid"}

    action: PolicyAction
    matched_rule_ids: list[str]
    decision_ts: datetime
    ttl_seconds: int = Field(default=60, gt=0)
    reason: str | None = None
    enforcement: str | None = None

    @field_validator("decision_ts", mode="before")
    @classmethod
    def _ensure_datetime(cls, v: Any) -> datetime:
        if isinstance(v, datetime):
            return v
        raise ValueError("decision_ts must be a datetime object")


class RateLimitConfig(BaseModel):
    model_config = {"extra": "forbid"}

    rpm: int = Field(default=1000, gt=0)
    tpm: int = Field(default=100000, gt=0)
    concurrent: int = Field(default=50, gt=0)
    enabled: bool = True


class SpendBudget(BaseModel):
    model_config = {"extra": "forbid"}

    daily_usd: Decimal | None = None
    monthly_usd: Decimal | None = None
    currency: str = "USD"
    enabled: bool = True

    @field_validator("daily_usd", "monthly_usd", mode="before")
    @classmethod
    def _coerce_decimal(cls, v: Any) -> Decimal | None:
        if v is None:
            return None
        val = Decimal(str(v))
        if val < 0:
            raise ValueError("Spend limit must be non-negative")
        return val


class UsageRecord(BaseModel):
    model_config = {"extra": "forbid"}

    tenant_id: str = Field(min_length=1)
    rpm_current: int = Field(ge=0)
    tpm_current: int = Field(ge=0)
    concurrent_current: int = Field(ge=0)
    daily_spend: Decimal = Field(default=Decimal("0"), ge=0)
    monthly_spend: Decimal = Field(default=Decimal("0"), ge=0)
    reset_at: datetime

    @field_validator("daily_spend", "monthly_spend", mode="before")
    @classmethod
    def _coerce_decimal_spend(cls, v: Any) -> Decimal:
        return Decimal(str(v))

    @field_validator("reset_at", mode="before")
    @classmethod
    def _ensure_datetime(cls, v: Any) -> datetime:
        if isinstance(v, datetime):
            return v
        raise ValueError("reset_at must be a datetime object")


@model_serializer
def _ser_decimal(self) -> float:
    return float(self)


class ResidencyRule(BaseModel):
    model_config = {"extra": "forbid"}

    allowed_regions: list[str] = Field(min_length=1)
    blocked_regions: list[str] = Field(default_factory=list)
    fallback_action: PolicyAction = PolicyAction.BLOCK
    required: bool = False

    @field_validator("allowed_regions")
    @classmethod
    def _validate_region_codes(cls, v: list[str]) -> list[str]:
        for region in v:
            if not _REGION_PATTERN.match(region):
                raise ValueError(
                    f"Invalid region code: '{region}'. Must match pattern like 'us-east-1'"
                )
        return v

    @field_validator("blocked_regions")
    @classmethod
    def _validate_blocked_region_codes(cls, v: list[str]) -> list[str]:
        for region in v:
            if not _REGION_PATTERN.match(region):
                raise ValueError(
                    f"Invalid region code: '{region}'. Must match pattern like 'us-east-1'"
                )
        return v
