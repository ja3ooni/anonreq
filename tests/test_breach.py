"""Tests for breach notification service.

Uses fakeredis-backed cache matching conftest patterns.
"""

from __future__ import annotations

import pytest

from anonreq.services.breach import BreachNotification, BreachService


@pytest.fixture
async def breach_service(cache_manager):
    svc = BreachService(cache_manager)
    keys = await svc._redis.keys("anonreq:breach:*")
    for k in keys:
        await svc._redis.delete(k)
    keys = await svc._redis.keys("anonreq:breach-template:*")
    for k in keys:
        await svc._redis.delete(k)
    yield svc


class TestBreachTemplate:
    async def test_set_template(self, breach_service):
        result = await breach_service.set_template(
            name="critical_breach",
            subject="Urgent: Data Breach Notification - {tenant_name}",
            body="A breach of severity {severity} was detected at {detected_at}. "
            "Affected records: {affected_records}. Please review immediately.",
            channels=["email", "webhook"],
        )
        assert result.name == "critical_breach"
        assert "{tenant_name}" in result.subject
        assert "{severity}" in result.body

    async def test_get_template(self, breach_service):
        await breach_service.set_template(
            "critical_breach", "Subject", "Body", ["email"]
        )
        template = await breach_service.get_template("critical_breach")
        assert template is not None
        assert template.name == "critical_breach"

    async def test_get_nonexistent_template(self, breach_service):
        template = await breach_service.get_template("no-such")
        assert template is None

    async def test_delete_template(self, breach_service):
        await breach_service.set_template("test", "S", "B", ["email"])
        await breach_service.delete_template("test")
        assert await breach_service.get_template("test") is None


class TestBreachCreate:
    async def test_create_notification(self, breach_service):
        await breach_service.set_template(
            "critical_breach", "Alert", "Body {severity}", ["email"]
        )
        notification = await breach_service.create_notification(
            severity="Critical",
            tenant_id="acme-corp",
            description="Possible data exposure detected",
            template_name="critical_breach",
            detected_by="monitor@anonreq",
        )
        assert notification.breach_id is not None
        assert notification.severity == "Critical"
        assert notification.tenant_id == "acme-corp"
        assert notification.status == "pending"

    async def test_create_nonexistent_template_fallback(self, breach_service):
        """Creating with no template should work with defaults."""
        notification = await breach_service.create_notification(
            severity="High",
            tenant_id="acme-corp",
            description="SLO breach",
            template_name="no-such-template",
            detected_by="system",
        )
        assert notification.status == "pending"
        assert notification.severity == "High"

    async def test_create_for_regulator_queue(self, breach_service):
        await breach_service.set_template("reg", "S", "B", ["email"])
        notification = await breach_service.create_notification(
            severity="Critical",
            tenant_id="acme-corp",
            description="Reg reportable incident",
            template_name="reg",
            detected_by="system",
            regulator_queue=True,
        )
        assert notification.regulator_queue is True


class TestBreachSend:
    async def test_send_notification(self, breach_service):
        await breach_service.set_template("t1", "Subj", "Body", ["email"])
        notif = await breach_service.create_notification(
            "Critical", "acme-corp", "desc", "t1", "system"
        )
        sent = await breach_service.send_notification(notif.breach_id)
        assert sent.status == "sent"
        assert sent.sent_at is not None

    async def test_send_nonexistent_raises(self, breach_service):
        with pytest.raises(ValueError, match="Notification not found"):
            await breach_service.send_notification("no-such")


class TestBreachList:
    async def test_list_notifications(self, breach_service):
        await breach_service.set_template("t1", "S", "B", ["email"])
        for i in range(3):
            await breach_service.create_notification(
                "High", "acme-corp", f"desc {i}", "t1", "system"
            )
        notifications = await breach_service.list_notifications("acme-corp")
        assert len(notifications) == 3

    async def test_list_empty(self, breach_service):
        notifications = await breach_service.list_notifications("no-such")
        assert notifications == []


class TestBreachRegulatorQueue:
    async def test_get_regulator_queue(self, breach_service):
        await breach_service.set_template("t1", "S", "B", ["email"])
        for sev in ["Critical", "High", "Low"]:
            await breach_service.create_notification(
                sev, "acme-corp", "desc", "t1", "system", regulator_queue=True
            )
        queue = await breach_service.get_regulator_queue()
        assert len(queue) == 3

    async def test_get_regulator_queue_empty(self, breach_service):
        queue = await breach_service.get_regulator_queue()
        assert queue == []


class TestBreachWorkflow:
    async def test_acknowledge_notification(self, breach_service):
        await breach_service.set_template("t1", "S", "B", ["email"])
        notif = await breach_service.create_notification(
            "Critical", "acme-corp", "desc", "t1", "system"
        )
        ack = await breach_service.acknowledge(notif.breach_id, "admin@acme.com")
        assert ack.status == "acknowledged"

    async def test_close_notification(self, breach_service):
        await breach_service.set_template("t1", "S", "B", ["email"])
        notif = await breach_service.create_notification(
            "Critical", "acme-corp", "desc", "t1", "system"
        )
        closed = await breach_service.close(
            notif.breach_id, closed_by="admin@acme.com"
        )
        assert closed.status == "closed"

    async def test_affected_tenant_notification(self, breach_service):
        await breach_service.set_template("t1", "S", "B", ["email"])
        notif = await breach_service.create_notification(
            "Critical", "acme-corp", "desc", "t1", "system"
        )
        affected = await breach_service.notify_affected_tenants(
            notif.breach_id,
            affected_tenants=["tenant-a", "tenant-b"],
        )
        assert affected.affected_tenants == ["tenant-a", "tenant-b"]
