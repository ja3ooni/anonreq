from __future__ import annotations

from collections.abc import Callable
from typing import Any

from prometheus_client import REGISTRY, Counter, Histogram


def _collector(name: str, factory: Callable[[], Any]) -> Any:
    existing = getattr(REGISTRY, "_names_to_collectors", {}).get(name)
    if existing is not None:
        return existing
    return factory()


agent_tool_calls_inspected_total = _collector(
    "anonreq_agent_tool_calls_inspected_total",
    lambda: Counter(
        "anonreq_agent_tool_calls_inspected_total",
        "Agent tool calls inspected",
        labelnames=["action", "tenant_id"],
    ),
)

agent_tool_results_sanitized_total = _collector(
    "anonreq_agent_tool_results_sanitized_total",
    lambda: Counter(
        "anonreq_agent_tool_results_sanitized_total",
        "Tool results sanitized",
        labelnames=["entity_type", "tenant_id"],
    ),
)

agent_governance_duration_ms = _collector(
    "anonreq_agent_governance_duration_ms",
    lambda: Histogram(
        "anonreq_agent_governance_duration_ms",
        "Agent governance latency",
        labelnames=["operation"],
        buckets=(5, 10, 25, 50, 100, 200, 500),
    ),
)
