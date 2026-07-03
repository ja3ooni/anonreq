# Phase 16 Context: Performance and Scale

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Goal

Phase 16 prove horizontal scale, low latency, backpressure, load shedding, and overhead SLOs for API, streaming, DLP, and transparent proxy paths. The work is scoped as a production enterprise capability, not a prototype. It must preserve the core AnonReq guarantees: fail secure, no PII in logs, ephemeral mappings, streaming correctness, OpenAPI as source of truth, tenant isolation, and measurable security acceptance.

## Scope

In scope:
- Requirements: Req 1, Req 6, Req 20, Req 21, Req 22, Req 24, Req 48, Req 58, Req 60.
- Components: LoadShedder, BackpressureController, LatencyBudgetManager, StreamingRestorationProfiler, ValkeyConnectionPoolTuner, K6ScenarioSuite, CapacityModel.
- API surface: GET /v1/governance/status, GET /v1/admin/performance/profile, GET /metrics.
- Metrics: anonreq_processing_overhead_seconds, anonreq_stream_tail_buffer_flushes_total, anonreq_backpressure_rejections_total, anonreq_audio_pipeline_latency_seconds.
- Audit events: slo_breach_detected, load_shed_event, capacity_profile_generated, performance_gate_failed.

Out of scope:
- Relaxing ForwardingGuard requirements.
- Persisting token mappings, raw prompts, raw responses, raw transcript text, or original entity values.
- Adding unauthenticated administrative routes.
- Provider-specific shortcuts that bypass the internal OpenAI-compatible envelope.

## Business Value

This phase moves AnonReq from a privacy gateway toward an enterprise AI control plane. It gives security, compliance, platform, and SRE teams enforceable controls they can operate, audit, and explain during procurement, regulator review, and incident response.

## Dependencies

The phase assumes the Stage 1 gateway pipeline exists: request context, detection, tokenization, Valkey mapping, provider routing, restoration, audit logging, health checks, metrics, and property tests. It also depends on the master security model's rule that all forwarding flows through ForwardingGuard after a sanitized envelope is produced.

## Success Criteria

- All new behavior is tenant-scoped and role-protected.
- All new failures are fail-secure and produce controlled 4xx/5xx responses.
- Required metrics and audit events are emitted with metadata only.
- Tests listed in the phase test plan pass in CI.
- Documentation and OpenAPI updates are complete before implementation is marked done.
