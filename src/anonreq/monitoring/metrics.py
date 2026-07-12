"""Prometheus metric definitions for the AnonReq gateway.

Provides all 8 metrics required by D-139:
- ``requests_total`` — Counter partitioned by endpoint, status_code, provider, classification
- ``detection_latency`` — Histogram of detection engine latency in milliseconds
- ``entities_detected`` — Counter partitioned by entity_type and locale
- ``unrestored_tokens`` — Counter partitioned by entity_type
- ``fail_secure_events`` — Counter partitioned by failure_type
- ``audit_failures`` — Counter (unlabeled)
- ``processing_overhead`` — Histogram of gateway processing overhead in milliseconds
- ``active_config_version`` — Gauge showing current custom rules config version

All metrics use only low-cardinality labels per D-138. No per-request identifiers
(tenant_id, request_id, session_id) appear in any label. See AG-15.
"""

from prometheus_client import Counter, Gauge, Histogram

requests_total = Counter(
    "anonreq_requests_total",
    "Total requests processed, partitioned by endpoint, status code, provider, "
    "and classification action",
    labelnames=["endpoint", "status_code", "provider", "classification"],
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

fail_secure_events = Counter(
    "anonreq_fail_secure_events_total",
    "Fail-secure events triggered, partitioned by failure type",
    labelnames=["failure_type"],
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
