"""Tests for Policy Engine metrics."""

from __future__ import annotations

import pytest
from prometheus_client import CollectorRegistry, generate_latest

from anonreq.policy.metrics import PolicyMetrics, validate_label_value


@pytest.fixture
def test_registry() -> CollectorRegistry:
    return CollectorRegistry()


@pytest.fixture
def metrics(test_registry) -> PolicyMetrics:
    return PolicyMetrics(test_registry)


def test_metrics_registration(metrics):
    assert metrics.policy_decisions is not None
    assert metrics.policy_denials is not None
    assert metrics.rate_limit_hits is not None
    assert metrics.spend_limit_hits is not None


def test_record_decision(metrics, test_registry):
    metrics.record_decision("tenant_1", "ALLOW")
    metrics.record_decision("tenant_1", "BLOCK")

    output = generate_latest(test_registry).decode("utf-8")
    assert 'anonreq_policy_decisions_total{action="ALLOW",tenant_id="tenant_1"} 1.0' in output
    assert 'anonreq_policy_decisions_total{action="BLOCK",tenant_id="tenant_1"} 1.0' in output


def test_record_denial(metrics, test_registry):
    metrics.record_denial("tenant_1", "rate_limit_exceeded")

    output = generate_latest(test_registry).decode("utf-8")
    assert 'anonreq_policy_denials_total{reason="rate_limit_exceeded",tenant_id="tenant_1"} 1.0' in output


def test_record_rate_limit(metrics, test_registry):
    metrics.record_rate_limit("tenant_1", "RPM")

    output = generate_latest(test_registry).decode("utf-8")
    assert 'anonreq_rate_limit_hits_total{limit_type="RPM",tenant_id="tenant_1"} 1.0' in output


def test_record_spend_limit(metrics, test_registry):
    metrics.record_spend_limit("tenant_1", "daily")

    output = generate_latest(test_registry).decode("utf-8")
    assert 'anonreq_spend_limit_hits_total{budget_type="daily",tenant_id="tenant_1"} 1.0' in output


def test_label_cardinality_rejection(metrics):
    # Test length rejection (> 64 characters)
    with pytest.raises(ValueError, match="Label value too long"):
        metrics.record_decision("a" * 65, "ALLOW")

    # Test invalid character rejection (e.g. spaces or other injection chars)
    with pytest.raises(ValueError, match="Invalid label value format"):
        metrics.record_decision("tenant; injection", "ALLOW")

    # Test valid label values are accepted
    assert validate_label_value("tenant.1_sub-tenant") == "tenant.1_sub-tenant"


def test_metrics_registration_idempotency(test_registry):
    # Registering twice with the same registry should be idempotent
    m1 = PolicyMetrics(test_registry)
    m2 = PolicyMetrics(test_registry)

    assert m1.policy_decisions is m2.policy_decisions
    # Check that they reference the same counter objects
    assert m1.policy_decisions == m2.policy_decisions
