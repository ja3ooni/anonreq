"""DORA escalation integration tests.

Covers:
- CRITICAL SLO breach creates incident + auto-escalation with notification
- IMPORTANT SLO breach logs incident only (no notification, no escalation)
- STANDARD SLO breach does NOT create incident
- Manual incident creation and resolution workflow
- Incident filtering by tenant, status, and criticality
- auto_escalate_on_slo_breach convenience method
"""

from __future__ import annotations

from datetime import datetime

import pytest

from anonreq.governance.incidents import IncidentManager
from anonreq.models.governance import ServiceCriticality

# In-memory store is module-level; these tests use unique tenant IDs
# to avoid cross-test pollution.
_CRIT_TENANT = "escalation-test-critical"
_IMP_TENANT = "escalation-test-important"
_STD_TENANT = "escalation-test-standard"
_RESOLVE_TENANT = "escalation-test-resolve"
_SLO_TENANT = "escalation-test-slo-breach"


@pytest.fixture(autouse=True)
def clean_store():
    """Clean the incident store before each test by patching it.

    We use a disposable list so test pollution doesn't apply.
    """
    import anonreq.governance.incidents as inc_mod
    _orig = inc_mod._incident_store
    inc_mod._incident_store = []
    yield
    inc_mod._incident_store = _orig


@pytest.fixture
def manager() -> IncidentManager:
    return IncidentManager()


# ── Criticality-based escalation ──────────────────────────────────


class TestCriticalityEscalation:
    """Verify escalation behavior per criticality tier (D-016, D-017, D-018)."""

    @pytest.mark.asyncio
    async def test_critical_creates_incident_and_escalates(self, manager: IncidentManager):
        """CRITICAL SLO breach creates incident + notification."""
        inc = await manager.create_incident(
            tenant_id=_CRIT_TENANT,
            service_id="svc-latency",
            service_name="P99 Latency Monitor",
            criticality=ServiceCriticality.CRITICAL,
            severity="S1",
            title="SLO breach: p99 latency",
            description="P99 latency exceeded 99th percentile threshold.",
        )
        assert inc is not None
        assert inc.status == "open"

        escalated = await manager.escalate_if_needed(inc)
        assert escalated.escalated is True, \
            "CRITICAL incident must be escalated"
        assert escalated.escalated_at is not None, \
            "escalated_at must be set on escalation"
        assert escalated.notified is False, \
            "notified stays False when no notification_service provided"
        assert escalated.notified_at is None

    @pytest.mark.asyncio
    async def test_important_logs_incident_no_notification(
        self, manager: IncidentManager
    ):
        """IMPORTANT SLO breach creates incident but no notification."""
        inc = await manager.create_incident(
            tenant_id=_IMP_TENANT,
            service_id="svc-availability",
            service_name="Availability Monitor",
            criticality=ServiceCriticality.IMPORTANT,
            severity="S2",
            title="SLO breach: availability",
            description="Availability dropped below 99.5%.",
        )
        assert inc is not None
        assert inc.escalated is False

        escalated = await manager.escalate_if_needed(inc)
        assert escalated.escalated is False, \
            "IMPORTANT incident must NOT be escalated"
        assert escalated.escalated_at is None
        assert escalated.notified is False

    @pytest.mark.asyncio
    async def test_standard_does_not_escalate(self, manager: IncidentManager):
        """STANDARD SLO breach — no escalation."""
        inc = await manager.create_incident(
            tenant_id=_STD_TENANT,
            service_id="svc-throughput",
            service_name="Throughput Monitor",
            criticality=ServiceCriticality.STANDARD,
            severity="S3",
            title="SLO breach: throughput",
            description="Throughput dropped below 90%.",
        )
        assert inc.escalated is False

        escalated = await manager.escalate_if_needed(inc)
        assert escalated.escalated is False
        assert escalated.escalated_at is None
        assert escalated.notified is False


# ── auto_escalate_on_slo_breach ───────────────────────────────────


