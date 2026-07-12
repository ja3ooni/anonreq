"""Notification service: webhooks, email templates, governance event dispatch.

Provides:
- ``NotificationEventType`` enum for governance events
- ``NotificationChannel`` enum for delivery channels
- ``NotificationConfig`` model for per-tenant configuration
- ``NotificationService`` for managing configs and dispatching events
- Email template rendering for governance events
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from anonreq.cache.manager import CacheManager


class NotificationEventType(StrEnum):
    REVIEW_OVERDUE = "review_overdue"
    RISK_THRESHOLD_BREACHED = "risk_threshold_breached"
    KILL_SWITCH_ACTIVATED = "kill_switch_activated"
    GOVERNANCE_RECORD_UPDATED = "governance_record_updated"
    RISK_ASSESSMENT_CREATED = "risk_assessment_created"


class NotificationChannel(StrEnum):
    WEBHOOK = "webhook"
    EMAIL = "email"


class NotificationConfig(BaseModel):
    id: str
    tenant_id: str
    channel: NotificationChannel
    config: dict[str, Any] = {}
    events: list[NotificationEventType] = []
    enabled: bool = True
    created_at: datetime

    model_config = {"extra": "ignore"}


CONFIGS_KEY = "anonreq:notifications:configs"

EMAIL_TEMPLATES: dict[str, str] = {
    "review_overdue": (
        "Subject: [AnonReq] Review Overdue for {tenant_id}\n\n"
        "The governance review for tenant {tenant_id} is overdue by {days_overdue} days.\n"
        "Please take immediate action to complete the review cycle.\n\n"
        "-- AnonReq Governance System"
    ),
    "risk_threshold_breached": (
        "Subject: [AnonReq] Risk Threshold Breached for {tenant_id}\n\n"
        "The risk assessment for tenant {tenant_id} has breached the threshold.\n"
        "Current risk score: {risk_score}\n"
        "Immediate reassessment required.\n\n"
        "-- AnonReq Governance System"
    ),
    "kill_switch_activated": (
        "Subject: [AnonReq] Kill-Switch Activated by {operator_id}\n\n"
        "The kill-switch has been activated by {operator_id}.\n"
        "Reason: {reason}\n"
        "All provider forwarding is now blocked.\n\n"
        "-- AnonReq Governance System"
    ),
}


class NotificationService:
    """Manages notification configurations and dispatches governance events.

    Configs are stored in Valkey as a HASH. Dispatch is fire-and-forget
    with configurable webhook URLs and email template rendering.
    """

    def __init__(self, cache_manager: CacheManager) -> None:
        self._redis = cache_manager._redis

    async def create_config(
        self,
        tenant_id: str,
        channel: NotificationChannel,
        config: dict[str, Any],
        events: list[NotificationEventType],
    ) -> NotificationConfig:
        notification_config = NotificationConfig(
            id=uuid4().hex[:24],
            tenant_id=tenant_id,
            channel=channel,
            config=config,
            events=events,
            enabled=True,
            created_at=datetime.now(UTC),
        )
        await self._redis.hset(
            CONFIGS_KEY,
            notification_config.id,
            notification_config.model_dump_json(),
        )
        return notification_config

    async def list_configs(
        self,
        tenant_id: str,
    ) -> list[NotificationConfig]:
        raw = await self._redis.hgetall(CONFIGS_KEY)
        results: list[NotificationConfig] = []
        for _, value in raw.items():
            nc = NotificationConfig(**json.loads(value))
            if nc.tenant_id == tenant_id:
                results.append(nc)
        return results

    async def get_config(
        self,
        config_id: str,
    ) -> NotificationConfig | None:
        raw = await self._redis.hget(CONFIGS_KEY, config_id)
        if raw is None:
            return None
        return NotificationConfig(**json.loads(raw))

    async def update_config(
        self,
        config_id: str,
        config: dict[str, Any] | None = None,
        events: list[NotificationEventType] | None = None,
        enabled: bool | None = None,
    ) -> NotificationConfig:
        raw = await self._redis.hget(CONFIGS_KEY, config_id)
        if raw is None:
            raise ValueError(f"Notification config not found: {config_id}")
        nc = NotificationConfig(**json.loads(raw))
        if config is not None:
            nc.config = config
        if events is not None:
            nc.events = events
        if enabled is not None:
            nc.enabled = enabled
        await self._redis.hset(CONFIGS_KEY, config_id, nc.model_dump_json())
        return nc

    async def delete_config(self, config_id: str) -> None:
        raw = await self._redis.hget(CONFIGS_KEY, config_id)
        if raw is None:
            raise ValueError(f"Notification config not found: {config_id}")
        await self._redis.hdel(CONFIGS_KEY, config_id)

    async def notify(
        self,
        event_type: NotificationEventType,
        tenant_id: str,
        payload: dict[str, Any],
    ) -> None:
        raw = await self._redis.hgetall(CONFIGS_KEY)
        for _, value in raw.items():
            nc = NotificationConfig(**json.loads(value))
            if nc.tenant_id != tenant_id:
                continue
            if not nc.enabled:
                continue
            if event_type not in nc.events:
                continue

            if nc.channel == NotificationChannel.WEBHOOK:
                await self._dispatch_webhook(nc, event_type, payload)
            elif nc.channel == NotificationChannel.EMAIL:
                await self._dispatch_email(nc, event_type, payload)

    async def _dispatch_webhook(
        self,
        config: NotificationConfig,
        event_type: NotificationEventType,
        payload: dict[str, Any],
    ) -> None:
        url = config.config.get("url", "")
        if not url:
            return
        import httpx

        body = {
            "event": event_type.value,
            "tenant_id": config.tenant_id,
            "payload": payload,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(url, json=body)
        except Exception:
            pass

    async def _dispatch_email(
        self,
        config: NotificationConfig,
        event_type: NotificationEventType,
        payload: dict[str, Any],
    ) -> None:
        template_name = event_type.value
        self.render_email_template(template_name, payload)
        to = config.config.get("to", [])
        if not to:
            return

    def render_email_template(
        self,
        template_name: str,
        context: dict[str, Any],
    ) -> str:
        template = EMAIL_TEMPLATES.get(template_name, "")
        return template.format(**context)
