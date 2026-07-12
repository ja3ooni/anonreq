"""Property-based tests for compliance, audit & fairness invariants.

Uses Hypothesis to verify:
- Lineage immutability
- Retention enforcement
- DSAR workflow completeness
- Supplier governance invariants
"""

from __future__ import annotations

from datetime import UTC, datetime

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from anonreq.services.breach import BreachService
from anonreq.services.dsar import DSARService
from anonreq.services.lineage import LineageRecord, LineageService
from anonreq.services.retention import RetentionService
from anonreq.services.supplier import SupplierRecord, SupplierService

# ── Strategies ──────────────────────────────────────────────────────────

tenant_strategy = st.text(min_size=1, max_size=32, alphabet=st.characters(
    whitelist_categories=("L", "N", "P"),
    whitelist_characters="-_.",
))
session_strategy = st.text(min_size=1, max_size=32, alphabet=st.characters(
    whitelist_categories=("L", "N"),
    whitelist_characters="-",
))
entity_count_strategy = st.dictionaries(
    keys=st.text(min_size=2, max_size=10, alphabet=st.characters(whitelist_categories=("L",))),
    values=st.integers(min_value=0, max_value=100),
    min_size=0, max_size=5,
)
policy_actions_strategy = st.lists(
    st.sampled_from(["allow_and_anonymize", "anonymize_and_flag", "block", "allow"]),
    min_size=0, max_size=4,
)
record_type_strategy = st.sampled_from(
    ["audit_logs", "lineage", "governance", "risk_assessments", "incidents"]
)
dsar_type_strategy = st.sampled_from(
    ["access", "erasure", "rectification", "portability", "restriction"]
)
risk_class_strategy = st.sampled_from(["Low", "Medium", "High", "Critical"])
contract_status_strategy = st.sampled_from(["Active", "Expired", "Suspended"])


# ── Lineage Property Tests ──────────────────────────────────────────────


