"""Breach notification service.

Provides:
- ``BreachTemplate``: Configurable notification templates.
- ``BreachNotification``: A breach notification event.
- ``BreachService``: Create, send, acknowledge, and close notifications.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel

from anonreq.cache.manager import CacheManager


class BreachTemplate(BaseModel):
    name: str
    subject: str
    body: str
    channels: list[str] = ["email"]

    model_config = {"extra": "ignore"}


class BreachNotification(BaseModel):
    breach_id: str
    severity: str
    tenant_id: str
    description: str
    template_name: str = "default"
    detected_at: datetime
    detected_by: str = "system"
    status: str = "pending"
    sent_at: datetime | None = None
    sent_by: str | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    closed_at: datetime | None = None
    closed_by: str | None = None
    delivered: bool = False
    regulator_queue: bool = False
    affected_tenants: list[str] = []

    model_config = {"extra": "ignore"}


TEMPLATE_KEY_PREFIX = "anonreq:breach-template"
BREACH_KEY_PREFIX = "anonreq:breach"
TENANT_BREACH_PREFIX = "anonreq:breach:tenant"
REGULATOR_QUEUE_KEY = "anonreq:breach:regulator-queue"


class BreachService:
    """Manages breach notification lifecycle.

    Supports configurable templates, regulator notification queue,
    and affected-tenant notification workflows.
    """

    def __init__(self, cache_manager: CacheManager) -> None:
        self._redis = cache_manager._redis

    async def set_template(
        self,
        name: str,
        subject: str,
        body: str,
        channels: list[str] | None = None,
    ) -> BreachTemplate:
        template = BreachTemplate(
            name=name,
            subject=subject,
            body=body,
            channels=channels or ["email"],
        )
        await self._redis.set(
            f"{TEMPLATE_KEY_PREFIX}:{name}",
            template.model_dump_json(),
        )
        return template

    async def get_template(self, name: str) -> BreachTemplate | None:
        raw = await self._redis.get(f"{TEMPLATE_KEY_PREFIX}:{name}")
        if raw is None:
            return None
        return BreachTemplate(**json.loads(raw))

    async def delete_template(self, name: str) -> None:
        await self._redis.delete(f"{TEMPLATE_KEY_PREFIX}:{name}")

    async def create_notification(
        self,
        severity: str,
        tenant_id: str,
        description: str,
        template_name: str,
        detected_by: str = "system",
        regulator_queue: bool = False,
    ) -> BreachNotification:
        now = datetime.now(timezone.utc)
        notification = BreachNotification(
            breach_id=str(uuid.uuid4()),
            severity=severity,
            tenant_id=tenant_id,
            description=description,
            template_name=template_name,
            detected_at=now,
            detected_by=detected_by,
            regulator_queue=regulator_queue,
        )
        await self._redis.set(
            f"{BREACH_KEY_PREFIX}:{notification.breach_id}",
            notification.model_dump_json(),
        )
        await self._redis.sadd(
            f"{TENANT_BREACH_PREFIX}:{tenant_id}",
            notification.breach_id,
        )
        if regulator_queue:
            await self._redis.sadd(REGULATOR_QUEUE_KEY, notification.breach_id)
        return notification

    async def send_notification(self, breach_id: str) -> BreachNotification:
        notification = await self._get_notification_or_raise(breach_id)
        now = datetime.now(timezone.utc)
        notification.status = "sent"
        notification.sent_at = now
        notification.delivered = True
        await self._redis.set(
            f"{BREACH_KEY_PREFIX}:{breach_id}",
            notification.model_dump_json(),
        )
        return notification

    async def get_notification(self, breach_id: str) -> BreachNotification | None:
        raw = await self._redis.get(f"{BREACH_KEY_PREFIX}:{breach_id}")
        if raw is None:
            return None
        return BreachNotification(**json.loads(raw))

    async def list_notifications(self, tenant_id: str) -> list[BreachNotification]:
        breach_ids = await self._redis.smembers(
            f"{TENANT_BREACH_PREFIX}:{tenant_id}"
        )
        notifications = []
        for bid in breach_ids:
            bid_str = bid.decode() if isinstance(bid, bytes) else bid
            raw = await self._redis.get(f"{BREACH_KEY_PREFIX}:{bid_str}")
            if raw:
                notifications.append(BreachNotification(**json.loads(raw)))
        return notifications

    async def get_regulator_queue(self) -> list[BreachNotification]:
        breach_ids = await self._redis.smembers(REGULATOR_QUEUE_KEY)
        notifications = []
        for bid in breach_ids:
            bid_str = bid.decode() if isinstance(bid, bytes) else bid
            notification = await self.get_notification(bid_str)
            if notification is not None:
                notifications.append(notification)
        return notifications

    async def acknowledge(
        self,
        breach_id: str,
        acknowledged_by: str,
    ) -> BreachNotification:
        notification = await self._get_notification_or_raise(breach_id)
        notification.status = "acknowledged"
        notification.acknowledged_at = datetime.now(timezone.utc)
        notification.acknowledged_by = acknowledged_by
        await self._redis.set(
            f"{BREACH_KEY_PREFIX}:{breach_id}",
            notification.model_dump_json(),
        )
        return notification

    async def close(
        self,
        breach_id: str,
        closed_by: str,
    ) -> BreachNotification:
        notification = await self._get_notification_or_raise(breach_id)
        notification.status = "closed"
        notification.closed_at = datetime.now(timezone.utc)
        notification.closed_by = closed_by
        await self._redis.set(
            f"{BREACH_KEY_PREFIX}:{breach_id}",
            notification.model_dump_json(),
        )
        return notification

    async def notify_affected_tenants(
        self,
        breach_id: str,
        affected_tenants: list[str],
    ) -> BreachNotification:
        notification = await self._get_notification_or_raise(breach_id)
        notification.affected_tenants = affected_tenants
        await self._redis.set(
            f"{BREACH_KEY_PREFIX}:{breach_id}",
            notification.model_dump_json(),
        )
        return notification

    async def _get_notification_or_raise(self, breach_id: str) -> BreachNotification:
        notification = await self.get_notification(breach_id)
        if notification is None:
            raise ValueError(f"Notification not found: {breach_id}")
        return notification
