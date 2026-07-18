"""Retention management with Legal Hold support.

Provides:
- ``RetentionPolicy``: Per-record-type retention schedule.
- ``LegalHold``: A hold suspension blocking record deletion.
- ``RetentionService``: CRUD for policies and holds, hold enforcement.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from anonreq.cache.manager import CacheManager


class RetentionPolicy(BaseModel):
    record_type: str
    retention_days: int
    disposition_action: str = "delete"

    model_config = {"extra": "ignore"}


class LegalHold(BaseModel):
    hold_id: str
    record_types: list[str]
    tenant_id: str
    hold_ref: str
    imposed_by: str
    imposed_at: datetime
    released_at: datetime | None = None
    released_by: str | None = None
    filters: dict[str, Any] | None = None

    model_config = {"extra": "ignore"}


POLICY_KEY_PREFIX = "anonreq:retention:policy"
HOLD_KEY_PREFIX = "anonreq:legalhold"
HOLD_INDEX_KEY = "anonreq:legalhold:index"


class RetentionService:
    """Manages retention policies and Legal Holds.

    Policies define per-record-type retention. Legal Holds override
    policies by blocking deletion of matching records.
    """

    def __init__(self, cache_manager: CacheManager) -> None:
        self._redis = cache_manager._redis

    async def set_policy(
        self,
        record_type: str,
        retention_days: int,
        disposition_action: str = "delete",
    ) -> RetentionPolicy:
        policy = RetentionPolicy(
            record_type=record_type,
            retention_days=retention_days,
            disposition_action=disposition_action,
        )
        await self._redis.set(
            f"{POLICY_KEY_PREFIX}:{record_type}",
            policy.model_dump_json(),
        )
        return policy

    async def get_policy(self, record_type: str) -> RetentionPolicy | None:
        raw = await self._redis.get(f"{POLICY_KEY_PREFIX}:{record_type}")
        if raw is None:
            return None
        return RetentionPolicy(**json.loads(raw))

    async def list_policies(self) -> list[RetentionPolicy]:
        keys = await self._redis.keys(f"{POLICY_KEY_PREFIX}:*")
        policies = []
        for key in keys:
            raw = await self._redis.get(key)
            if raw:
                policies.append(RetentionPolicy(**json.loads(raw)))
        return policies

    async def impose_hold(
        self,
        record_types: list[str],
        tenant_id: str,
        hold_ref: str,
        imposed_by: str,
        filters: dict[str, Any] | None = None,
    ) -> LegalHold:
        hold = LegalHold(
            hold_id=str(uuid.uuid4()),
            record_types=record_types,
            tenant_id=tenant_id,
            hold_ref=hold_ref,
            imposed_by=imposed_by,
            imposed_at=datetime.now(UTC),
            filters=filters,
        )
        await self._redis.set(
            f"{HOLD_KEY_PREFIX}:{hold.hold_id}",
            hold.model_dump_json(),
        )
        await self._redis.sadd(HOLD_INDEX_KEY, hold.hold_id)
        return hold

    async def release_hold(
        self,
        hold_id: str,
        released_by: str,
    ) -> LegalHold:
        raw = await self._redis.get(f"{HOLD_KEY_PREFIX}:{hold_id}")
        if raw is None:
            raise ValueError(f"Hold not found: {hold_id}")
        hold = LegalHold(**json.loads(raw))
        hold.released_at = datetime.now(UTC)
        hold.released_by = released_by
        await self._redis.set(
            f"{HOLD_KEY_PREFIX}:{hold_id}",
            hold.model_dump_json(),
        )
        return hold

    async def get_hold(self, hold_id: str) -> LegalHold | None:
        raw = await self._redis.get(f"{HOLD_KEY_PREFIX}:{hold_id}")
        if raw is None:
            return None
        return LegalHold(**json.loads(raw))

    async def list_holds(self) -> list[LegalHold]:
        hold_ids = await self._redis.smembers(HOLD_INDEX_KEY)
        holds = []
        for hid in hold_ids:
            hid_str = hid.decode() if isinstance(hid, bytes) else hid
            hold = await self.get_hold(hid_str)
            if hold is not None:
                holds.append(hold)
        return holds

    async def is_hold_active(
        self, record_type: str, tenant_id: str
    ) -> bool:
        hold_ids = await self._redis.smembers(HOLD_INDEX_KEY)
        for hid in hold_ids:
            hid_str = hid.decode() if isinstance(hid, bytes) else hid
            raw = await self._redis.get(f"{HOLD_KEY_PREFIX}:{hid_str}")
            if raw is None:
                continue
            hold = LegalHold(**json.loads(raw))
            if hold.released_at is not None:
                continue
            if hold.tenant_id != tenant_id:
                continue
            if record_type not in hold.record_types:
                continue
            return True
        return False