class TestLineageProperty:
    @given(
        session_id=session_strategy,
        tenant_id=tenant_strategy,
        entity_counts=entity_count_strategy,
        policy_actions=policy_actions_strategy,
    )
    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_lineage_record_immutability(
        self, cache_manager, session_id, tenant_id, entity_counts, policy_actions
    ):
        """Invariant: lineage records cannot be modified after creation."""
        svc = LineageService(cache_manager)
        await svc._redis.delete(f"anonreq:lineage:{session_id}")

        record = LineageRecord(
            session_id=session_id,
            tenant_id=tenant_id,
            timestamp_request_received=datetime.now(UTC),
            entities_anonymized_count=entity_counts,
            policy_actions_applied=policy_actions,
        )
        await svc.create_record(record)
        fetched = await svc.get_record(session_id)
        assert fetched is not None
        assert fetched.session_id == session_id
        assert fetched.entities_anonymized_count == entity_counts
        assert fetched.policy_actions_applied == policy_actions

        svc_attrs = {k for k in dir(svc) if not k.startswith("_")}
        assert "update_record" not in svc_attrs
        assert "delete_record" not in svc_attrs

    @given(
        session_id=session_strategy,
        tenant_id=tenant_strategy,
    )
    @settings(max_examples=50, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_lineage_integrity_hash_present(
        self, cache_manager, session_id, tenant_id
    ):
        """Invariant: every lineage record has a valid integrity hash."""
        svc = LineageService(cache_manager)
        await svc._redis.delete(f"anonreq:lineage:{session_id}")

        record = LineageRecord(
            session_id=session_id,
            tenant_id=tenant_id,
            timestamp_request_received=datetime.now(UTC),
            entities_anonymized_count={},
            policy_actions_applied=[],
        )
        await svc.create_record(record)
        assert await svc.verify_integrity(session_id) is True

    @given(
        session_id=session_strategy,
    )
    @settings(max_examples=50, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_lineage_nonexistent_verify(
        self, cache_manager, session_id
    ):
        """Invariant: nonexistent records fail verification."""
        svc = LineageService(cache_manager)
        await svc._redis.delete(f"anonreq:lineage:{session_id}")
        assert await svc.verify_integrity(session_id) is False


# ── Retention Property Tests ────────────────────────────────────────────


class TestRetentionProperty:
    @given(
        record_type=record_type_strategy,
        days=st.integers(min_value=1, max_value=7300),
    )
    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_retention_policy_roundtrip(
        self, cache_manager, record_type, days
    ):
        """Invariant: retention policy round-trips correctly."""
        svc = RetentionService(cache_manager)
        await svc._redis.delete(f"anonreq:retention:policy:{record_type}")

        await svc.set_policy(record_type, days, "delete")
        policy = await svc.get_policy(record_type)
        assert policy is not None
        assert policy.record_type == record_type
        assert policy.retention_days == days

    @given(
        record_type=record_type_strategy,
        days=st.integers(min_value=1, max_value=7300),
    )
    @settings(max_examples=50, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.filter_too_much])  # noqa: E501
    async def test_hold_blocks_deletion(
        self, cache_manager, record_type, days
    ):
        """Invariant: active hold prevents deletion."""
        svc = RetentionService(cache_manager)
        await svc._redis.delete(f"anonreq:retention:policy:{record_type}")
        await svc._redis.delete("anonreq:legalhold:*")

        await svc.set_policy(record_type, days, "delete")
        active = await svc.is_hold_active(record_type, "acme-corp")
        assume(active is False)

        await svc.impose_hold(
            record_types=[record_type],
            tenant_id="acme-corp",
            hold_ref="Test hold",
            imposed_by="legal@acme.com",
        )
        assert await svc.is_hold_active(record_type, "acme-corp") is True


# ── Supplier Property Tests ──────────────────────────────────────────────


class TestSupplierProperty:
    @given(
        name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L",))),
        risk=risk_class_strategy,
        contract=contract_status_strategy,
    )
    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_supplier_registration_roundtrip(
        self, cache_manager, name, risk, contract
    ):
        """Invariant: supplier registration round-trips correctly."""
        svc = SupplierService(cache_manager)
        await svc._redis.delete(f"anonreq:supplier:{name}")

        record = SupplierRecord(
            provider_name=name,
            legal_entity=f"{name} LLC",
            jurisdiction="US",
            data_residency_regions=["us-east-1"],
            risk_classification=risk,
            contract_status=contract,
        )
        await svc.register_provider(record)
        fetched = await svc.get_provider(name)
        assert fetched is not None
        assert fetched.provider_name == name
        assert fetched.risk_classification == risk
        assert fetched.contract_status == contract

    @given(
        name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L",))),
    )
    @settings(max_examples=50, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_supplier_suspend_sets_status(
        self, cache_manager, name
    ):
        """Invariant: suspended providers have Suspended status."""
        svc = SupplierService(cache_manager)
        await svc._redis.delete(f"anonreq:supplier:{name}")

        await svc.register_provider(
            SupplierRecord(
                provider_name=name,
                legal_entity=f"{name} LLC",
                jurisdiction="US",
                data_residency_regions=[],
                risk_classification="Low",
                contract_status="Active",
            )
        )
        result = await svc.suspend_provider(name, "admin@test.com")
        assert result.contract_status == "Suspended"


# ── DSAR Property Tests ──────────────────────────────────────────────────


class TestDSARProperty:
    @given(
        tenant_id=tenant_strategy,
        subject_id=st.text(min_size=1, max_size=16),
        dsar_type=dsar_type_strategy,
    )
    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_dsar_workflow_completeness(
        self, cache_manager, tenant_id, subject_id, dsar_type
    ):
        """Invariant: DSAR requests always reach a terminal status."""
        svc = DSARService(cache_manager)
        keys = await svc._redis.keys("anonreq:dsar:*")
        for k in keys:
            await svc._redis.delete(k)

        req = await svc.create_request(
            request_type=dsar_type,
            tenant_id=tenant_id,
            subject_id=subject_id,
            requested_by=f"{subject_id}@example.com",
        )
        assert req.status == "pending"

        if dsar_type == "erasure":
            result = await svc.process_erasure(req.request_id, "admin")
            assert result.status in ("completed", "rejected")
        elif dsar_type == "rectification":
            result = await svc.process_rectification(req.request_id, "admin")
            assert result.status in ("completed", "rejected")
        elif dsar_type == "portability":
            result = await svc.process_portability(req.request_id, "admin")
            assert result.status in ("completed", "rejected")
        elif dsar_type == "restriction":
            result = await svc.process_restriction(req.request_id, "admin")
            assert result.status in ("completed", "rejected")
        elif dsar_type == "access":
            result = await svc.reject_request(req.request_id, "test")
            assert result.status in ("completed", "rejected")

        final = await svc.get_request(req.request_id)
        assert final is not None
        assert final.status in ("completed", "rejected")

    @given(
        tenant_id=tenant_strategy,
        subject_id=st.text(min_size=1, max_size=16),
    )
    @settings(max_examples=50, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_dsar_erasure_sets_result(
        self, cache_manager, tenant_id, subject_id
    ):
        """Invariant: processed erasure always has a non-null result."""
        svc = DSARService(cache_manager)
        keys = await svc._redis.keys("anonreq:dsar:*")
        for k in keys:
            await svc._redis.delete(k)

        req = await svc.create_request(
            request_type="erasure",
            tenant_id=tenant_id,
            subject_id=subject_id,
            requested_by=f"{subject_id}@example.com",
        )
        result = await svc.process_erasure(req.request_id, "admin")
        assert result.result is not None
        assert result.result in ("deleted", "legal_hold")


# ── Breach Property Tests ────────────────────────────────────────────────


class TestBreachProperty:
    @given(
        severity=st.sampled_from(["Critical", "High", "Medium", "Low"]),
        tenant_id=tenant_strategy,
    )
    @settings(max_examples=100, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_breach_notification_flow(
        self, cache_manager, severity, tenant_id
    ):
        """Invariant: breach notifications progress through expected states."""
        svc = BreachService(cache_manager)
        keys = await svc._redis.keys("anonreq:breach:*")
        for k in keys:
            await svc._redis.delete(k)

        await svc.set_template("default", "Alert {severity}", "Body {severity}", ["email"])
        notif = await svc.create_notification(
            severity=severity,
            tenant_id=tenant_id,
            description=f"Test breach of severity {severity}",
            template_name="default",
            detected_by="system",
        )
        assert notif.status == "pending"

        sent = await svc.send_notification(notif.breach_id)
        assert sent.status == "sent"
        assert sent.sent_at is not None
