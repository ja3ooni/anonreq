from __future__ import annotations

from prometheus_client import Counter


class FirewallMetrics:
    _instance: FirewallMetrics | None = None

    def __init__(self) -> None:
        try:
            self.prompt_security_events = Counter(
                "anonreq_prompt_security_events_total",
                "Total prompt security events (injection, violation, rule reload)",
                labelnames=["event_type", "tenant_id", "category"],
            )
        except ValueError:
            from prometheus_client import REGISTRY

            self.prompt_security_events = REGISTRY._names_to_collectors[
                "anonreq_prompt_security_events_total"
            ]

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
