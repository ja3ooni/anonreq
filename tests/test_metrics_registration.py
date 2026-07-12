from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import Response
from httpx import ASGITransport, AsyncClient
from prometheus_client import REGISTRY, generate_latest
from prometheus_client.metrics import Counter, Gauge, Histogram

from anonreq.agent import metrics as agent_metrics
from anonreq.firewall import metrics as firewall_metrics
from anonreq.proxy import metrics as proxy_metrics
from anonreq.voice import metrics as voice_metrics

EXPECTED_METRICS = {
    "anonreq_firewall_blocks_total": (Counter, ("detection_type", "tenant_id")),
    "anonreq_firewall_evaluation_duration_ms": (Histogram, ("decision",)),
    "anonreq_firewall_latency_budget_exceeded_total": (Counter, ()),
    "anonreq_agent_tool_calls_inspected_total": (Counter, ("action", "tenant_id")),
    "anonreq_agent_tool_results_sanitized_total": (Counter, ("entity_type", "tenant_id")),
    "anonreq_agent_governance_duration_ms": (Histogram, ("operation",)),
    "anonreq_voice_streams_active": (Gauge, ("connector_type", "tenant_id")),
    "anonreq_voice_latency_ms": (Histogram, ("connector_type",)),
    "anonreq_voice_entities_detected_total": (Counter, ("entity_type", "connector_type")),
    "anonreq_voice_audio_sanitized_seconds_total": (Counter, ("method", "connector_type")),
    "anonreq_voice_latency_exceeded_total": (Counter, ("connector_type",)),
    "anonreq_proxy_tls_intercepted_total": (Counter, ("domain", "tenant_id")),
    "anonreq_proxy_cert_pinning_detected_total": (Counter, ("domain", "action")),
    "anonreq_proxy_non_ai_blocked_total": (Counter, ("policy",)),
    "anonreq_fail_closed_total": (Counter, ("component", "failure_reason")),
}


def _collector(metric_name: str):
    return REGISTRY._names_to_collectors[metric_name]


def test_all_phase_21_metrics_registered_with_expected_types_and_labels():
    assert firewall_metrics.firewall_blocks_total is _collector("anonreq_firewall_blocks_total")
    assert agent_metrics.agent_tool_calls_inspected_total is _collector(
        "anonreq_agent_tool_calls_inspected_total"
    )
    assert voice_metrics.voice_streams_active is _collector("anonreq_voice_streams_active")
    assert proxy_metrics.fail_closed_total is _collector("anonreq_fail_closed_total")

    for metric_name, (expected_type, expected_labels) in EXPECTED_METRICS.items():
        collector = _collector(metric_name)
        assert isinstance(collector, expected_type)
        assert tuple(collector._labelnames) == expected_labels


def test_phase_21_metrics_increment_without_duplicate_registration_errors():
    firewall_metrics.firewall_blocks_total.labels(
        detection_type="prompt_injection", tenant_id="tenant_a"
    ).inc()
    firewall_metrics.firewall_evaluation_duration_ms.labels(decision="block").observe(12)
    firewall_metrics.firewall_latency_budget_exceeded_total.inc()
    agent_metrics.agent_tool_calls_inspected_total.labels(action="allow", tenant_id="tenant_a").inc()  # noqa: E501
    agent_metrics.agent_tool_results_sanitized_total.labels(
        entity_type="email", tenant_id="tenant_a"
    ).inc()
    agent_metrics.agent_governance_duration_ms.labels(operation="result_sanitize").observe(9)
    voice_metrics.voice_streams_active.labels(connector_type="sip", tenant_id="tenant_a").inc()
    voice_metrics.voice_latency_ms.labels(connector_type="sip").observe(50)
    voice_metrics.voice_entities_detected_total.labels(
        entity_type="email", connector_type="sip"
    ).inc()
    voice_metrics.voice_audio_sanitized_seconds_total.labels(
        method="mute", connector_type="sip"
    ).inc(0.25)
    voice_metrics.voice_latency_exceeded_total.labels(connector_type="sip").inc()
    proxy_metrics.proxy_tls_intercepted_total.labels(
        domain="api.openai.com", tenant_id="tenant_a"
    ).inc()
    proxy_metrics.proxy_cert_pinning_detected_total.labels(
        domain="api.openai.com", action="block"
    ).inc()
    proxy_metrics.proxy_non_ai_blocked_total.labels(policy="fail-closed").inc()
    proxy_metrics.fail_closed_total.labels(
        component="transparent_proxy", failure_reason="interception_error"
    ).inc()

    body = generate_latest(REGISTRY).decode("utf-8")
    for metric_name in EXPECTED_METRICS:
        assert metric_name in body


async def test_metrics_endpoint_exposes_phase_21_metrics():
    app = FastAPI()

    @app.get("/metrics")
    async def metrics():
        return Response(generate_latest(REGISTRY), media_type="text/plain; charset=utf-8")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/metrics")

    assert response.status_code == 200
    body = response.text
    for metric_name in EXPECTED_METRICS:
        assert metric_name in body
