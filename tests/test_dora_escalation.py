"""Tests for DORA incident auto-escalation per criticality tier (D-016, D-017, D-018).

Covers:
- Critical service SLO breach → auto-create incident + notify
- Important service SLO breach → log incident only (no notify)
- Standard service → no escalation
- Incident record has all required fields
- dora_incident_created audit event emitted for auto-created incidents
- Manual incident creation also supported
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from anonreq.models.governance import IncidentRecord, ServiceCriticality

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_notification_service() -> MagicMock:
    """Mock notification service."""
    svc = MagicMock()
    svc.notify = AsyncMock()
    return svc


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Mock async DB session."""
    return AsyncMock()


@pytest.fixture
def mock_audit_emitter() -> MagicMock:
    """Mock audit event emitter."""
    return MagicMock()


# ── ServiceCriticality enum ─────────────────────────────────────────────────


class TestServiceCriticality:
    """ServiceCriticality enum values."""

    def test_enum_values(self):
        """All expected values exist."""
        assert ServiceCriticality.CRITICAL.value == "CRITICAL"
        assert ServiceCriticality.IMPORTANT.value == "IMPORTANT"
        assert ServiceCriticality.STANDARD.value == "STANDARD"

    def test_from_string(self):
        """Can be constructed from string."""
        assert ServiceCriticality("CRITICAL") == ServiceCriticality.CRITICAL
        assert ServiceCriticality("IMPORTANT") == ServiceCriticality.IMPORTANT
        assert ServiceCriticality("STANDARD") == ServiceCriticality.STANDARD


# ── IncidentRecord model ────────────────────────────────────────────────────


class TestIncidentRecord:
    """IncidentRecord model validation."""

    def test_minimal_incident(self):
        """Create an incident with required fields only."""
        datetime.now(UTC)
        incident = IncidentRecord(
            tenant_id="acme-corp",
            service_id="svc-gateway",
            service_name="AnonReq Gateway",
            criticality=ServiceCriticality.CRITICAL,
            severity="S1",
            title="P95 latency exceeded 200ms",
            description="Gateway P95 latency at 312ms for 5+ minutes",
        )
        assert incident.tenant_id == "acme-corp"
        assert incident.criticality == ServiceCriticality.CRITICAL
        assert incident.status == "open"
        assert incident.escalated is False
        assert incident.notified is False

    def test_full_incident(self):
        """Create an incident with all fields."""
        now = datetime.now(UTC)
        incident = IncidentRecord(
            id="inc_001",
            tenant_id="acme-corp",
            service_id="svc-gateway",
            service_name="AnonReq Gateway",
            criticality=ServiceCriticality.IMPORTANT,
            severity="S2",
            title="Cache hit rate dropped",
            description="Hit rate at 72%",
            status="open",
            created_at=now,
            escalated=False,
            notified=False,
        )
        assert incident.id is not None
        assert incident.criticality == ServiceCriticality.IMPORTANT

    def test_incident_default_id(self):
        """Incident auto-generates id if not provided."""
        incident = IncidentRecord(
            tenant_id="acme-corp",
            service_id="svc-gateway",
            service_name="AnonReq Gateway",
            criticality=ServiceCriticality.STANDARD,
            severity="S3",
            title="Minor issue",
            description="Something happened",
        )
        assert len(incident.id) > 0

    def test_incident_serialization(self):
        """Incident serializes to dict correctly."""
        incident = IncidentRecord(
            tenant_id="acme-corp",
            service_id="svc-llm",
            service_name="LLM Provider",
            criticality=ServiceCriticality.CRITICAL,
            severity="S1",
            title="LLM timeout spike",
            description="Timeouts at 15%",
        )
        data = incident.model_dump()
        assert data["tenant_id"] == "acme-corp"
        assert data["criticality"] == "CRITICAL"
        assert data["status"] == "open"


# ── IncidentManager tests ──────────────────────────────────────────────────


