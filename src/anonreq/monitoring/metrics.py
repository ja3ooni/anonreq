"""Prometheus metric definitions for the AnonReq gateway.

Provides all 8 metrics required by D-139:
- ``requests_total`` — Counter partitioned by endpoint, status_code, provider, classification, tenant_id
- ``detection_latency`` — Histogram of detection engine latency in milliseconds
- ``entities_detected`` — Counter partitioned by entity_type and locale
- ``unrestored_tokens`` — Counter partitioned by entity_type
- ``fail_secure_events`` — Counter partitioned by failure_type and tenant_id
- ``audit_failures`` — Counter (unlabeled)
- ``processing_overhead`` — Histogram of gateway processing overhead in milliseconds
- ``active_config_version`` — Gauge showing current custom rules config version

Per D-11, per-request counters carry tenant_id label.
Per D-12, bounded cardinality prevents metrics label explosion.
"""

from prometheus_client import Counter, Gauge, Histogram

# Per D-12: Bounded cardinality for tenant labels
_known_tenants: set[str] = set()
MAX_TENANTS: int = 100  # Default; overridden by Settings at runtime


def _tenant_label(tenant_id: str) -> str:
    """Return tenant_id or '_overflow' if cardinality limit exceeded per D-12."""
    if tenant_id in _known_tenants:
        return tenant_id
    if len(_known_tenants) >= MAX_TENANTS:
        return "_overflow"
    _known_tenants.add(tenant_id)
    return tenant_id


def set_max_tenants(max_tenants: int) -> None:
    """Configure the maximum unique tenant labels per D-12."""
    global MAX_TENANTS
    MAX_TENANTS = max_tenants


# Per D-11: requests_total now carries tenant_id label
# BREAKING: This is a breaking change for existing Prometheus scrapers
# that do not expect the tenant_id label.
requests_total = Counter(
    "anonreq_requests_total",
    "Total requests processed, partitioned by endpoint, status code, provider, "
    "classification, and tenant_id",
    labelnames=["tenant_id", "endpoint", "status_code", "provider", "classification"],
)

detection_latency = Histogram(
    "anonreq_detection_latency_ms",
    "Detection engine latency in milliseconds per TextNode",
    buckets=[5, 10, 25, 50, 100, 250, 500, 1000],
)

entities_detected = Counter(
    "anonreq_entities_detected_total",
    "Total entities detected, partitioned by entity type and locale",
    labelnames=["entity_type", "locale"],
)

unrestored_tokens = Counter(
    "anonreq_unrestored_tokens_total",
    "Residual unrestored tokens found post-restoration, partitioned by entity type",
    labelnames=["entity_type"],
)

# Per D-11: fail_secure_events now carries tenant_id label
fail_secure_events = Counter(
    "anonreq_fail_secure_events_total",
    "Fail-secure events triggered, partitioned by failure type and tenant_id",
    labelnames=["tenant_id", "failure_type"],
)

audit_failures = Counter(
    "anonreq_audit_failures_total",
    "Audit log write failures encountered",
)

processing_overhead = Histogram(
    "anonreq_processing_overhead_ms",
    "Gateway processing overhead in milliseconds (total minus provider round-trip time)",
    buckets=[5, 10, 25, 50, 100, 250, 500, 1000],
)

active_config_version = Gauge(
    "anonreq_active_config_version",
    "Current active custom rules config version (incremented on successful hot-reload)",
)

# Phase 17: Proxy metrics for TLS tunnel monitoring
proxy_connections_active = Gauge(
    "anonreq_proxy_connections_active",
    "Number of currently active TLS tunnels through the MITM proxy",
)

proxy_pinning_blocks = Counter(
    "anonreq_proxy_pinning_blocks_total",
    "Total number of certificate pinning blocks triggered",
)

# Phase 21 agent metric aliases live in anonreq.agent.metrics so their label
# contract matches the Phase 21 security acceptance table.
