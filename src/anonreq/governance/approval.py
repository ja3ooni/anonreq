"""ApprovalManager — async human approval flow for high-risk tool calls.

Per D-005, D-006, D-007, D-008:
- Async model: tool call suspended, added to oversight queue
- Client receives HTTP 202 with approval_token
- Client polls approval status via GET /v1/oversight/approvals/{token}
- Approval decisions resolve the token (approved/denied)

Per T-18-02-01, T-18-02-02:
- 256-bit random token is cryptographically unguessable
- Single-use, TTL-scoped
- Atomic operations prevent tampering
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from fastapi import HTTPException

from anonreq.cache.manager import CacheManager
from anonreq.governance.tool_extractor import ToolCall
from anonreq.models.processing_context import ProcessingContext


APPROVAL_KEY_PREFIX = "anonreq:approval:"


class ApprovalStatus(str, Enum):
    """Status of an approval request.

    PENDING: Awaiting human decision.
    APPROVED: Approved by human operator.
    DENIED: Denied by human operator.
    EXPIRED: TTL passed without decision.
    """

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class ApprovalRecord:
    """Data record for a single approval token.

    Stores tool call context and decision state in a Valkey HASH.
    """

    __slots__ = (
        "token",
        "tool_call",
        "context_id",
        "tenant_id",
        "status",
        "created_at",
        "expires_at",
        "decided_by",
        "decided_at",
        "approval_note",
    )

    def __init__(
        self,
        token: str,
        tool_call: ToolCall,
        context_id: str,
        tenant_id: str = "default",
        status: ApprovalStatus = ApprovalStatus.PENDING,
        created_at: datetime | None = None,
        expires_at: datetime | None = None,
        decided_by: str | None = None,
        decided_at: datetime | None = None,
        approval_note: str | None = None,
    ) -> None:
        self.token = token
        self.tool_call = tool_call
        self.context_id = context_id
        self.tenant_id = tenant_id
        self.status = status
        now = datetime.now(timezone.utc)
        self.created_at = created_at or now
        self.expires_at = expires_at or now
        self.decided_by = decided_by
        self.decided_at = decided_at
        self.approval_note = approval_note

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for Valkey storage."""
        return {
            "token": self.token,
            "tool_call": json.dumps(
                {
                    "id": self.tool_call.id,
                    "name": self.tool_call.name,
                    "arguments": self.tool_call.arguments,
                    "format": self.tool_call.format,
                    "domain": self.tool_call.domain,
                    "provider": self.tool_call.provider,
                },
                default=str,
            ),
            "context_id": self.context_id,
            "tenant_id": self.tenant_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "decided_by": self.decided_by or "",
            "decided_at": self.decided_at.isoformat() if self.decided_at else "",
            "approval_note": self.approval_note or "",
        }

    @classmethod
    def from_dict(cls, data: dict[str, str], token: str) -> ApprovalRecord:
        """Deserialize from Valkey HASH data."""
        tool_call_data = json.loads(data.get("tool_call", "{}"))
        tool_call = ToolCall(
            id=tool_call_data.get("id", ""),
            name=tool_call_data.get("name", ""),
            arguments=tool_call_data.get("arguments", {}),
            format=tool_call_data.get("format", "openai"),
            domain=tool_call_data.get("domain", "model"),
            provider=tool_call_data.get("provider"),
        )

        decided_at_str = data.get("decided_at", "")
        decided_by = data.get("decided_by") or None
        approval_note = data.get("approval_note") or None

        return cls(
            token=token,
            tool_call=tool_call,
            context_id=data.get("context_id", ""),
            tenant_id=data.get("tenant_id", "default"),
            status=ApprovalStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else None,
            expires_at=datetime.fromisoformat(data["expires_at"]) if "expires_at" in data else None,
            decided_by=decided_by,
            decided_at=datetime.fromisoformat(decided_at_str) if decided_at_str else None,
            approval_note=approval_note,
        )


