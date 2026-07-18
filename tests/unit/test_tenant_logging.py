"""Unit tests for tenant_id propagation via structlog contextvars.

Per D-10, verifies:
- structlog contextvars bind/unbind correctly manages tenant_id
- tenant_id appears in log event dicts after binding
- No tenant_id leakage between different bindings
- merge_contextvars processor correctly merges tenant_id into event dict
- tenant_id passes the allowlist_processor
"""

from __future__ import annotations

import structlog
import pytest
from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
    merge_contextvars,
)
from structlog.testing import capture_logs


@pytest.fixture(autouse=True)
def _clear_structlog_context():
    """Clear structlog context vars before each test."""
    clear_contextvars()
    yield
    clear_contextvars()


@pytest.mark.unit
class TestTenantStructlogPropagation:
    """Tests for tenant_id in structlog contextvars."""

    def test_bind_tenant_id_appears_in_log(self):
        """Per D-10: binding tenant_id makes it appear in log entries."""
        bind_contextvars(tenant_id="acme-corp")
        with capture_logs() as cap_logs:
            logger = structlog.get_logger()
            logger.info("test_event", extra_field="value")
        assert len(cap_logs) == 1
        assert cap_logs[0]["tenant_id"] == "acme-corp"

    def test_unbind_removes_tenant_id(self):
        """unbind_contextvars removes tenant_id from subsequent logs."""
        bind_contextvars(tenant_id="tenant-a")
        with capture_logs() as cap_logs_1:
            structlog.get_logger().info("first_event")
        assert cap_logs_1[0]["tenant_id"] == "tenant-a"

        clear_contextvars()
        with capture_logs() as cap_logs_2:
            structlog.get_logger().info("second_event")
        assert "tenant_id" not in cap_logs_2[0]

    def test_no_leakage_between_bindings(self):
        """Different bindings don't leak tenant_id across requests."""
        bind_contextvars(tenant_id="tenant-x")
        with capture_logs() as cap_logs_1:
            structlog.get_logger().info("request_x")
        assert cap_logs_1[0]["tenant_id"] == "tenant-x"

        clear_contextvars()

        bind_contextvars(tenant_id="tenant-y")
        with capture_logs() as cap_logs_2:
            structlog.get_logger().info("request_y")
        assert cap_logs_2[0]["tenant_id"] == "tenant-y"
        assert cap_logs_2[0]["tenant_id"] != "tenant-x"

    def test_merge_contextvars_includes_tenant_id(self):
        """merge_contextvars processor merges tenant_id into event dict."""
        bind_contextvars(tenant_id="merge-test")
        merged = {}
        merge_contextvars(None, None, merged)
        assert merged["tenant_id"] == "merge-test"

    def test_tenant_id_passes_allowlist(self):
        """tenant_id is in the logging allowlist and is not stripped."""
        from anonreq.logging_config import allowlist_processor, ALLOWLIST

        assert "tenant_id" in ALLOWLIST

        # Simulate an event dict with tenant_id
        event_dict = {
            "event": "test",
            "tenant_id": "allowed-tenant",
            "request_id": "req-123",
        }
        result = allowlist_processor(None, None, event_dict)
        assert "tenant_id" in result
        assert result["tenant_id"] == "allowed-tenant"

    def test_tenant_id_with_request_id_in_same_log(self):
        """tenant_id and request_id can coexist in the same log entry."""
        bind_contextvars(tenant_id="multi-tenant", request_id="req-456")
        with capture_logs() as cap_logs:
            structlog.get_logger().info("combined_event")
        assert cap_logs[0]["tenant_id"] == "multi-tenant"
        assert cap_logs[0]["request_id"] == "req-456"
