"""Unit tests for the Prometheus metrics module (D-138, D-139).

Tests cover:
- All 8 metric objects are importable with correct types
- Label names match D-139 specification exactly
- Histogram buckets match D-139
- Counter initial values are 0, gauge initial value is 0
- Metric docstrings are non-empty and describe purpose/label semantics
- No PII or entity value appears in any label name (AG-15)
"""

from prometheus_client import Counter, Histogram, Gauge

from anonreq.monitoring import metrics as m


def test_all_8_metrics_importable():
    """All 8 metric objects are importable from monitoring.metrics module."""
    assert hasattr(m, "requests_total")
    assert hasattr(m, "detection_latency")
    assert hasattr(m, "entities_detected")
    assert hasattr(m, "unrestored_tokens")
    assert hasattr(m, "fail_secure_events")
    assert hasattr(m, "audit_failures")
    assert hasattr(m, "processing_overhead")
    assert hasattr(m, "active_config_version")


class TestMetricTypes:
    """Verify each metric is the correct Prometheus type."""

    def test_requests_total_is_counter(self):
        assert isinstance(m.requests_total, Counter)

    def test_detection_latency_is_histogram(self):
        assert isinstance(m.detection_latency, Histogram)

    def test_entities_detected_is_counter(self):
        assert isinstance(m.entities_detected, Counter)

    def test_unrestored_tokens_is_counter(self):
        assert isinstance(m.unrestored_tokens, Counter)

    def test_fail_secure_events_is_counter(self):
        assert isinstance(m.fail_secure_events, Counter)

    def test_audit_failures_is_counter(self):
        assert isinstance(m.audit_failures, Counter)

    def test_processing_overhead_is_histogram(self):
        assert isinstance(m.processing_overhead, Histogram)

    def test_active_config_version_is_gauge(self):
        assert isinstance(m.active_config_version, Gauge)


class TestLabelNames:
    """Verify label names match D-139 specification exactly."""

    def test_requests_total_labels(self):
        assert m.requests_total._labelnames == (
            "endpoint", "status_code", "provider", "classification"
        )

    def test_detection_latency_no_labels(self):
        assert m.detection_latency._labelnames == ()

    def test_entities_detected_labels(self):
        assert m.entities_detected._labelnames == ("entity_type", "locale")

    def test_unrestored_tokens_labels(self):
        assert m.unrestored_tokens._labelnames == ("endpoint",)

    def test_fail_secure_events_labels(self):
        assert m.fail_secure_events._labelnames == ("failure_type",)

    def test_audit_failures_no_labels(self):
        assert m.audit_failures._labelnames == ()

    def test_processing_overhead_no_labels(self):
        assert m.processing_overhead._labelnames == ()

    def test_active_config_version_no_labels(self):
        assert m.active_config_version._labelnames == ()


class TestHistogramBuckets:
    """Verify histogram buckets match D-139."""

    EXPECTED_BUCKETS = (5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0)

    def test_detection_latency_buckets(self):
        assert m.detection_latency._buckets == self.EXPECTED_BUCKETS

    def test_processing_overhead_buckets(self):
        assert m.processing_overhead._buckets == self.EXPECTED_BUCKETS


class TestInitialValues:
    """Verify counters and gauges start at zero."""

    def test_requests_total_initial_zero(self):
        assert m.requests_total._value.get() == 0.0

    def test_entities_detected_initial_zero(self):
        assert m.entities_detected._value.get() == 0.0

    def test_unrestored_tokens_initial_zero(self):
        assert m.unrestored_tokens._value.get() == 0.0

    def test_fail_secure_events_initial_zero(self):
        assert m.fail_secure_events._value.get() == 0.0

    def test_audit_failures_initial_zero(self):
        assert m.audit_failures._value.get() == 0.0

    def test_active_config_version_initial_zero(self):
        assert m.active_config_version._value.get() == 0.0


class TestDocstrings:
    """Verify all metric docstrings are non-empty."""

    def test_requests_total_docstring(self):
        assert m.requests_total._documentation.strip()

    def test_detection_latency_docstring(self):
        assert m.detection_latency._documentation.strip()

    def test_entities_detected_docstring(self):
        assert m.entities_detected._documentation.strip()

    def test_unrestored_tokens_docstring(self):
        assert m.unrestored_tokens._documentation.strip()

    def test_fail_secure_events_docstring(self):
        assert m.fail_secure_events._documentation.strip()

    def test_audit_failures_docstring(self):
        assert m.audit_failures._documentation.strip()

    def test_processing_overhead_docstring(self):
        assert m.processing_overhead._documentation.strip()

    def test_active_config_version_docstring(self):
        assert m.active_config_version._documentation.strip()


class TestNoPIIInLabels:
    """Verify no PII or entity values in any label name (AG-15)."""

    def test_no_sensitive_keys_in_label_names(self):
        """Label names must not reference tenant_id, request_id, session_id, or raw content."""
        all_labels: set[str] = set()
        for metric_obj in [
            m.requests_total,
            m.detection_latency,
            m.entities_detected,
            m.unrestored_tokens,
            m.fail_secure_events,
            m.audit_failures,
            m.processing_overhead,
            m.active_config_version,
        ]:
            all_labels.update(metric_obj._labelnames)

        forbidden_substrings = [
            "tenant", "request_id", "session", "user_id",
            "email", "phone", "name", "address", "credit_card",
            "ssn", "password", "secret", "token", "api_key",
            "content", "text", "prompt", "message",
        ]
        for label in all_labels:
            label_lower = label.lower()
            for forbidden in forbidden_substrings:
                assert forbidden not in label_lower, (
                    f"Label '{label}' contains forbidden substring '{forbidden}'"
                )
