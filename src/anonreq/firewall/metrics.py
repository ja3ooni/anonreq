from __future__ import annotations

from collections.abc import Callable
from typing import Any

from prometheus_client import Counter, Histogram, REGISTRY


def _collector(name: str, factory: Callable[[], Any]) -> Any:
    existing = getattr(REGISTRY, "_names_to_collectors", {}).get(name)
    if existing is not None:
        return existing
    return factory()


firewall_blocks_total = _collector(
    "anonreq_firewall_blocks_total",
    lambda: Counter(
        "anonreq_firewall_blocks_total",
        "AI Firewall blocked requests",
        labelnames=["detection_type", "tenant_id"],
    ),
)

firewall_evaluation_duration_ms = _collector(
    "anonreq_firewall_evaluation_duration_ms",
    lambda: Histogram(
        "anonreq_firewall_evaluation_duration_ms",
        "AI Firewall evaluation latency",
        labelnames=["decision"],
        buckets=(1, 5, 10, 20, 50, 100, 200),
    ),
)

firewall_latency_budget_exceeded_total = _collector(
    "anonreq_firewall_latency_budget_exceeded_total",
    lambda: Counter(
        "anonreq_firewall_latency_budget_exceeded_total",
        "Firewall latency over 20ms budget",
    ),
)


class FirewallMetrics:
    _instance: FirewallMetrics | None = None

    def __init__(self) -> None:
        self.prompt_security_events = _collector(
            "anonreq_prompt_security_events_total",
            lambda: Counter(
                "anonreq_prompt_security_events_total",
                "Total prompt security events (injection, violation, rule reload)",
                labelnames=["event_type", "tenant_id", "category"],
            ),
        )

    @classmethod
    def get_instance(cls) -> FirewallMetrics:
        if cls._instance is None:
            cls._instance = FirewallMetrics()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def record_injection(self, tenant_id: str, category: str) -> None:
        self.prompt_security_events.labels(
            event_type="injection_detected",
            tenant_id=tenant_id,
            category=category,
        ).inc()

    def record_outbound_violation(self, tenant_id: str, category: str) -> None:
        self.prompt_security_events.labels(
            event_type="outbound_violation",
            tenant_id=tenant_id,
            category=category,
        ).inc()

    def record_rule_reload(self) -> None:
        self.prompt_security_events.labels(
            event_type="rule_reloaded",
            tenant_id="",
            category="",
        ).inc()
