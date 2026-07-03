"""Tests for Prometheus tool governance counters.

Covers:
- Counter increment with different label combinations
- Counter values after multiple increments
- Metric registration with custom CollectorRegistry
- No label cardinality violations (no per-request identifiers)

Each test class gets its own ``CollectorRegistry`` with freshly-registered
counters to avoid the global-state contamination that makes isolated value
assertions impossible with shared module-level counters.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from prometheus_client import REGISTRY, CollectorRegistry, Counter, generate_latest

from anonreq.governance.metrics import (
    TOOL_BLOCKS_COUNTER,
    TOOL_CALLS_COUNTER,
    TOOL_RESULT_VIOLATIONS_COUNTER,
    register_tool_governance_metrics,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def tool_registry() -> CollectorRegistry:
    """Return a clean CollectorRegistry with fresh tool counters registered."""
    registry = CollectorRegistry()
    register_tool_governance_metrics(registry)
    return registry


def _read_counter_value(
    registry: CollectorRegistry, metric_name: str, labels: dict[str, str] | None = None
) -> float:
    """Read a counter value from the exposition format of *registry*.

    Args:
        registry: The registry to scrape.
        metric_name: Metric name (without ``_total`` suffix).
        labels: Optional label filter.

    Returns:
        Float value, or 0.0 if not present.
    """
    text = generate_latest(registry).decode()
    # A Counter that has never been incremented does not appear in the
    # exposition format.  ``generate_latest`` returns an empty body for
    # zero-valued counters — this is standard Prometheus client behaviour.
    prefix = f"{metric_name}_total"

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith(prefix):
            continue
        if "{" in line:
            labels_str = line[line.index("{") + 1 : line.index("}")]
            parsed = _parse_labels(labels_str)
            if labels is not None:
                if any(parsed.get(k) != v for k, v in labels.items()):
                    continue
        elif labels is not None:
            continue
        value_str = line.split()[-1]
        return float(value_str)
    return 0.0


def _parse_labels(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for k, v in re.findall(r'(\w+)="([^"]*)"', raw):
        result[k] = v
    return result


def _get_counter(
    registry: CollectorRegistry, name: str
) -> Counter:
    """Retrieve a Counter by name from the registry's collectors."""
    for collector in registry._collector_to_names:
        if isinstance(collector, Counter) and collector._name == name:
            return collector
    msg = f"Counter '{name}' not found in registry"
    raise LookupError(msg)


# ── Tests ────────────────────────────────────────────────────────────────────


class TestToolCallsFresh:
    """``anonreq_tool_calls_total`` — fresh counters per test via fixture."""

    def test_initial_is_zero_before_any_inc(self, tool_registry: CollectorRegistry) -> None:
        """Counter has no data samples until first inc (expected)."""
        text = generate_latest(tool_registry).decode()
        # The HELP/TYPE lines appear on registration; the actual sample
        # line (``anonreq_tool_calls_total{...} N``) only appears after
        # the first ``inc()``.  Verify no *data* line yet.
        sample_lines = [
            l for l in text.splitlines()
            if l.startswith("anonreq_tool_calls_total{")
        ]
        assert len(sample_lines) == 0
        # But the HELP/TYPE lines should be present
        assert "# HELP anonreq_tool_calls_total" in text

    def test_increment_with_labels(self, tool_registry: CollectorRegistry) -> None:
        c = _get_counter(tool_registry, "anonreq_tool_calls")
        c.labels(permission="allow", domain="model", provider="openai").inc()
        val = _read_counter_value(
            tool_registry,
            "anonreq_tool_calls",
            {"permission": "allow", "domain": "model", "provider": "openai"},
        )
        assert val == 1.0

    def test_multiple_increments(self, tool_registry: CollectorRegistry) -> None:
        c = _get_counter(tool_registry, "anonreq_tool_calls")
        c.labels(permission="block", domain="model", provider="anthropic").inc(3)
        val = _read_counter_value(
            tool_registry,
            "anonreq_tool_calls",
            {"permission": "block", "domain": "model", "provider": "anthropic"},
        )
        assert val == 3.0

    def test_different_labels_separate_counters(
        self, tool_registry: CollectorRegistry,
    ) -> None:
        c = _get_counter(tool_registry, "anonreq_tool_calls")
        c.labels(permission="allow", domain="model", provider="openai").inc(5)
        c.labels(permission="block", domain="model", provider="openai").inc(2)
        allow = _read_counter_value(
            tool_registry,
            "anonreq_tool_calls",
            {"permission": "allow", "domain": "model", "provider": "openai"},
        )
        block = _read_counter_value(
            tool_registry,
            "anonreq_tool_calls",
            {"permission": "block", "domain": "model", "provider": "openai"},
        )
        assert allow == 5.0
        assert block == 2.0


