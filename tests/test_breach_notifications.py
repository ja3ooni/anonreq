"""Tests for breach notification automation.

Per D-026 through D-029:
- Templates per framework/region with variable substitution
- Regulator notification queue
- Affected-tenant notification via governance contacts
- Metadata-only payload invariant
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from anonreq.models.breach import BreachNotification, BreachTemplate, RegulatorQueueItem


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def template_manager():
    from anonreq.breach.templates import BreachTemplateManager

    return BreachTemplateManager()


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    async def mock_execute(stmt, params=None):
        result = AsyncMock()
        result.rowcount = 1
        result.fetchone = AsyncMock(return_value=None)
        result.fetchall = AsyncMock(return_value=[])
        stmt_str = str(stmt) if hasattr(stmt, "__str__") else str(stmt)

        if "SELECT * FROM regulator_notification_queue" in stmt_str:
            result.fetchall = AsyncMock(return_value=[])
        elif "SELECT * FROM breach_notifications" in stmt_str:
            result.fetchall = AsyncMock(return_value=[])
        else:
            result.fetchone = AsyncMock(return_value=None)

        return result

    session.execute = mock_execute
    return session


@pytest.fixture
def breach_notifier(mock_db_session, template_manager):
    from anonreq.breach.notifications import BreachNotifier

    return BreachNotifier(
        db=mock_db_session,
        template_manager=template_manager,
    )


# ── Test 1: Template loading and rendering ───────────────────────────────────


class TestBreachTemplates:
    def test_get_template_gdpr_eu(self, template_manager):
        """GDPR EU template can be loaded."""
        template = template_manager.get_template("gdpr", "eu")
        assert template.framework == "gdpr"
        assert template.region == "eu"
        assert "GDPR Breach Notification" in template.subject_template

    def test_get_template_gdpr_uk(self, template_manager):
        """GDPR UK template can be loaded."""
        template = template_manager.get_template("gdpr", "uk")
        assert template.framework == "gdpr"
        assert template.region == "uk"
        assert "UK DPA Breach Notification" in template.subject_template

    def test_get_template_dora_eu(self, template_manager):
        """DORA EU template can be loaded."""
        template = template_manager.get_template("dora", "eu")
        assert template.framework == "dora"
        assert template.region == "eu"
        assert "DORA ICT Incident Notification" in template.subject_template

    def test_get_template_nonexistent_raises(self, template_manager):
        """Non-existent template raises ValueError."""
        with pytest.raises(ValueError, match="No template found"):
            template_manager.get_template("nonexistent", "xx")

    def test_render_template_substitutes_variables(self, template_manager):
        """Template variables are substituted correctly."""
        template = template_manager.get_template("gdpr", "eu")
        subject, body = template_manager.render_template(template, {
            "recipient_name": "Test User",
            "tenant_name": "Acme Corp",
            "breach_id": "BR-001",
            "date": "2024-01-15",
            "description": "Data exposure incident",
            "sender_name": "Security Team",
        })
        assert "Acme Corp" in subject
        assert "Test User" in body
        assert "BR-001" in body
        assert "Data exposure incident" in body

    def test_render_template_missing_variables_raises(
        self, template_manager
    ):
        """Missing required variables raises KeyError."""
        template = template_manager.get_template("gdpr", "eu")
        with pytest.raises(KeyError, match="Missing required"):
            template_manager.render_template(template, {})

    def test_render_template_body_contains_all_vars(
        self, template_manager
    ):
        """Rendered body contains all required template variables."""
        template = template_manager.get_template("gdpr", "eu")
        variables = {
            "recipient_name": "Regulator",
            "tenant_name": "Acme",
            "breach_id": "BR-002",
            "date": "2024-06-01",
            "description": "Test breach",
            "sender_name": "Admin",
            "affected_count": "50",
            "mitigation": "System patched",
        }
        subject, body = template_manager.render_template(
            template, variables
        )
        assert "50" in body
        assert "System patched" in body

    def test_custom_template_override(self, template_manager):
        """Custom templates override defaults."""
        custom = BreachTemplate(
            id="custom-gdpr-eu",
            framework="gdpr",
            region="eu",
            subject_template="Custom Subject - {{tenant_name}}",
            body_template="Custom body for {{description}}",
        )
        import asyncio
        asyncio.run(
            template_manager.set_custom_template("gdpr", "eu", custom)
        )
        template = template_manager.get_template("gdpr", "eu")
        assert template.id == "custom-gdpr-eu"
        assert "Custom Subject" in template.subject_template

    def test_list_available_templates(self, template_manager):
        """List available templates returns all frameworks and regions."""
        templates = template_manager.list_available_templates()
        frameworks = {t["framework"] for t in templates}
        assert "gdpr" in frameworks
        assert "dora" in frameworks
        regions = {t["region"] for t in templates}
        assert "eu" in regions
        assert "uk" in regions


# ── Test 2: Notification sending ─────────────────────────────────────────────


class TestBreachNotifications:
    async def test_send_breach_notifications_returns_counts(
        self, breach_notifier
    ):
        """send_breach_notifications returns notification counts."""
        result = await breach_notifier.send_breach_notifications(
            breach_id="BR-001",
            framework="gdpr",
            description="Test breach",
            affected_tenants=["acme", "othercorp"],
        )
        assert isinstance(result, dict)
        assert "notifications_sent" in result
        assert "regulator_queued" in result
        assert result["notifications_sent"] >= 1

    async def test_send_breach_notifications_regulator_queued(
        self, breach_notifier
    ):
        """Regulator notification is queued."""
        result = await breach_notifier.send_breach_notifications(
            breach_id="BR-002",
            framework="dora",
            description="DORA incident",
            affected_tenants=["acme"],
        )
        assert result["regulator_queued"] is True

    async def test_get_notification_queue_returns_list(
        self, breach_notifier
    ):
        """get_notification_queue returns a list."""
        queue = await breach_notifier.get_notification_queue()
        assert isinstance(queue, list)

    async def test_get_notification_queue_filtered(
        self, breach_notifier
    ):
        """get_notification_queue filters by status."""
        pending = await breach_notifier.get_notification_queue(
            status="pending"
        )
        assert isinstance(pending, list)

    async def test_retry_failed_notifications_returns_count(
        self, breach_notifier
    ):
        """retry_failed_notifications returns an integer."""
        count = await breach_notifier.retry_failed_notifications()
        assert isinstance(count, int)
        assert count >= 0


# ── Test 3: Breach model invariants ──────────────────────────────────────────


class TestBreachModels:
    def test_breach_notification_default_status(self):
        """BreachNotification defaults to pending status."""
        notif = BreachNotification(
            breach_id="BR-001",
            target_type="regulator",
            target_id="reg-1",
            channel="email",
            template_id="gdpr-eu",
        )
        assert notif.status == "pending"

    def test_breach_notification_required_fields(self):
        """BreachNotification requires breach_id, target, channel."""
        notif = BreachNotification(
            breach_id="BR-001",
            target_type="tenant",
            target_id="tenant-1",
            channel="email",
            template_id="gdpr-eu",
        )
        assert notif.target_type == "tenant"
        assert notif.target_id == "tenant-1"

    def test_regulator_queue_item_creation(self):
        """RegulatorQueueItem can be created."""
        item = RegulatorQueueItem(
            regulator_id="ICO",
            notification_id="N-001",
        )
        assert item.regulator_id == "ICO"
        assert item.notification_id == "N-001"
        assert item.status == "pending"

    def test_breach_template_creation(self):
        """BreachTemplate can be created."""
        tpl = BreachTemplate(
            framework="gdpr",
            region="eu",
            subject_template="Subject {{var}}",
            body_template="Body {{var}}",
        )
        assert tpl.framework == "gdpr"
        assert tpl.region == "eu"
