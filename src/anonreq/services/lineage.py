"""Immutable data lineage service.

Provides:
- ``LineageRecord``: Pydantic model for a single lineage entry.
- ``LineageService``: Store, query, and verify integrity of lineage records.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime

from pydantic import BaseModel

from anonreq.cache.manager import CacheManager


class LineageRecord(BaseModel):
    session_id: str
    tenant_id: str
    timestamp_request_received: datetime
    timestamp_provider_forwarded: datetime | None = None
    timestamp_response_delivered: datetime | None = None
    source_application_id: str | None = None
    provider_routed_to: str | None = None
    model_used: str | None = None
    entities_anonymized_count: dict[str, int] = {}
    compliance_preset_applied: str | None = None
    classification_level_applied: str | None = None
    policy_actions_applied: list[str] = []
    integrity_hash: str = ""

    model_config = {"extra": "ignore"}


LINEAGE_KEY_PREFIX = "anonreq:lineage"
TENANT_INDEX_PREFIX = "anonreq:lineage:tenant"
SIGNING_KEY = b"anonreq-lineage-hmac-key-v1"


def _compute_integrity_hash(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hmac.new(SIGNING_KEY, canonical.encode(), hashlib.sha256).hexdigest()


class LineageService:
    """Immutable lineage record store.

    Records are write-once with HMAC-SHA256 integrity tags.
    No update or delete operations are exposed.
    """

    def __init__(self, cache_manager: CacheManager) -> None:
        self._redis = cache_manager._redis

    async def create_record(self, record: LineageRecord) -> LineageRecord:
        payload = record.model_dump(mode="json")
        payload.pop("integrity_hash", None)
        payload["integrity_hash"] = _compute_integrity_hash(payload)
        record.integrity_hash = payload["integrity_hash"]
        await self._redis.set(
            f"{LINEAGE_KEY_PREFIX}:{record.session_id}",
            json.dumps(payload),
        )
        await self._redis.sadd(
            f"{TENANT_INDEX_PREFIX}:{record.tenant_id}",
            record.session_id,
        )
        return record

    async def get_record(self, session_id: str) -> LineageRecord | None:
        raw = await self._redis.get(f"{LINEAGE_KEY_PREFIX}:{session_id}")
        if raw is None:
            return None
        return LineageRecord(**json.loads(raw))

    async def list_records(self, tenant_id: str) -> list[LineageRecord]:
        session_ids = await self._redis.smembers(
            f"{TENANT_INDEX_PREFIX}:{tenant_id}"
        )
        records = []
        for sid in session_ids:
            sid_str = sid.decode() if isinstance(sid, bytes) else sid
            raw = await self._redis.get(f"{LINEAGE_KEY_PREFIX}:{sid_str}")
            if raw:
                records.append(LineageRecord(**json.loads(raw)))
        return records

    async def verify_integrity(self, session_id: str) -> bool:
        raw = await self._redis.get(f"{LINEAGE_KEY_PREFIX}:{session_id}")
        if raw is None:
            return False
        data = json.loads(raw)
        stored_hash = data.pop("integrity_hash", "")
        computed = _compute_integrity_hash(data)
        return hmac.compare_digest(stored_hash, computed)
