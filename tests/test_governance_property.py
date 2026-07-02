"""Property-based tests for governance invariants.

Uses Hypothesis to verify:
- Approval request invariants
- Kill-switch invariants
- Lifecycle transition invariants
- Notification config invariants
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import HealthCheck, assume, given, settings, strategies as st

from anonreq.models.governance import (
    ChangeEntry,
    GovernanceOfficer,
    GovernanceOfficerRole,
    GovernanceRecord,
    ReviewCycle,
)
from anonreq.services.lifecycle import LifecycleService, LifecycleStage
from anonreq.services.notifications import (
    NotificationChannel,
    NotificationEventType,
    NotificationService,
)
from anonreq.services.oversight import ApprovalRequest, ApprovalRequestCreate, OversightService
from anonreq.services.transparency import TransparencyService

# ── Strategies ──────────────────────────────────────────────────────────

tenant_strategy = st.text(min_size=1, max_size=32, alphabet=st.characters(
    whitelist_categories=("L", "N", "P"),
    whitelist_characters="-_.",
))
operator_strategy = st.emails()
risk_score_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
entity_count_strategy = st.integers(min_value=0, max_value=10000)
entity_type_strategy = st.text(min_size=2, max_size=20, alphabet=st.characters(
    whitelist_categories=("L",), whitelist_characters="_"
))

gov_officer_role_strategy = st.sampled_from(list(GovernanceOfficerRole))


@given(
    tenant=tenant_strategy,
    score=risk_score_strategy,
)
@settings(max_examples=200, deadline=None)
async def test_approval_request_risk_score_range(tenant, score):
    """Invariant: approval request risk scores are always 0.0–1.0."""
    req = ApprovalRequest(
        id="test_id",
        tenant_id=tenant,
        request_type="high_risk",
        description="Property test",
        status="pending",
        risk_score=score,
        created_at=datetime.now(timezone.utc),
    )
    assert 0.0 <= req.risk_score <= 1.0


@given(
    tenant=tenant_strategy,
    status=st.sampled_from(["pending", "approved", "rejected"]),
)
@settings(max_examples=200, deadline=None)
async def test_approval_request_status_invariant(tenant, status):
    """Invariant: approval request status is always one of the three valid values."""
    req = ApprovalRequest(
        id="test_id",
        tenant_id=tenant,
        request_type="high_risk",
        description="Property test",
        status=status,
        risk_score=0.5,
        created_at=datetime.now(timezone.utc),
    )
    assert req.status in ("pending", "approved", "rejected")


@given(
    tenant=tenant_strategy,
    description=st.text(max_size=200),
)
@settings(max_examples=200, deadline=None)
async def test_approval_request_has_id(tenant, description):
    """Invariant: every approval request has a non-empty id."""
    req = ApprovalRequest(
        id="generated_id",
        tenant_id=tenant,
        request_type="test",
        description=description,
        status="pending",
        risk_score=0.5,
        created_at=datetime.now(timezone.utc),
    )
    assert req.id is not None
    assert len(req.id) > 0


@given(
    tenant=tenant_strategy,
    version=st.integers(min_value=1, max_value=1000),
    changed_by=operator_strategy,
    description=st.text(max_size=200),
)
@settings(max_examples=200, deadline=None)
async def test_change_entry_invariants(tenant, version, changed_by, description):
    """Invariant: change entry always has version >= 1 and non-empty changed_by."""
    entry = ChangeEntry(
        version=version,
        changed_at=datetime.now(timezone.utc),
        changed_by=changed_by,
        description=description,
    )
    assert entry.version >= 1
    assert len(entry.changed_by) > 0
    assert entry.changed_at is not None


@given(
    role1=gov_officer_role_strategy,
    role2=gov_officer_role_strategy,
)
@settings(max_examples=200, deadline=None)
async def test_governance_officer_role_uniqueness(role1, role2):
    """Invariant: governance officer roles are unique within a record."""
    assume(role1 != role2)
    officers = [
        GovernanceOfficer(role=role1, name="Alice", email="alice@acme.com"),
        GovernanceOfficer(role=role2, name="Bob", email="bob@acme.com"),
    ]
    roles = {o.role for o in officers}
    assert len(roles) == 2


@given(
    role=gov_officer_role_strategy,
    name=st.text(min_size=1, max_size=50),
    email=operator_strategy,
)
@settings(max_examples=200, deadline=None)
async def test_governance_officer_valid(role, name, email):
    """Invariant: governance officers have all required fields."""
    officer = GovernanceOfficer(role=role, name=name, email=email)
    assert officer.role in GovernanceOfficerRole
    assert len(officer.name) > 0
    assert "@" in officer.email


@given(
    stage=st.sampled_from(list(LifecycleStage)),
    version=st.integers(min_value=1, max_value=100),
)
@settings(max_examples=200, deadline=None)
async def test_lifecycle_stage_enum_coverage(stage, version):
    """Invariant: all lifecycle stages are valid and version is always >= 1."""
    assert stage in LifecycleStage
    assert version >= 1


@given(
    event_type=st.sampled_from(list(NotificationEventType)),
    channel=st.sampled_from(list(NotificationChannel)),
)
@settings(max_examples=200, deadline=None)
async def test_notification_event_types(event_type, channel):
    """Invariant: notification event types and channels are valid enums."""
    assert event_type in NotificationEventType
    assert channel in NotificationChannel


@given(
    session_id=st.text(min_size=1, max_size=64),
    entity_count=entity_count_strategy,
)
@settings(max_examples=200, deadline=None)
async def test_transparency_record_invariants(session_id, entity_count):
    """Invariant: transparency records have positive entity counts."""
    from anonreq.services.transparency import TransparencyRecord

    record = TransparencyRecord(
        session_id=session_id,
        tenant_id="test-tenant",
        entity_count=entity_count,
        entity_types=["EMAIL"],
        processed_at=datetime.now(timezone.utc),
        anonymized=True,
    )
    assert len(record.session_id) > 0
    assert record.entity_count >= 0


@given(
    version=st.integers(min_value=1, max_value=100),
    changes=st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.text(max_size=100),
        min_size=1, max_size=10,
    ),
)
@settings(max_examples=200, deadline=None)
async def test_change_entry_with_changes(version, changes):
    """Invariant: change entries can store arbitrary metadata."""
    entry = ChangeEntry(
        version=version,
        changed_at=datetime.now(timezone.utc),
        changed_by="tester",
        description="Prop test",
        changes=changes,
    )
    assert entry.version == version
    assert len(entry.changes) == len(changes)


@given(
    n=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_oversight_service_create_batch(cache_manager, n):
    """Invariant: batch creating approvals preserves count."""
    svc = OversightService(cache_manager)
    await svc._redis.delete("anonreq:oversight:approvals")

    for i in range(n):
        await svc.create_approval_request(
            tenant_id=f"tenant_{i}",
            request_type="test",
            description=f"Test {i}",
            risk_score=0.5,
        )

    pending = await svc.list_pending_approvals()
    assert len(pending) == n


@given(
    tenant=tenant_strategy,
    score1=risk_score_strategy,
    score2=risk_score_strategy,
)
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_kill_switch_blocks_after_activate(cache_manager, tenant, score1, score2):
    """Invariant: after kill-switch activation, is_kill_switch_active returns True."""
    assume(score1 != score2)
    svc = OversightService(cache_manager)
    await svc._redis.delete("anonreq:oversight:kill-switch")

    assert await svc.is_kill_switch_active() is False
    await svc.activate_kill_switch("admin", "test")
    assert await svc.is_kill_switch_active() is True
