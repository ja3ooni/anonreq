"""Prometheus metrics for the Enterprise Policy Engine.

Provides registration and increment helpers for policy decision,
denial, rate limit, and spend budget counters.
"""

from __future__ import annotations

import re
from typing import Any, cast

from prometheus_client import REGISTRY, Counter


def validate_label_value(value: str) -> str:
    """Validate label values to enforce bounded cardinality and prevent injection.

    Raises:
        ValueError: If value is too long or contains invalid characters.
    """
    if len(value) > 64:
        raise ValueError(f"Label value too long: {len(value)} chars (max 64)")
    if not re.match(r"^[a-zA-Z0-9_\-\.\*]+$", value):
        raise ValueError(f"Invalid label value format: '{value}'")
    return value


class PolicyMetrics:
    """Singleton-like container for Policy Engine Prometheus metrics."""

    _instance: PolicyMetrics | None = None

    def __new__(cls, registry: Any = REGISTRY) -> PolicyMetrics:
        # For idempotency and test flexibility, we allow creating with different registries
        # but cache the default REGISTRY instance.
        if registry is REGISTRY:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_metrics(registry)
            return cls._instance

        # Custom registry (usually for testing)
        inst = super().__new__(cls)
        inst._init_metrics(registry)
        return inst

    def _init_metrics(self, registry: Any) -> None:
        """Register the 4 policy engine counters idempotently on the registry."""
        self._registry = registry

        self.policy_decisions = self._get_or_register(
            "anonreq_policy_decisions_total",
            "Total policy decisions by tenant and action",
            ["tenant_id", "action"],
        )

        self.policy_denials = self._get_or_register(
            "anonreq_policy_denials_total",
            "Total policy denials by tenant and reason",
            ["tenant_id", "reason"],
        )

        self.rate_limit_hits = self._get_or_register(
            "anonreq_rate_limit_hits_total",
            "Rate limit hits by tenant and type",
            ["tenant_id", "limit_type"],
        )

        self.spend_limit_hits = self._get_or_register(
            "anonreq_spend_limit_hits_total",
            "Spend limit hits by tenant and budget type",
            ["tenant_id", "budget_type"],
        )

    def _get_or_register(self, name: str, doc: str, labels: list[str]) -> Counter:
        """idempotently get or register a Prometheus counter on the registry."""
        # Under standard registry or custom registry, if name is already collected, reuse it
        if hasattr(self._registry, "_names_to_collectors") and name in self._registry._names_to_collectors:  # noqa: E501
            return cast(Counter, self._registry._names_to_collectors[name])
        try:
            return Counter(name, doc, labels, registry=self._registry)
        except ValueError:
            # Fallback in case of race condition or collector lookup mismatch
            if hasattr(self._registry, "_names_to_collectors"):
                return cast(Counter, self._registry._names_to_collectors[name])
            raise

    def record_decision(self, tenant_id: str, action: str) -> None:
        """Increment policy decisions counter after validating labels."""
        t_val = validate_label_value(tenant_id)
        a_val = validate_label_value(action)
        self.policy_decisions.labels(tenant_id=t_val, action=a_val).inc()

    def record_denial(self, tenant_id: str, reason: str) -> None:
        """Increment policy denials counter after validating labels."""
        t_val = validate_label_value(tenant_id)
        r_val = validate_label_value(reason)
        self.policy_denials.labels(tenant_id=t_val, reason=r_val).inc()

    def record_rate_limit(self, tenant_id: str, limit_type: str) -> None:
        """Increment rate limit hits counter after validating labels."""
        t_val = validate_label_value(tenant_id)
        l_val = validate_label_value(limit_type)
        self.rate_limit_hits.labels(tenant_id=t_val, limit_type=l_val).inc()

    def record_spend_limit(self, tenant_id: str, budget_type: str) -> None:
        """Increment spend budget limit hits counter after validating labels."""
        t_val = validate_label_value(tenant_id)
        b_val = validate_label_value(budget_type)
        self.spend_limit_hits.labels(tenant_id=t_val, budget_type=b_val).inc()


def register_policy_metrics() -> PolicyMetrics:
    """Access the default registry policy metrics singleton."""
    return PolicyMetrics(REGISTRY)