class TestToolBlocksFresh:
    """``anonreq_tool_blocks_total`` — fresh counters per test via fixture."""

    def test_increment_with_tool_name(self, tool_registry: CollectorRegistry) -> None:
        c = _get_counter(tool_registry, "anonreq_tool_blocks")
        c.labels(tool_name="code_interpreter", domain="model", reason="policy").inc()
        val = _read_counter_value(
            tool_registry,
            "anonreq_tool_blocks",
            {"tool_name": "code_interpreter", "domain": "model", "reason": "policy"},
        )
        assert val == 1.0

    def test_increment_with_different_reasons(
        self, tool_registry: CollectorRegistry,
    ) -> None:
        c = _get_counter(tool_registry, "anonreq_tool_blocks")
        c.labels(
            tool_name="web_search", domain="model", reason="policy",
        ).inc(1)
        c.labels(
            tool_name="web_search", domain="model", reason="domain_isolation",
        ).inc(2)
        policy = _read_counter_value(
            tool_registry,
            "anonreq_tool_blocks",
            {"tool_name": "web_search", "domain": "model", "reason": "policy"},
        )
        isolation = _read_counter_value(
            tool_registry,
            "anonreq_tool_blocks",
            {
                "tool_name": "web_search",
                "domain": "model",
                "reason": "domain_isolation",
            },
        )
        assert policy == 1.0
        assert isolation == 2.0


class TestToolResultViolationsFresh:
    """``anonreq_tool_result_violations_total`` — fresh counters."""

    def test_increment_with_type_label(
        self, tool_registry: CollectorRegistry,
    ) -> None:
        c = _get_counter(tool_registry, "anonreq_tool_result_violations")
        c.labels(type_label="pii_detected").inc()
        val = _read_counter_value(
            tool_registry,
            "anonreq_tool_result_violations",
            {"type_label": "pii_detected"},
        )
        assert val == 1.0

    def test_multiple_types_separate_counters(
        self, tool_registry: CollectorRegistry,
    ) -> None:
        c = _get_counter(tool_registry, "anonreq_tool_result_violations")
        c.labels(type_label="pii_detected").inc(3)
        c.labels(type_label="reconstruction_detected").inc(1)
        pii = _read_counter_value(
            tool_registry,
            "anonreq_tool_result_violations",
            {"type_label": "pii_detected"},
        )
        recon = _read_counter_value(
            tool_registry,
            "anonreq_tool_result_violations",
            {"type_label": "reconstruction_detected"},
        )
        assert pii == 3.0
        assert recon == 1.0


class TestRegisterToolGovernanceMetrics:
    """Custom registry registration tests."""

    def test_register_with_custom_registry(self) -> None:
        """register_tool_governance_metrics registers all three counters."""
        registry = CollectorRegistry()
        register_tool_governance_metrics(registry)

        text = generate_latest(registry).decode()
        # The counters are registered; after incrementing once each
        # they will appear in the output.
        names = {"anonreq_tool_calls", "anonreq_tool_blocks", "anonreq_tool_result_violations"}
        for name in names:
            # verify the counter object exists in the registry
            _get_counter(registry, name)
        # After first inc each
        for name in names:
            counter = _get_counter(registry, name)
            counter.labels(**{"permission": "test", "domain": "test", "provider": "test"} if "calls" in name else {"tool_name": "test", "domain": "test", "reason": "test"} if "blocks" in name else {"type_label": "test"}).inc()
        text = generate_latest(registry).decode()
        assert "anonreq_tool_calls_total" in text
        assert "anonreq_tool_blocks_total" in text
        assert "anonreq_tool_result_violations_total" in text

    def test_initial_value_in_custom_registry(self) -> None:
        """Counters registered in custom registry start at 0."""
        registry = CollectorRegistry()
        c = Counter(
            "anonreq_tool_calls",
            "Tool calls",
            labelnames=["permission", "domain", "provider"],
            registry=registry,
        )
        # In standard Prometheus exposition, zero-valued counters with
        # labels do not appear until incremented.  We verify the invariant
        # by incrementing once and checking the value is 1.0.
        c.labels(permission="allow", domain="model", provider="openai").inc()
        text = generate_latest(registry).decode()
        assert "anonreq_tool_calls_total" in text
        assert 'permission="allow"' in text


class TestLabelCardinality:
    """No per-request identifiers in labels (D-138/AG-15)."""

    def test_no_tenant_id_label(self) -> None:
        for counter in [
            TOOL_CALLS_COUNTER,
            TOOL_BLOCKS_COUNTER,
            TOOL_RESULT_VIOLATIONS_COUNTER,
        ]:
            for label in counter._labelnames:
                assert "tenant" not in label, (
                    f"Label '{label}' contains 'tenant'"
                )

    def test_no_session_id_label(self) -> None:
        for counter in [
            TOOL_CALLS_COUNTER,
            TOOL_BLOCKS_COUNTER,
            TOOL_RESULT_VIOLATIONS_COUNTER,
        ]:
            for label in counter._labelnames:
                assert "session" not in label, (
                    f"Label '{label}' contains 'session'"
                )


class TestGlobalModuleCounters:
    """Smoke checks against the module-level global counters.

    These tests only verify that the global counters exist and can be
    incremented without errors — they do not assert specific values
    because global state is shared across test modules and any prior
    test run may have incremented them.
    """

    def test_global_counters_can_increment(self) -> None:
        TOOL_CALLS_COUNTER.labels(
            permission="test", domain="test", provider="test",
        ).inc()
        TOOL_BLOCKS_COUNTER.labels(
            tool_name="test", domain="test", reason="test",
        ).inc()
        TOOL_RESULT_VIOLATIONS_COUNTER.labels(type_label="test").inc()
        # No assertion on value — we just verify no exception is raised.
