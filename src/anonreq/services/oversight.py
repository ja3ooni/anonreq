"""Human oversight service: approval queue, kill-switch, and versioning.

Provides:
- ``ApprovalRequest`` / ``ApprovalRequestCreate`` models for the approval queue
- ``KillSwitchStatus`` model for kill-switch state
- ``OversightService`` with operations for approvals and kill-switch
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from anonreq.cache.manager import CacheManager


class ApprovalRequest(BaseModel):
    id: str
    tenant_id: str
    request_type: str
    description: str
    status: str = "pending"
    risk_score: float = 0.0
    operator_id: str | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    created_at: datetime
    metadata: dict[str, Any] = {}

    model_config = {"extra": "ignore"}


class ApprovalRequestCreate(BaseModel):
    tenant_id: str
    request_type: str
    description: str
    risk_score: float = 0.0
    metadata: dict[str, Any] = {}

    model_config = {"extra": "ignore"}


class KillSwitchStatus(BaseModel):
    active: bool
    operator_id: str | None = None
    reason: str | None = None
    activated_at: datetime | None = None

    model_config = {"extra": "ignore"}


APPROVALS_KEY = "anonreq:oversight:approvals"
KILL_SWITCH_KEY = "anonreq:oversight:kill-switch"
APPROVAL_TTL = 86400  # 24h


class OversightService:
    """Approval queue and kill-switch management.

    Stores approvals as a Redis HASH and kill-switch as a single key.
    All state is ephemeral (no disk writes), matching the AnonReq
    in-memory design philosophy.
    """

    def __init__(self, cache_manager: CacheManager) -> None:
        self._redis = cache_manager._redis

    async def create_approval_request(
        self,
        tenant_id: str,
        request_type: str,
        description: str,
        risk_score: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        request = ApprovalRequest(
            id=uuid4().hex[:24],
            tenant_id=tenant_id,
            request_type=request_type,
            description=description,
            status="pending",
            risk_score=risk_score,
            created_at=datetime.now(UTC),
            metadata=metadata or {},
        )
        await self._redis.hset(
            APPROVALS_KEY,
            request.id,
            request.model_dump_json(),
        )
        await self._redis.expire(APPROVALS_KEY, APPROVAL_TTL)
        return request

    async def list_pending_approvals(
        self,
        tenant_id: str | None = None,
    ) -> list[ApprovalRequest]:
        raw = await self._redis.hgetall(APPROVALS_KEY)
        results: list[ApprovalRequest] = []
        for _, value in raw.items():
            req = ApprovalRequest(**json.loads(value))
            if tenant_id is None or req.tenant_id == tenant_id:
                results.append(req)
        results.sort(key=lambda r: r.created_at, reverse=True)
        return results

    async def get_approval_request(
        self,
        approval_id: str,
    ) -> ApprovalRequest | None:
        raw = await self._redis.hget(APPROVALS_KEY, approval_id)
        if raw is None:
            return None
        return ApprovalRequest(**json.loads(raw))

    async def approve_request(
        self,
        approval_id: str,
        operator_id: str,
    ) -> ApprovalRequest:
        raw = await self._redis.hget(APPROVALS_KEY, approval_id)
        if raw is None:
            raise ValueError(f"Approval request not found: {approval_id}")
        req = ApprovalRequest(**json.loads(raw))
        if req.status != "pending":
            raise ValueError(
                f"Approval request {approval_id} already {req.status}"
            )
        req.status = "approved"
        req.decided_by = operator_id
        req.decided_at = datetime.now(UTC)
        await self._redis.hset(
            APPROVALS_KEY,
            approval_id,
            req.model_dump_json(),
        )
        return req

    async def reject_request(
        self,
        approval_id: str,
        operator_id: str,
    ) -> ApprovalRequest:
        raw = await self._redis.hget(APPROVALS_KEY, approval_id)
        if raw is None:
            raise ValueError(f"Approval request not found: {approval_id}")
        req = ApprovalRequest(**json.loads(raw))
        if req.status != "pending":
            raise ValueError(
                f"Approval request {approval_id} already {req.status}"
            )
        req.status = "rejected"
        req.decided_by = operator_id
        req.decided_at = datetime.now(UTC)
        await self._redis.hset(
            APPROVALS_KEY,
            approval_id,
            req.model_dump_json(),
        )
        return req

    async def activate_kill_switch(
        self,
        operator_id: str,
        reason: str,
    ) -> None:
        status = KillSwitchStatus(
            active=True,
            operator_id=operator_id,
            reason=reason,
            activated_at=datetime.now(UTC),
        )
        await self._redis.set(KILL_SWITCH_KEY, status.model_dump_json())

    async def deactivate_kill_switch(
        self,
        operator_id: str,  # noqa: ARG002
    ) -> None:
        await self._redis.delete(KILL_SWITCH_KEY)

    async def is_kill_switch_active(self) -> bool:
        raw = await self._redis.get(KILL_SWITCH_KEY)
        return raw is not None

    async def get_kill_switch_status(self) -> KillSwitchStatus:
        raw = await self._redis.get(KILL_SWITCH_KEY)
        if raw is None:
            return KillSwitchStatus(active=False)
        return KillSwitchStatus(**json.loads(raw))