class TestIncidentCreation:
    """Manual and automatic incident creation."""

    @pytest.mark.asyncio
    async def test_create_incident_manual(
        self, mock_db_session: AsyncMock, mock_notification_service: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """Manual incident creation returns a valid record."""
        from anonreq.governance.incidents import IncidentManager

        manager = IncidentManager(
            db=mock_db_session,
            notification_service=mock_notification_service,
            emit_audit=mock_audit_emitter,
        )

        incident = await manager.create_incident(
            tenant_id="acme-corp",
            service_id="svc-gateway",
            service_name="AnonReq Gateway",
            criticality=ServiceCriticality.CRITICAL,
            severity="S1",
            title="Manual test incident",
            description="Created for testing",
        )
        assert incident.tenant_id == "acme-corp"
        assert incident.title == "Manual test incident"
        assert incident.status == "open"

    @pytest.mark.asyncio
    async def test_list_incidents(
        self, mock_db_session: AsyncMock, mock_notification_service: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """List incidents returns all created incidents."""
        from anonreq.governance.incidents import IncidentManager

        manager = IncidentManager(
            db=mock_db_session,
            notification_service=mock_notification_service,
            emit_audit=mock_audit_emitter,
        )

        inc1 = await manager.create_incident(
            tenant_id="acme-corp", service_id="s1", service_name="Gateway",
            criticality=ServiceCriticality.CRITICAL, severity="S1",
            title="Incident 1", description="First",
        )
        inc2 = await manager.create_incident(
            tenant_id="acme-corp", service_id="s2", service_name="Cache",
            criticality=ServiceCriticality.IMPORTANT, severity="S2",
            title="Incident 2", description="Second",
        )

        all_incidents = await manager.list_incidents()
        assert len(all_incidents) >= 2
        assert any(i.id == inc1.id for i in all_incidents)
        assert any(i.id == inc2.id for i in all_incidents)

    @pytest.mark.asyncio
    async def test_list_incidents_filter_by_tenant(
        self, mock_db_session: AsyncMock, mock_notification_service: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """List incidents can be filtered by tenant."""
        from anonreq.governance.incidents import IncidentManager

        manager = IncidentManager(
            db=mock_db_session,
            notification_service=mock_notification_service,
            emit_audit=mock_audit_emitter,
        )

        await manager.create_incident(
            tenant_id="tenant-a", service_id="s1", service_name="A",
            criticality=ServiceCriticality.STANDARD, severity="S3",
            title="Tenant A incident", description="For tenant A",
        )
        await manager.create_incident(
            tenant_id="tenant-b", service_id="s1", service_name="B",
            criticality=ServiceCriticality.STANDARD, severity="S3",
            title="Tenant B incident", description="For tenant B",
        )

        tenant_a_incidents = await manager.list_incidents(tenant_id="tenant-a")
        assert all(i.tenant_id == "tenant-a" for i in tenant_a_incidents)

    @pytest.mark.asyncio
    async def test_resolve_incident(
        self, mock_db_session: AsyncMock, mock_notification_service: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """Resolve an incident sets status to resolved."""
        from anonreq.governance.incidents import IncidentManager

        manager = IncidentManager(
            db=mock_db_session,
            notification_service=mock_notification_service,
            emit_audit=mock_audit_emitter,
        )

        incident = await manager.create_incident(
            tenant_id="acme-corp", service_id="s1", service_name="Gateway",
            criticality=ServiceCriticality.CRITICAL, severity="S1",
            title="To resolve", description="Will be resolved",
        )

        resolved = await manager.resolve_incident(incident.id, "Fixed by scaling up")
        assert resolved.status == "resolved"
        assert resolved.resolved_at is not None


class TestCriticalityEscalation:
    """Escalation behavior per criticality tier."""

    @pytest.mark.asyncio
    async def test_critical_escalates_and_notifies(
        self, mock_db_session: AsyncMock, mock_notification_service: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """CRITICAL service SLO breach → escalate + notify."""
        from anonreq.governance.incidents import IncidentManager

        manager = IncidentManager(
            db=mock_db_session,
            notification_service=mock_notification_service,
            emit_audit=mock_audit_emitter,
        )

        incident = await manager.create_incident(
            tenant_id="acme-corp",
            service_id="svc-gateway",
            service_name="AnonReq Gateway",
            criticality=ServiceCriticality.CRITICAL,
            severity="S1",
            title="SLO breach: P95 > 100ms",
            description="P95 at 312ms",
        )
        escalated = await manager.escalate_if_needed(incident)

        assert escalated.escalated is True
        assert escalated.escalated_at is not None
        assert escalated.notified is True
        assert escalated.notified_at is not None
        mock_notification_service.notify.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_important_logs_only(
        self, mock_db_session: AsyncMock, mock_notification_service: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """IMPORTANT service SLO breach → log only, no notify."""
        from anonreq.governance.incidents import IncidentManager

        manager = IncidentManager(
            db=mock_db_session,
            notification_service=mock_notification_service,
            emit_audit=mock_audit_emitter,
        )

        incident = await manager.create_incident(
            tenant_id="acme-corp",
            service_id="svc-cache",
            service_name="Cache Layer",
            criticality=ServiceCriticality.IMPORTANT,
            severity="S2",
            title="Cache hit rate below 80%",
            description="Hit rate at 72%",
        )
        escalated = await manager.escalate_if_needed(incident)

        assert escalated.escalated is False
        assert escalated.notified is False
        mock_notification_service.notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_standard_no_escalation(
        self, mock_db_session: AsyncMock, mock_notification_service: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """STANDARD service SLO breach → no escalation."""
        from anonreq.governance.incidents import IncidentManager

        manager = IncidentManager(
            db=mock_db_session,
            notification_service=mock_notification_service,
            emit_audit=mock_audit_emitter,
        )

        incident = await manager.create_incident(
            tenant_id="acme-corp",
            service_id="svc-logging",
            service_name="Log Aggregator",
            criticality=ServiceCriticality.STANDARD,
            severity="S3",
            title="Log shipping delay",
            description=" Batched logs delayed by 30s",
        )
        escalated = await manager.escalate_if_needed(incident)

        assert escalated.escalated is False
        assert escalated.notified is False
        mock_notification_service.notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_escalate_on_slo_breach(
        self, mock_db_session: AsyncMock, mock_notification_service: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """auto_escalate_on_slo_breach creates incident and escalates."""
        from anonreq.governance.incidents import IncidentManager

        manager = IncidentManager(
            db=mock_db_session,
            notification_service=mock_notification_service,
            emit_audit=mock_audit_emitter,
        )

        incident = await manager.auto_escalate_on_slo_breach(
            tenant_id="acme-corp",
            service_id="svc-gateway",
            slo_metric="P95 latency",
            slo_value=312.0,
            threshold=100.0,
        )

        assert incident is not None
        assert incident.criticality == ServiceCriticality.CRITICAL
        assert incident.escalated is True
        assert incident.notified is True
        mock_notification_service.notify.assert_awaited_once()


class TestDORAAuditEvent:
    """Audit event emission for DORA incidents."""

    @pytest.mark.asyncio
    async def test_audit_emitted_for_critical(
        self, mock_db_session: AsyncMock, mock_notification_service: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """dora_incident_created audit event emitted for critical incident."""
        from anonreq.governance.incidents import IncidentManager

        manager = IncidentManager(
            db=mock_db_session,
            notification_service=mock_notification_service,
            emit_audit=mock_audit_emitter,
        )

        incident = await manager.create_incident(
            tenant_id="acme-corp",
            service_id="svc-gateway",
            service_name="Gateway",
            criticality=ServiceCriticality.CRITICAL,
            severity="S1",
            title="CRITICAL incident",
            description="Something critical",
        )
        await manager.escalate_if_needed(incident)

        # Audit event should be emitted
        mock_audit_emitter.assert_called()
        call_arg = mock_audit_emitter.call_args[1]
        assert call_arg.get("event_type") == "dora_incident_created"

    @pytest.mark.asyncio
    async def test_audit_emitted_for_important(
        self, mock_db_session: AsyncMock, mock_notification_service: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """dora_incident_created audit event emitted for important incident."""
        from anonreq.governance.incidents import IncidentManager

        manager = IncidentManager(
            db=mock_db_session,
            notification_service=mock_notification_service,
            emit_audit=mock_audit_emitter,
        )

        incident = await manager.create_incident(
            tenant_id="acme-corp",
            service_id="svc-cache",
            service_name="Cache",
            criticality=ServiceCriticality.IMPORTANT,
            severity="S2",
            title="IMPORTANT incident",
            description="Something important",
        )
        await manager.escalate_if_needed(incident)

        mock_audit_emitter.assert_called()
        call_arg = mock_audit_emitter.call_args[1]
        assert call_arg.get("event_type") == "dora_incident_created"

    @pytest.mark.asyncio
    async def test_no_audit_for_standard(
        self, mock_db_session: AsyncMock, mock_notification_service: MagicMock,
        mock_audit_emitter: MagicMock,
    ):
        """No audit event for standard (no escalation needed)."""
        from anonreq.governance.incidents import IncidentManager

        manager = IncidentManager(
            db=mock_db_session,
            notification_service=mock_notification_service,
            emit_audit=mock_audit_emitter,
        )

        incident = await manager.create_incident(
            tenant_id="acme-corp",
            service_id="svc-logging",
            service_name="Logging",
            criticality=ServiceCriticality.STANDARD,
            severity="S3",
            title="STANDARD incident",
            description="Something minor",
        )
        await manager.escalate_if_needed(incident)

        mock_audit_emitter.assert_not_called()
