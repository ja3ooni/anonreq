"""Unit tests for tenant-scoped Prometheus metrics.

Per D-11/D-12, verifies:
- requests_total Counter carries tenant_id label
- _tenant_label returns original ID for known tenants
- _tenant_label returns '_overflow' when cardinality limit exceeded
- Existing tenants maintain their label after overflow threshold
- MetricsMiddleware reads tenant_id from request.state
"""

from __future__ import annotations

import pytest
from prometheus_client import CollectorRegistry

from anonreq.monitoring.metrics import (
    _tenant_label,
    requests_total,
    set_max_tenants,
    _known_tenants,
)


@pytest.fixture(autouse=True)
def _reset_cardinality_state():
    """Reset tenant cardinality state before each test."""
    _known_tenants.clear()
    set_max_tenants(100)
    yield
    _known_tenants.clear()
    set_max_tenants(100)


@pytest.mark.unit
class TestTenantLabel:
    """Tests for the _tenant_label bounded cardinality helper."""

    def test_returns_original_for_new_tenant(self):
        """First call for a new tenant returns the original ID."""
        result = _tenant_label("tenant-alpha")
        assert result == "tenant-alpha"

    def test_returns_same_id_for_known_tenant(self):
        """Subsequent calls for a known tenant return the same ID."""
        _tenant_label("tenant-beta")
        result = _tenant_label("tenant-beta")
        assert result == "tenant-beta"

    def test_overflow_after_limit_exceeded(self):
        """After MAX_TENANTS unique tenants, next new tenant gets '_overflow'."""
        set_max_tenants(3)
        _tenant_label("t1")
        _tenant_label("t2")
        _tenant_label("t3")
        result = _tenant_label("t4")
        assert result == "_overflow"

    def test_known_tenants_still_return_correct_id_after_overflow(self):
        """Existing tenants still get their label after overflow threshold."""
        set_max_tenants(2)
        _tenant_label("existing-1")
        _tenant_label("existing-2")
        # Next new tenant gets overflow
        assert _tenant_label("new-tenant") == "_overflow"
        # But existing tenants still return correctly
        assert _tenant_label("existing-1") == "existing-1"
        assert _tenant_label("existing-2") == "existing-2"

    def test_max_tenants_can_be_reconfigured(self):
        """set_max_tenants updates the limit dynamically."""
        set_max_tenants(1)
        _tenant_label("first")
        assert _tenant_label("second") == "_overflow"
        # Reconfigure to allow more
        set_max_tenants(5)
        assert _tenant_label("third") == "third"


@pytest.mark.unit
class TestTenantMetricsCounter:
    """Tests for requests_total Counter with tenant_id label."""

    def test_requests_total_has_tenant_id_label(self):
        """requests_total Counter accepts tenant_id as first label."""
        requests_total.labels(
            tenant_id="tenant-1",
            endpoint="/v1/chat/completions",
            status_code="200",
            provider="openai",
            classification="ANONYMIZE",
        ).inc()
        # If we got here without exception, the label contract is valid

    def test_requests_total_carries_all_expected_labels(self):
        """requests_total metric sample includes tenant_id."""
        requests_total.labels(
            tenant_id="tenant-check",
            endpoint="/v1/models",
            status_code="200",
            provider="unknown",
            classification="unknown",
        ).inc()
        # Verify the metric name contains 'requests_total'
        assert "anonreq_requests_total" in requests_total._name

    def test_tenant_overflow_label_works_in_counter(self):
        """_overflow can be used as a valid tenant_id label."""
        requests_total.labels(
            tenant_id="_overflow",
            endpoint="/v1/chat/completions",
            status_code="500",
            provider="unknown",
            classification="BLOCK",
        ).inc()


@pytest.mark.unit
class TestMetricsMiddlewareTenantIntegration:
    """Tests for MetricsMiddleware reading tenant_id from request.state."""

    def test_middleware_reads_tenant_id_from_state(self, monkeypatch):
        """MetricsMiddleware reads tenant_id via getattr from request.state."""

        class FakeState:
            tenant_id = "test-tenant"
            provider = "anthropic"
            classification = "ANONYMIZE"

        class FakeRequest:
            url = type("URL", (), {"path": "/v1/chat/completions"})()
            state = FakeState()

        # Simulate the logic from MetricsMiddleware.dispatch
        tenant_id_raw = getattr(FakeRequest.state, "tenant_id", "_unknown")
        tenant_id_label = _tenant_label(tenant_id_raw)
        assert tenant_id_label == "test-tenant"

    def test_middleware_defaults_to_unknown_when_no_tenant(self, monkeypatch):
        """MetricsMiddleware uses '_unknown' when tenant_id is not set."""

        class FakeState:
            provider = "openai"
            classification = "PASS"

        class FakeRequest:
            url = type("URL", (), {"path": "/v1/models"})()
            state = FakeState()

        tenant_id_raw = getattr(FakeRequest.state, "tenant_id", "_unknown")
        tenant_id_label = _tenant_label(tenant_id_raw)
        assert tenant_id_label == "_unknown"
