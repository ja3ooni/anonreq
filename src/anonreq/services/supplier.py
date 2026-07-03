"""Supplier governance service.

Provides:
- ``SupplierRecord``: Provider inventory with risk, contract, and review data.
- ``SupplierService``: Register, query, update, and manage providers.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import BaseModel

from anonreq.cache.manager import CacheManager


class SupplierRecord(BaseModel):
    provider_name: str
    legal_entity: str = ""
    jurisdiction: str = ""
    data_residency_regions: list[str] = []
    risk_classification: str = "Low"
    contract_status: str = "Active"
    last_risk_review_date: datetime | None = None
    data_processing_agreement_ref: str | None = None
    sub_processor_list_ref: str | None = None
    ict_concentration_risk: bool = False
    review_cycle_days: int = 365
    suspended_by: str | None = None
    suspended_at: datetime | None = None

    model_config = {"extra": "ignore"}


SUPPLIER_KEY_PREFIX = "anonreq:supplier"
SUPPLIER_INDEX_KEY = "anonreq:supplier:index"


class SupplierService:
    """Supplier/provider inventory with governance oversight.

    Tracks provider risk classification, contract status, review cycles,
    and ICT concentration risk indicators.
    """

    def __init__(self, cache_manager: CacheManager) -> None:
        self._redis = cache_manager._redis

    async def register_provider(self, record: SupplierRecord) -> SupplierRecord:
        await self._redis.set(
            f"{SUPPLIER_KEY_PREFIX}:{record.provider_name}",
            record.model_dump_json(),
        )
        await self._redis.sadd(SUPPLIER_INDEX_KEY, record.provider_name)
        return record

    async def get_provider(self, provider_name: str) -> SupplierRecord | None:
        raw = await self._redis.get(f"{SUPPLIER_KEY_PREFIX}:{provider_name}")
        if raw is None:
            return None
        return SupplierRecord(**json.loads(raw))

    async def list_providers(self) -> list[SupplierRecord]:
        names = await self._redis.smembers(SUPPLIER_INDEX_KEY)
        providers = []
        for name in names:
            name_str = name.decode() if isinstance(name, bytes) else name
            raw = await self._redis.get(f"{SUPPLIER_KEY_PREFIX}:{name_str}")
            if raw:
                providers.append(SupplierRecord(**json.loads(raw)))
        return providers

    async def update_provider(
        self,
        provider_name: str,
        **kwargs,
    ) -> SupplierRecord:
        raw = await self._redis.get(f"{SUPPLIER_KEY_PREFIX}:{provider_name}")
        if raw is None:
            raise ValueError(f"Provider not found: {provider_name}")
        record = SupplierRecord(**json.loads(raw))
        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)
        await self._redis.set(
            f"{SUPPLIER_KEY_PREFIX}:{provider_name}",
            record.model_dump_json(),
        )
        return record

    async def suspend_provider(
        self,
        provider_name: str,
        suspended_by: str,
    ) -> SupplierRecord:
        return await self.update_provider(
            provider_name,
            contract_status="Suspended",
            suspended_by=suspended_by,
            suspended_at=datetime.now(timezone.utc),
        )

    async def get_overdue_providers(self) -> list[SupplierRecord]:
        providers = await self.list_providers()
        now = datetime.now(timezone.utc)
        overdue = []
        for p in providers:
            if p.last_risk_review_date is None:
                overdue.append(p)
            else:
                elapsed = (now - p.last_risk_review_date).days
                if elapsed > p.review_cycle_days:
                    overdue.append(p)
        return overdue

    async def get_critical_providers(self) -> list[SupplierRecord]:
        providers = await self.list_providers()
        return [p for p in providers if p.risk_classification == "Critical"]

    async def get_concentration_risk_providers(self) -> list[SupplierRecord]:
        providers = await self.list_providers()
        return [p for p in providers if p.ict_concentration_risk]

    async def export_providers(self) -> list[dict]:
        providers = await self.list_providers()
        return [p.model_dump(mode="json") for p in providers]
