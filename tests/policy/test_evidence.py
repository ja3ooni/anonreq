"""Tests for Policy Enforcement Evidence Store and manifests."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from anonreq.policy.evidence import EvidenceStore, PolicyEvidence, _hash_policy_state
from anonreq.policy.models import PolicyAction, PolicyDecision, PolicyRule


def _sample_rules() -> list[PolicyRule]:
    return [
        PolicyRule(
            rule_id="rule_001",
            action=PolicyAction.BLOCK,
            priority=10,
            enabled=True,
            conditions={"model": "gpt-4"},
            tenant_id="tenant_abc",
        ),
        PolicyRule(
            rule_id="rule_002",
            action=PolicyAction.ALLOW,
            priority=5,
            enabled=False,
            conditions={"model": "claude-3"},
            tenant_id="tenant_abc",
        ),
    ]


@pytest.fixture
def mock_policy_store() -> AsyncMock:
    store = AsyncMock()
    store.load_policies.return_value = _sample_rules()
    return store


@pytest.fixture
def evidence_store(mock_policy_store) -> EvidenceStore:
    return EvidenceStore(mock_policy_store)


def test_hash_policy_state_determinism():
    # Verify that the same policy state always produces the identical hash,
    # regardless of list ordering of rule objects.
    rules_a = _sample_rules()
    rules_b = list(reversed(rules_a))

    hash_a = _hash_policy_state(rules_a)
    hash_b = _hash_policy_state(rules_b)

    assert hash_a == hash_b
    assert len(hash_a) == 64  # SHA-256 hex string length


def test_hash_policy_state_different():
    # Verify that different policy states produce different hashes
    rules_a = _sample_rules()
    rules_c = _sample_rules()
    rules_c[0].enabled = False

    hash_a = _hash_policy_state(rules_a)
    hash_c = _hash_policy_state(rules_c)

    assert hash_a != hash_c


@pytest.mark.asyncio
async def test_record_decision_evidence(evidence_store):
    decision_ts = datetime.now(UTC)
    decision = PolicyDecision(
        action=PolicyAction.BLOCK,
        matched_rule_ids=["rule_001"],
        decision_ts=decision_ts,
        enforcement="test_decision_id_123",
    )

    record = await evidence_store.record_decision_evidence("tenant_abc", decision)

    assert isinstance(record, PolicyEvidence)
    assert record.tenant_id == "tenant_abc"
    assert record.action == PolicyAction.BLOCK
    assert record.decision_id == "test_decision_id_123"
    assert record.rule_count == 2
    assert record.enabled_rule_count == 1
    assert record.timestamp == decision_ts

    # Check version is the first 16 characters of the full hash
    assert record.policy_version == record.policy_hash[:16]

    # Check store caches it
    cached = await evidence_store.get_evidence(record.evidence_id)
    assert cached == record


@pytest.mark.asyncio
async def test_evidence_manifest_generation(evidence_store):
    decision_ts = datetime.now(UTC)
    decision = PolicyDecision(
        action=PolicyAction.BLOCK,
        matched_rule_ids=["rule_001"],
        decision_ts=decision_ts,
    )

    r1 = await evidence_store.record_decision_evidence("tenant_abc", decision)
    r2 = await evidence_store.record_decision_evidence("tenant_abc", decision)

    # Record a different tenant
    await evidence_store.record_decision_evidence("tenant_xyz", decision)

    manifest = await evidence_store.generate_manifest("tenant_abc")
    assert manifest["tenant_id"] == "tenant_abc"
    assert len(manifest["records"]) == 2
    assert manifest["records"][0]["evidence_id"] in (r1.evidence_id, r2.evidence_id)
    assert manifest["merkle_root"] is not None
    assert len(manifest["merkle_root"]) == 64


def test_no_sensitive_values_in_serialized_evidence(evidence_store):
    # Verify that serialized output doesn't contain raw prompt/tokens/entity values
    decision = PolicyDecision(
        action=PolicyAction.BLOCK,
        matched_rule_ids=["rule_001"],
        decision_ts=datetime.now(UTC),
        reason="Blocked due to SSN: 123-45-6789",  # potentially sensitive detail in reason
    )

    import asyncio
    record = asyncio.run(evidence_store.record_decision_evidence("tenant_abc", decision))

    # Serialize to JSON
    raw_json = record.model_dump_json()
    assert "123-45-6789" not in raw_json
    # It should only contain metadata rule IDs and reason field if allowed,
    # but let's confirm no real PII / tokens like "[SSN_0]" or similar are present
    assert "token" not in raw_json
    assert "payload" not in raw_json