class ApprovalManager:
    """Manages async human approval flow for high-risk tool calls.

    Creates pending approvals, stores in Valkey with cryptographically
    random tokens, supports approve/deny/status check, and integrates
    with the Phase 14 oversight queue.
    """

    def __init__(
        self,
        cache_manager: CacheManager,
        oversight_service: Any | None = None,
        ttl: int = 300,
    ) -> None:
        """Initialize the ApprovalManager.

        Args:
            cache_manager: CacheManager backed by Valkey/Redis.
            oversight_service: Optional Phase 14 OversightService for
                queue integration.
            ttl: Default TTL for approval tokens in seconds (default 300).
        """
        self._cache_manager = cache_manager
        self._redis = cache_manager._redis
        self._oversight_service = oversight_service
        self._ttl = ttl

    async def create_approval(
        self,
        tool_call: ToolCall,
        context: ProcessingContext,
    ) -> dict[str, Any]:
        """Create a pending approval for a tool call.

        Generates a 256-bit cryptographically random token, stores the
        approval record in Valkey, and optionally adds to the oversight
        queue. Returns HTTP 202-compatible response.

        Args:
            tool_call: The tool call requiring approval.
            context: Processing context with tenant/request info.

        Returns:
            Dict with ``approval_token`` and ``status="pending"``.
        """
        token = secrets.token_urlsafe(32)  # 256-bit entropy
        now = datetime.now(timezone.utc)
        expires_at = now.replace(microsecond=0) + timedelta(seconds=self._ttl)

        record = ApprovalRecord(
            token=token,
            tool_call=tool_call,
            context_id=context.context_id or "",
            tenant_id=context.tenant_id,
            status=ApprovalStatus.PENDING,
            created_at=now,
            expires_at=expires_at,
        )

        # Store in Valkey HASH
        # Redis TTL is longer than the business TTL so the record
        # persists long enough for the data-level expiry check.
        # Actual expiry is determined by the stored expires_at field.
        redis_ttl = max(self._ttl + 3600, 7200)
        key = f"{APPROVAL_KEY_PREFIX}{token}"
        async with self._redis.pipeline(transaction=True) as pipe:
            await (
                pipe.hset(key, mapping=record.to_dict())
                .expire(key, redis_ttl)
                .execute()
            )

        # Optionally add to Phase 14 oversight queue
        if self._oversight_service is not None:
            try:
                await self._oversight_service.create_approval_request(
                    tenant_id=context.tenant_id,
                    request_type="tool_approval",
                    description=f"Tool call '{tool_call.name}' requires human approval",
                    risk_score=0.8,
                    metadata={
                        "approval_token": token,
                        "tool_name": tool_call.name,
                        "tool_id": tool_call.id,
                        "context_id": context.context_id,
                    },
                )
            except Exception:
                pass  # Non-critical — token is already stored

        return {
            "approval_token": token,
            "status": "pending",
        }

    async def get_approval_status(self, token: str) -> dict[str, Any]:
        """Get the current status of an approval token.

        Returns status including pending/approved/denied/expired.
        If the token is unknown, returns status=not_found.

        Args:
            token: The approval token to check.

        Returns:
            Dict with ``approval_token`` and ``status``.
        """
        key = f"{APPROVAL_KEY_PREFIX}{token}"
        raw = await self._redis.hgetall(key)
        if not raw:
            return {"approval_token": token, "status": "not_found"}

        # Check for expiry
        expires_at_str = raw.get("expires_at", "")
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str)
            now = datetime.now(timezone.utc)
            if now > expires_at and raw.get("status") == ApprovalStatus.PENDING.value:
                # Mark as expired
                raw["status"] = ApprovalStatus.EXPIRED.value
                await self._redis.hset(key, "status", ApprovalStatus.EXPIRED.value)

        return {
            "approval_token": token,
            "status": raw.get("status", "unknown"),
            "created_at": raw.get("created_at", ""),
            "expires_at": raw.get("expires_at", ""),
            "decided_by": raw.get("decided_by") or None,
            "decided_at": raw.get("decided_at") or None,
        }

    async def approve_approval(
        self,
        token: str,
        decided_by: str,
        note: str = "",
    ) -> dict[str, Any]:
        """Approve a pending approval token.

        Resolves the token to APPROVED and returns the tool call
        context for execution.

        Args:
            token: The approval token to approve.
            decided_by: Identifier of the human operator.
            note: Optional approval note.

        Returns:
            Dict with status, decision info, and tool_call.

        Raises:
            HTTPException 404: Token not found.
            HTTPException 409: Token already resolved.
        """
        key = f"{APPROVAL_KEY_PREFIX}{token}"
        raw = await self._redis.hgetall(key)
        if not raw:
            raise HTTPException(status_code=404, detail="Approval token not found")

        current_status = raw.get("status", "")
        if current_status != ApprovalStatus.PENDING.value:
            raise HTTPException(
                status_code=409,
                detail=f"Approval token already resolved: {current_status}",
            )

        now = datetime.now(timezone.utc)
        raw["status"] = ApprovalStatus.APPROVED.value
        raw["decided_by"] = decided_by
        raw["decided_at"] = now.isoformat()
        raw["approval_note"] = note

        # Update Valkey with 60s TTL extension for post-decision cleanup
        async with self._redis.pipeline(transaction=True) as pipe:
            await (
                pipe.hset(key, mapping=raw)
                .expire(key, 60)
                .execute()
            )

        # Return tool call context for execution
        tool_call_data = json.loads(raw.get("tool_call", "{}"))
        return {
            "status": ApprovalStatus.APPROVED.value,
            "decided_by": decided_by,
            "decided_at": raw["decided_at"],
            "approval_note": note,
            "tool_call": tool_call_data,
        }

    async def deny_approval(
        self,
        token: str,
        decided_by: str,
        note: str = "",
    ) -> dict[str, Any]:
        """Deny a pending approval token.

        Resolves the token to DENIED.

        Args:
            token: The approval token to deny.
            decided_by: Identifier of the human operator.
            note: Optional denial reason.

        Returns:
            Dict with status and decision info.

        Raises:
            HTTPException 404: Token not found.
            HTTPException 409: Token already resolved.
        """
        key = f"{APPROVAL_KEY_PREFIX}{token}"
        raw = await self._redis.hgetall(key)
        if not raw:
            raise HTTPException(status_code=404, detail="Approval token not found")

        current_status = raw.get("status", "")
        if current_status != ApprovalStatus.PENDING.value:
            raise HTTPException(
                status_code=409,
                detail=f"Approval token already resolved: {current_status}",
            )

        now = datetime.now(timezone.utc)
        raw["status"] = ApprovalStatus.DENIED.value
        raw["decided_by"] = decided_by
        raw["decided_at"] = now.isoformat()
        raw["approval_note"] = note

        # Update Valkey with 60s TTL extension
        async with self._redis.pipeline(transaction=True) as pipe:
            await (
                pipe.hset(key, mapping=raw)
                .expire(key, 60)
                .execute()
            )

        return {
            "status": ApprovalStatus.DENIED.value,
            "decided_by": decided_by,
            "decided_at": raw["decided_at"],
            "approval_note": note,
        }

    async def cleanup_expired(self) -> int:
        """Scan and delete expired approvals.

        Returns the count of expired approvals deleted.
        """
        # Scan for approval keys using SCAN cursor
        cursor = 0
        deleted = 0
        pattern = f"{APPROVAL_KEY_PREFIX}*"
        now = datetime.now(timezone.utc)

        while True:
            cursor, keys = await self._redis.scan(cursor=cursor, match=pattern, count=100)
            for key in keys:
                raw = await self._redis.hgetall(key)
                if not raw:
                    continue
                expires_at_str = raw.get("expires_at", "")
                if not expires_at_str:
                    continue
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                except ValueError:
                    continue
                if now > expires_at and raw.get("status") == ApprovalStatus.PENDING.value:
                    await self._redis.delete(key)
                    deleted += 1
            if cursor == 0:
                break

        return deleted