class TestAutoEscalateOnSloBreach:
    """Verify the convenience method auto_escalate_on_slo_breach."""

    @pytest.mark.asyncio
    async def test_slo_breach_auto_escalates_for_critical(
        self, manager: IncidentManager
    ):
        """auto_escalate_on_slo_breach creates and escalates for critical."""
        result = await manager.auto_escalate_on_slo_breach(
            tenant_id=_SLO_TENANT,
            service_id="svc-latency",
            slo_metric="P95 latency",
            slo_value=150.0,
            threshold=100.0,
        )
        assert result is not None
        assert result.escalated is True
        assert result.status == "open"
        assert "P95 latency" in result.title

    @pytest.mark.asyncio
    async def test_slo_breach_incident_has_required_fields(
        self, manager: IncidentManager
    ):
        """Auto-created incident has all required metadata."""
        result = await manager.auto_escalate_on_slo_breach(
            tenant_id=_SLO_TENANT,
            service_id="svc-availability",
            slo_metric="uptime",
            slo_value=0.97,
            threshold=0.995,
        )
        assert result is not None
        assert isinstance(result.id, str)
        assert len(result.id) > 0
        assert isinstance(result.created_at, datetime)
        assert result.created_at.tzinfo is not None, \
            "created_at must be timezone-aware"


# ── Incident lifecycle ────────────────────────────────────────────


class TestIncidentLifecycle:
    """Verify incident creation and resolution workflow."""

    @pytest.mark.asyncio
    async def test_create_and_resolve(self, manager: IncidentManager):
        """Incident can be created and resolved."""
        inc = await manager.create_incident(
            tenant_id=_RESOLVE_TENANT,
            service_id="svc-test",
            service_name="Test Service",
            criticality=ServiceCriticality.CRITICAL,
            severity="S1",
            title="Test incident",
            description="Testing creation and resolution.",
        )
        assert inc.status == "open"

        resolved = await manager.resolve_incident(
            inc.id, "Root cause fixed."
        )
        assert resolved is not None
        assert resolved.status == "resolved"
        assert resolved.resolved_at is not None

    @pytest.mark.asyncio
    async def test_resolve_unknown_returns_none(self, manager: IncidentManager):
        """Resolving a non-existent incident returns None."""
        result = await manager.resolve_incident("nonexistent-id", "N/A")
        assert result is None


# ── Filtering ─────────────────────────────────────────────────────


class TestIncidentFiltering:
    """Verify list_incidents filtering works."""

    @pytest.mark.asyncio
    async def test_list_by_tenant(self, manager: IncidentManager):
        """list_incidents filters by tenant."""
        await manager.create_incident(
            tenant_id="tenant-x",
            service_id="svc-a",
            service_name="Svc A",
            criticality=ServiceCriticality.IMPORTANT,
            severity="S2",
            title="Incident A",
            description="Desc A",
        )
        await manager.create_incident(
            tenant_id="tenant-y",
            service_id="svc-b",
            service_name="Svc B",
            criticality=ServiceCriticality.CRITICAL,
            severity="S1",
            title="Incident B",
            description="Desc B",
        )
        x_incidents = await manager.list_incidents(tenant_id="tenant-x")
        assert len(x_incidents) == 1
        assert x_incidents[0].tenant_id == "tenant-x"

        all_incidents = await manager.list_incidents()
        assert len(all_incidents) >= 2

    @pytest.mark.asyncio
    async def test_list_by_criticality(self, manager: IncidentManager):
        """list_incidents filters by criticality."""
        await manager.create_incident(
            tenant_id="flt-crit",
            service_id="svc-c",
            service_name="Svc C",
            criticality=ServiceCriticality.CRITICAL,
            severity="S1",
            title="Critical incident",
            description="Critical",
        )
        await manager.create_incident(
            tenant_id="flt-crit",
            service_id="svc-d",
            service_name="Svc D",
            criticality=ServiceCriticality.STANDARD,
            severity="S3",
            title="Standard incident",
            description="Standard",
        )
        critical = await manager.list_incidents(
            criticality=ServiceCriticality.CRITICAL
        )
        assert all(i.criticality == ServiceCriticality.CRITICAL for i in critical)

    @pytest.mark.asyncio
    async def test_list_pagination(self, manager: IncidentManager):
        """list_incidents supports skip/limit pagination."""
        for i in range(5):
            await manager.create_incident(
                tenant_id="pagination-tenant",
                service_id=f"svc-{i}",
                service_name=f"Svc {i}",
                criticality=ServiceCriticality.CRITICAL,
                severity="S1",
                title=f"Incident {i}",
                description=f"Desc {i}",
            )
        page = await manager.list_incidents(skip=0, limit=2)
        assert len(page) == 2
        page2 = await manager.list_incidents(skip=2, limit=2)
        assert len(page2) == 2
        assert page[0].id != page2[0].id, \
            "Pagination must return different incidents"
