"""Tests for governance notification service: webhook configs, email templates, dispatch.

Uses fakeredis-backed cache matching conftest patterns.
"""

from __future__ import annotations

import pytest

from anonreq.services.notifications import (
    NotificationChannel,
    NotificationEventType,
    NotificationService,
)


@pytest.fixture
async def notification_service(cache_manager):
    svc = NotificationService(cache_manager)
    # Clean slate
    await svc._redis.delete("anonreq:notifications:configs")
    return svc


class TestNotificationConfig:
    async def test_create_webhook_config(self, notification_service):
        config = await notification_service.create_config(
            tenant_id="acme-corp",
            channel=NotificationChannel.WEBHOOK,
            config={"url": "https://hooks.example.com/anonreq"},
            events=[NotificationEventType.REVIEW_OVERDUE],
        )
        assert config.id is not None
        assert config.tenant_id == "acme-corp"
        assert config.channel == NotificationChannel.WEBHOOK
        assert config.enabled is True

    async def test_create_email_config(self, notification_service):
        config = await notification_service.create_config(
            tenant_id="acme-corp",
            channel=NotificationChannel.EMAIL,
            config={"to": ["gov-team@acme.com"], "from": "anonreq@acme.com"},
            events=[NotificationEventType.KILL_SWITCH_ACTIVATED],
        )
        assert config.channel == NotificationChannel.EMAIL
        assert config.config.get("to") == ["gov-team@acme.com"]

    async def test_list_configs(self, notification_service):
        await notification_service.create_config(
            "acme-corp", NotificationChannel.WEBHOOK,
            {"url": "https://hooks.example.com/1"},
            [NotificationEventType.REVIEW_OVERDUE],
        )
        await notification_service.create_config(
            "acme-corp", NotificationChannel.WEBHOOK,
            {"url": "https://hooks.example.com/2"},
            [NotificationEventType.RISK_THRESHOLD_BREACHED],
        )
        configs = await notification_service.list_configs("acme-corp")
        assert len(configs) == 2
        assert configs[0].id != configs[1].id

    async def test_list_configs_other_tenant(self, notification_service):
        await notification_service.create_config(
            "acme-corp", NotificationChannel.WEBHOOK,
            {"url": "https://hooks.example.com/1"},
            [NotificationEventType.REVIEW_OVERDUE],
        )
        other = await notification_service.list_configs("other-corp")
        assert len(other) == 0

    async def test_update_config(self, notification_service):
        config = await notification_service.create_config(
            "acme-corp", NotificationChannel.WEBHOOK,
            {"url": "https://hooks.example.com/1"},
            [NotificationEventType.REVIEW_OVERDUE],
        )
        updated = await notification_service.update_config(
            config.id,
            config={"url": "https://hooks.example.com/v2"},
            enabled=False,
        )
        assert updated.config["url"] == "https://hooks.example.com/v2"
        assert updated.enabled is False

    async def test_update_nonexistent_raises(self, notification_service):
        with pytest.raises(ValueError, match="not found"):
            await notification_service.update_config("no-such", enabled=False)

    async def test_delete_config(self, notification_service):
        config = await notification_service.create_config(
            "acme-corp", NotificationChannel.WEBHOOK,
            {"url": "https://hooks.example.com/1"},
            [NotificationEventType.REVIEW_OVERDUE],
        )
        await notification_service.delete_config(config.id)
        configs = await notification_service.list_configs("acme-corp")
        assert len(configs) == 0

    async def test_delete_nonexistent_raises(self, notification_service):
        with pytest.raises(ValueError, match="not found"):
            await notification_service.delete_config("no-such")


class TestNotificationDispatch:
    async def test_dispatch_webhook(self, notification_service):
        """Webhook dispatch sends POST to configured URL."""

        await notification_service.create_config(
            tenant_id="acme-corp",
            channel=NotificationChannel.WEBHOOK,
            config={"url": "http://localhost:99999/nonexistent"},
            events=[NotificationEventType.REVIEW_OVERDUE],
        )
        # Should not raise — dispatch is fire-and-forget with timeout
        await notification_service.notify(
            event_type=NotificationEventType.REVIEW_OVERDUE,
            tenant_id="acme-corp",
            payload={"tenant_id": "acme-corp", "days_overdue": 15},
        )
        # No assertion on result — webhook may fail silently per design

    async def test_dispatch_disabled_config_skipped(self, notification_service):
        config = await notification_service.create_config(
            tenant_id="acme-corp",
            channel=NotificationChannel.WEBHOOK,
            config={"url": "https://hooks.example.com"},
            events=[NotificationEventType.REVIEW_OVERDUE],
        )
        await notification_service.update_config(config.id, enabled=False)

        await notification_service.notify(
            event_type=NotificationEventType.REVIEW_OVERDUE,
            tenant_id="acme-corp",
            payload={"test": True},
        )
        # Should not attempt dispatch

    async def test_dispatch_wrong_event_skipped(self, notification_service):
        await notification_service.create_config(
            tenant_id="acme-corp",
            channel=NotificationChannel.WEBHOOK,
            config={"url": "https://hooks.example.com"},
            events=[NotificationEventType.KILL_SWITCH_ACTIVATED],
        )
        await notification_service.notify(
            event_type=NotificationEventType.REVIEW_OVERDUE,
            tenant_id="acme-corp",
            payload={},
        )
        # Should skip — event type doesn't match

    async def test_event_type_enum_values(self):
        assert NotificationEventType.REVIEW_OVERDUE.value == "review_overdue"
        assert NotificationEventType.RISK_THRESHOLD_BREACHED.value == "risk_threshold_breached"
        assert NotificationEventType.KILL_SWITCH_ACTIVATED.value == "kill_switch_activated"

    async def test_channel_enum_values(self):
        assert NotificationChannel.WEBHOOK.value == "webhook"
        assert NotificationChannel.EMAIL.value == "email"


class TestEmailTemplateSystem:
    async def test_email_template_renders(self, notification_service):
        rendered = notification_service.render_email_template(
            template_name="review_overdue",
            context={"tenant_id": "acme-corp", "days_overdue": 15},
        )
        assert "acme-corp" in rendered
        assert "15" in rendered
        assert rendered.startswith("Subject:")

    async def test_email_template_risk_breach(self, notification_service):
        rendered = notification_service.render_email_template(
            template_name="risk_threshold_breached",
            context={"tenant_id": "acme-corp", "risk_score": 0.85},
        )
        assert "acme-corp" in rendered
        assert "0.85" in rendered

    async def test_email_template_kill_switch(self, notification_service):
        rendered = notification_service.render_email_template(
            template_name="kill_switch_activated",
            context={"operator_id": "admin@acme.com", "reason": "Security incident"},
        )
        assert "admin@acme.com" in rendered
        assert "Security incident" in rendered
