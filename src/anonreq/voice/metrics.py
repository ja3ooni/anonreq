from __future__ import annotations

from collections.abc import Callable
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, REGISTRY


def _collector(name: str, factory: Callable[[], Any]) -> Any:
    existing = getattr(REGISTRY, "_names_to_collectors", {}).get(name)
    if existing is not None:
        return existing
    return factory()


voice_streams_active = _collector(
    "anonreq_voice_streams_active",
    lambda: Gauge(
        "anonreq_voice_streams_active",
        "Active voice streams",
        labelnames=["connector_type", "tenant_id"],
    ),
)

voice_latency_ms = _collector(
    "anonreq_voice_latency_ms",
    lambda: Histogram(
        "anonreq_voice_latency_ms",
        "Voice pipeline latency",
        labelnames=["connector_type"],
        buckets=(10, 25, 50, 100, 150, 200, 300, 500),
    ),
)

voice_entities_detected_total = _collector(
    "anonreq_voice_entities_detected_total",
    lambda: Counter(
        "anonreq_voice_entities_detected_total",
        "Entities detected in voice streams",
        labelnames=["entity_type", "connector_type"],
    ),
)

voice_audio_sanitized_seconds_total = _collector(
    "anonreq_voice_audio_sanitized_seconds_total",
    lambda: Counter(
        "anonreq_voice_audio_sanitized_seconds_total",
        "Audio sanitized duration",
        labelnames=["method", "connector_type"],
    ),
)

voice_latency_exceeded_total = _collector(
    "anonreq_voice_latency_exceeded_total",
    lambda: Counter(
        "anonreq_voice_latency_exceeded_total",
        "Voice latency budget exceeded",
        labelnames=["connector_type"],
    ),
)
