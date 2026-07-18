"""Data Subject Access Request (DSAR) workflow service.

Provides:
- ``DSARRequest``: Pydantic model for a DSAR case.
- ``DSARService``: Intake, processing (erasure/rectification/portability/restriction),
  status tracking, and audit trail.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, field_validator

from anonreq.cache.manager import CacheManager

VALID_REQUEST_TYPES = {"access", "erasure", "rectification", "portability", "restriction"}
VALID_STATUSES = {"pending", "processing", "completed", "rejected"}


class DSARRequest(BaseModel):
    request_id: str
    request_type: str
    tenant_id: str
    subject_id: str
    requested_by: str
    status: str = "pending"
    created_at: datetime
    completed_at: datetime | None = None
    processed_by: str | None = None
    notes: str | None = None
    result: str | None = None
    legal_hold: bool = False

    model_config = {"extra": "ignore"}

    @field_validator("request_type")
    @classmethod
    def validate_request_type(cls, v: str) -> str:
        if v not in VALID_REQUEST_TYPES:
            raise ValueError(f"Invalid request type: {v}. Must be one of {VALID_REQUEST_TYPES}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return v


DSAR_KEY_PREFIX = "anonreq:dsar"
TENANT_DSAR_PREFIX = "anonreq:dsar:tenant"
AUDIT_TRAIL_PREFIX = "anonreq:dsar:audit"


class DSARService:
    """Manages Data Subject Access Request workflows.

    Supports five DSAR types: access, erasure, rectification, portability,
    and restriction. Each request tracks status transitions and maintains
    an audit trail.
    """

    def __init__(self, cache_manager: CacheManager) -> None:
        self._redis = cache_manager._redis

    async def create_request(
        self,
        request_type: str,
        tenant_id: str,
        subject_id: str,
        requested_by: str,
        notes: str | None = None,
    ) -> DSARRequest:
        req = DSARRequest(
            request_id=str(uuid.uuid4()),
            request_type=request_type,
            tenant_id=tenant_id,
            subject_id=subject_id,
            requested_by=requested_by,
            created_at=datetime.now(UTC),
            notes=notes,
        )
        await self._redis.set(
            f"{DSAR_KEY_PREFIX}:{req.request_id}",
            req.model_dump_json(),
        )
        await self._redis.sadd(
            f"{TENANT_DSAR_PREFIX}:{tenant_id}",
            req.request_id,
        )
        await self._append_audit(req.request_id, "created", f"DSAR {request_type} created by {requested_by}")  # noqa: E501
        return req

    async def get_request(self, request_id: str) -> DSARRequest | None:
        raw = await self._redis.get(f"{DSAR_KEY_PREFIX}:{request_id}")
        if raw is None:
            return None
        return DSARRequest(**json.loads(raw))

    async def list_requests(self, tenant_id: str) -> list[DSARRequest]:
        request_ids = await self._redis.smembers(
            f"{TENANT_DSAR_PREFIX}:{tenant_id}"
        )
        requests = []
        for rid in request_ids:
            rid_str = rid.decode() if isinstance(rid, bytes) else rid
            raw = await self._redis.get(f"{DSAR_KEY_PREFIX}:{rid_str}")
            if raw:
                requests.append(DSARRequest(**json.loads(raw)))
        return requests

    async def process_erasure(
        self,
        request_id: str,
        processed_by: str,
        legal_hold: bool = False,
    ) -> DSARRequest:
        req = await self._get_request_or_raise(request_id)
        if req.request_type != "erasure":
            raise ValueError(f"Cannot process erasure for {req.request_type} request")
        now = datetime.now(UTC)
        req.status = "completed"
        req.completed_at = now
        req.processed_by = processed_by
        req.result = "legal_hold" if legal_hold else "deleted"
        req.legal_hold = legal_hold
        await self._save_and_audit(req, "erasure_processed",
                                   f"Erasure processed by {processed_by}, result: {req.result}")
        return req

    async def process_rectification(
        self,
        request_id: str,
        processed_by: str,
    ) -> DSARRequest:
        req = await self._get_request_or_raise(request_id)
        if req.request_type != "rectification":
            raise ValueError(f"Cannot process rectification for {req.request_type} request")
        now = datetime.now(UTC)
        req.status = "completed"
        req.completed_at = now
        req.processed_by = processed_by
        req.result = "rectified"
        await self._save_and_audit(req, "rectification_processed",
                                   f"Rectification processed by {processed_by}")
        return req

    async def process_portability(
        self,
        request_id: str,
        processed_by: str,
    ) -> DSARRequest:
        req = await self._get_request_or_raise(request_id)
        if req.request_type != "portability":
            raise ValueError(f"Cannot process portability for {req.request_type} request")
        now = datetime.now(UTC)
        req.status = "completed"
        req.completed_at = now
        req.processed_by = processed_by
        req.result = "data_exported"
        await self._save_and_audit(req, "portability_processed",
                                   f"Portability processed by {processed_by}")
        return req

    async def process_restriction(
        self,
        request_id: str,
        processed_by: str,
        legal_hold: bool = False,
    ) -> DSARRequest:
        req = await self._get_request_or_raise(request_id)
        if req.request_type != "restriction":
            raise ValueError(f"Cannot process restriction for {req.request_type} request")
        now = datetime.now(UTC)
        req.status = "completed"
        req.completed_at = now
        req.processed_by = processed_by
        req.result = "legal_hold" if legal_hold else "processing_restricted"
        req.legal_hold = legal_hold
        await self._save_and_audit(req, "restriction_processed",
                                   f"Restriction processed by {processed_by}, result: {req.result}")
        return req

    async def reject_request(
        self,
        request_id: str,
        reason: str,
    ) -> DSARRequest:
        req = await self._get_request_or_raise(request_id)
        req.status = "rejected"
        req.completed_at = datetime.now(UTC)
        req.result = reason
        await self._save_and_audit(req, "rejected", f"DSAR rejected: {reason}")
        return req

    async def get_status(self, request_id: str) -> str:
        req = await self.get_request(request_id)
        if req is None:
            return "not_found"
        return req.status

    async def get_audit_trail(self, request_id: str) -> list[dict[str, Any]]:
        raw = await self._redis.get(f"{AUDIT_TRAIL_PREFIX}:{request_id}")
        if raw is None:
            return []
        return list(json.loads(raw))

    async def _get_request_or_raise(self, request_id: str) -> DSARRequest:
        req = await self.get_request(request_id)
        if req is None:
            raise ValueError(f"DSAR request not found: {request_id}")
        return req

    async def _save_and_audit(self, req: DSARRequest, action: str, description: str) -> None:
        await self._redis.set(
            f"{DSAR_KEY_PREFIX}:{req.request_id}",
            req.model_dump_json(),
        )
        await self._append_audit(req.request_id, action, description)

    async def _append_audit(self, request_id: str, action: str, description: str) -> None:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "action": action,
            "description": description,
        }
        raw = await self._redis.get(f"{AUDIT_TRAIL_PREFIX}:{request_id}") or "[]"
        trail = json.loads(raw)
        trail.append(entry)
        await self._redis.set(
            f"{AUDIT_TRAIL_PREFIX}:{request_id}",
            json.dumps(trail),
        )
