from __future__ import annotations

from collections.abc import Callable
from typing import Any

from prometheus_client import Counter, REGISTRY


def _collector(name: str, factory: Callable[[], Any]) -> Any:
    existing = getattr(REGISTRY, "_names_to_collectors", {}).get(name)
    if existing is not None:
        return existing
    return factory()


proxy_tls_intercepted_total = _collector(
    "anonreq_proxy_tls_intercepted_total",
    lambda: Counter(
        "anonreq_proxy_tls_intercepted_total",
        "TLS intercept events",
        labelnames=["domain", "tenant_id"],
    ),
)

proxy_cert_pinning_detected_total = _collector(
    "anonreq_proxy_cert_pinning_detected_total",
    lambda: Counter(
        "anonreq_proxy_cert_pinning_detected_total",
        "Cert pinning detected",
        labelnames=["domain", "action"],
    ),
)

proxy_non_ai_blocked_total = _collector(
    "anonreq_proxy_non_ai_blocked_total",
    lambda: Counter(
        "anonreq_proxy_non_ai_blocked_total",
        "Non-AI traffic blocked",
        labelnames=["policy"],
    ),
)

fail_closed_total = _collector(
    "anonreq_fail_closed_total",
    lambda: Counter(
        "anonreq_fail_closed_total",
        "Fail-closed events",
        labelnames=["component", "failure_reason"],
    ),
)
