"""Prometheus tool governance counters.

Per SECURITY-ACCANCE.md required metrics:
- ``anonreq_tool_calls_total`` by permission label
- ``anonreq_tool_blocks_total`` by tool label
- ``anonreq_tool_result_violations_total`` by type label

All metrics use only low-cardinality labels per D-138/AG-15.  No
per-request identifiers (tenant_id, session_id) appear in any label.
"""

from __future__ import annotations

from prometheus_client import Counter, CollectorRegistry

# ── Module-level counters (auto-register with default REGISTRY) ──────

TOOL_CALLS_COUNTER = Counter(
    "anonreq_tool_calls_total",
    "Tool calls evaluated by governance",
    ["permission", "domain", "provider"],
)

TOOL_BLOCKS_COUNTER = Counter(
    "anonreq_tool_blocks_total",
    "Tool calls blocked by governance",
    ["tool_name", "domain", "reason"],
)

TOOL_RESULT_VIOLATIONS_COUNTER = Counter(
    "anonreq_tool_result_violations_total",
    "Tool result inspection violations",
    ["type_label"],  # pii_detected, reconstruction_detected
)


def register_tool_governance_metrics(registry: CollectorRegistry) -> None:
    """Register all tool governance counters with the given registry.

    Creates fresh Counter instances bound to the custom registry.
    Useful for test isolation where the default registry should not
    be polluted, or for multi-registry deployment scenarios.

    Args:
        registry: Prometheus ``CollectorRegistry`` to register with.
    """
    Counter(
        "anonreq_tool_calls_total",
        "Tool calls evaluated by governance",
        ["permission", "domain", "provider"],
        registry=registry,
    )
    Counter(
        "anonreq_tool_blocks_total",
        "Tool calls blocked by governance",
        ["tool_name", "domain", "reason"],
        registry=registry,
    )
    Counter(
        "anonreq_tool_result_violations_total",
        "Tool result inspection violations",
        ["type_label"],
        registry=registry,
    )
