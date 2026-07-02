"""Transparency service: session records, response headers, conformity packages.

Provides:
- ``TransparencyRecord`` for per-session transparency data
- ``TransparencyService`` for recording and querying transparency data
- ``add_transparency_headers`` helper for response middleware
- Conformity package generation (ZIP with SBOM, governance, risk, config audit)
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from anonreq.cache.manager import CacheManager


class TransparencyRecord(BaseModel):
    session_id: str
    tenant_id: str
    entity_count: int
    entity_types: list[str] = []
    processed_at: datetime
    anonymized: bool = True

    model_config = {"extra": "ignore"}


SESSION_KEY_PREFIX = "anonreq:transparency:session"
TENANT_SESSIONS_PREFIX = "anonreq:transparency:sessions"
ENTITY_COUNT_KEY = "anonreq:transparency:entity-count"


class TransparencyService:
    """Records and queries per-session transparency data.

    All data is stored ephemerally in Valkey, consistent with the
    AnonReq in-memory design philosophy.
    """

    def __init__(self, cache_manager: CacheManager) -> None:
        self._redis = cache_manager._redis

    def _session_key(self, session_id: str) -> str:
        return f"{SESSION_KEY_PREFIX}:{session_id}"

    def _tenant_sessions_key(self, tenant_id: str) -> str:
        return f"{TENANT_SESSIONS_PREFIX}:{tenant_id}"

    def _entity_count_key(self, tenant_id: str) -> str:
        return f"{ENTITY_COUNT_KEY}:{tenant_id}"

    async def record_session(
        self,
        tenant_id: str,
        session_id: str,
        entity_count: int,
        entity_types: list[str],
        anonymized: bool = True,
    ) -> TransparencyRecord:
        record = TransparencyRecord(
            session_id=session_id,
            tenant_id=tenant_id,
            entity_count=entity_count,
            entity_types=entity_types,
            processed_at=datetime.now(timezone.utc),
            anonymized=anonymized,
        )
        await self._redis.set(
            self._session_key(session_id),
            record.model_dump_json(),
            ex=86400,
        )
        await self._redis.rpush(
            self._tenant_sessions_key(tenant_id),
            session_id,
        )
        await self._redis.expire(self._tenant_sessions_key(tenant_id), 86400)
        current = await self._redis.get(self._entity_count_key(tenant_id)) or "0"
        await self._redis.set(
            self._entity_count_key(tenant_id),
            str(int(current) + entity_count),
            ex=86400,
        )
        return record

    async def get_session_record(
        self,
        session_id: str,
    ) -> TransparencyRecord | None:
        raw = await self._redis.get(self._session_key(session_id))
        if raw is None:
            return None
        return TransparencyRecord(**json.loads(raw))

    async def list_sessions(
        self,
        tenant_id: str,
    ) -> list[TransparencyRecord]:
        session_ids = await self._redis.lrange(
            self._tenant_sessions_key(tenant_id), 0, -1
        )
        records: list[TransparencyRecord] = []
        for sid in session_ids:
            raw = await self._redis.get(self._session_key(sid))
            if raw:
                records.append(TransparencyRecord(**json.loads(raw)))
        return records

    async def get_total_entity_count(
        self,
        tenant_id: str,
    ) -> int:
        raw = await self._redis.get(self._entity_count_key(tenant_id))
        return int(raw) if raw else 0

    async def generate_conformity_package(
        self,
        tenant_id: str,
    ) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            governance_data = {
                "tenant_id": tenant_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "package_type": "conformity",
                "version": "1.0",
            }
            zf.writestr("governance.json", json.dumps(governance_data, indent=2))

            risk_data = {
                "tenant_id": tenant_id,
                "assessments": [],
            }
            zf.writestr("risk_assessments.json", json.dumps(risk_data, indent=2))

            sbom_data = {
                "service": "AnonReq",
                "version": "1.0",
                "components": [
                    {"name": "Python", "version": "3.12"},
                    {"name": "FastAPI", "version": "0.x"},
                    {"name": "Presidio Analyzer"},
                    {"name": "Valkey/Redis"},
                ],
            }
            zf.writestr("sbom.json", json.dumps(sbom_data, indent=2))

            config_audit = {
                "tenant_id": tenant_id,
                "events": [],
            }
            zf.writestr("config_audit.json", json.dumps(config_audit, indent=2))

            sessions = await self.list_sessions(tenant_id)
            zf.writestr(
                "transparency_records.json",
                json.dumps([s.model_dump(mode="json") for s in sessions], indent=2),
            )

        return buf.getvalue()


def add_transparency_headers(
    response: Any,
    processed: bool = True,
    entity_count: int = 0,
) -> None:
    """Add X-AnonReq-Processed and X-AnonReq-Entity-Count response headers."""
    response.headers["X-AnonReq-Processed"] = "true" if processed else "false"
    response.headers["X-AnonReq-Entity-Count"] = str(entity_count)
