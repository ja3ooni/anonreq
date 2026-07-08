# Phase 20: AI SOC / SIEM Integration — Context

**Gathered:** 2026-06-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 20 delivers the AI SOC Integration output sink layer — a structured event forwarding pipeline that routes AI security events from the AnonReq Appliance to enterprise SIEM platforms. It is NOT a separate gateway or interception layer. Everything routes through the existing Phase 9 Content-Type Dispatcher pipeline. Phase 20 is an output sink layer that attaches to all security-relevant detection engines (Phases 10, 13, 12, 8, 17, 18) and forwards normalized events to configurable SIEM targets.

Event sources: firewall violations (Req 52), DLP actions (Req 49), shadow AI detections (Req 53), MNPI detections (Req 38), prompt security events (Req 36), classification blocks (Req 41), and governance actions (Phases 8/18).

</domain>

<decisions>
## Implementation Decisions

### Single Gateway Architecture
- **D-001:** NOT multiple gateways. Everything routes through Phase 9 Content-Type Dispatcher. Phase 20 is an output sink layer only.
- **D-002:** No separate SOC gateway process. SOC integration runs as a service within the Appliance process.

### Event Sources
- **D-003:** All firewall violations (Req 52), DLP actions (Req 49), shadow AI detections (Req 53), MNPI detections (Req 38), prompt security events (Req 36), classification blocks (Req 41), and governance actions.
- **D-004:** Events are consumed via an internal event bus (asyncio.Queue) — detection engines publish, SOC service consumes. Never block detection processing on SIEM delivery.

### SIEM Output Sinks
- **D-005:** Splunk HEC — `POST /services/collector/event` with `Authorization: Splunk {token}`, `sourcetype: anonreq:ai_security`
- **D-006:** IBM QRadar — syslog CEF format (ArcSight Common Event Format over TCP/UDP syslog)
- **D-007:** Microsoft Sentinel — Azure Monitor Data Collection Rule (DCR) API via HTTPS
- **D-008:** Elastic Security — Elasticsearch Bulk API (`POST /_bulk`) with API key auth
- **D-009:** Datadog — Datadog Logs API (`POST /v2/input/{api_key}`) via HTTPS
- **D-010:** Generic webhook — user-configurable URL, auth header, and payload template for custom SIEM integration

### Event Format
- **D-011:** Every forwarded event includes: `severity` (informational/low/medium/high/critical), `event_type`, `tenant_id`, `session_id`, `timestamp` (ISO 8601 UTC), `gateway_version`, `appliance_instance_id`, `mitre_technique_id`.
- **D-012:** No raw prompt content. Enforced at the event normalizer — source events are stripped of content fields before forwarding. Fail-secure: if content field detected in normalized event, the event is dropped and a `soc_strip_failure` audit event is emitted.

### MITRE Mapping
- **D-013:** Dedicated MITRE technique ID mapping config file (`config/mitre-mapping.yaml`) linking event types → MITRE ATT&CK for Enterprise / ATLAS technique IDs.
- **D-014:** MITRE mapping is applied at the event normalizer stage, before formatting.
- **D-015:** Mapping covers all security event types from Phases 10, 13, 12, 8, 17, 18.
- **D-016:** When no MITRE mapping exists for a given event_type, `mitre_technique_id` defaults to `"TEMP:UNMAPPED"` and a warning is logged.

### Buffer & Retry
- **D-017:** In-memory buffer with maximum 10,000 events per sink.
- **D-018:** Exponential backoff retry: initial 1s, multiplier 2, max 60s, jitter ±10%.
- **D-019:** LRU eviction when buffer is full — oldest events dropped first.
- **D-020:** Buffer overflow emits `event_type: soc_buffer_overflow` local audit entry.
- **D-021:** NEVER block request processing. Buffer/retry runs on a background asyncio task per sink.

### Health Monitoring
- **D-022:** `GET /v1/admin/soc/integration/status` — requires `security_officer` or `administrator` role.
- **D-023:** Response includes per-sink status: reachable/unreachable, last_successful_delivery_ts, buffer_size, last_error.
- **D-024:** Health is determined by periodic probe requests (configurable interval, default 60s per sink).

### Sink Configuration
- **D-025:** Sinks configured in `config/soc-sinks.yaml` — list of sink definitions with type, endpoint, auth, and per-sink settings.
- **D-026:** Sinks can be enabled/disabled individually. Disabled sinks are not started and not probed.
- **D-027:** Configuration is loaded at startup. Hot-reload is deferred to a future phase.

### Security
- **D-028:** Auth credentials for SIEM sinks stored in environment variables or a secrets file referenced by path (never in config YAML). YAML config references `$env:VAR_NAME` or `$file:/path/to/secret`.
- **D-029:** TLS verification enabled for all HTTPS-based sinks by default (configurable `tls_verify: false` for test environments).
- **D-030:** SOC endpoint itself is authenticated and authorized — `GET /v1/admin/soc/integration/status` requires security_officer or administrator.

### the Agent's Discretion
- CEF field mapping specifics for QRadar
- DCR rule name and stream name conventions for Sentinel
- Elasticsearch index naming convention for Elastic sink
- Webhook payload template schema
- Sink configuration YAML schema
- Probe request format (lightweight event or no-op ping)
- Retry jitter implementation details
- LRU eviction policy implementation (per-sink or global)
- MITRE technique ID mapping content

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` §Phase 20 — Goal and success criteria
- `req/requirements_v2.md` §Req 56 — AI SOC Integration
- `req/requirements_v2.md` §Req 34 — Post-Deployment Monitoring and Incident Reporting
- `req/requirements_v2.md` §Req 36 — Prompt Security and AI Firewall Baseline
- `.planning/phases/10-ai-security-firewall/10-CONTEXT.md` — Threat Detection (event source)
- `.planning/phases/13-ai-firewall-data-loss-prevention/13-CONTEXT.md` — DLP Engine (event source)
- `.planning/phases/12-data-classification-handling/12-CONTEXT.md` — Classification Engine (event source)
- `.planning/phases/17-universal-ai-traffic-gateway/17-CONTEXT.md` — Shadow AI Detection (event source)
- `.planning/phases/18-agent-tool-call-governance/18-CONTEXT.md` — Agent Governance (event source)
- `.planning/phases/08-Enterprise-Policy-Engine/08-CONTEXT.md` — PDP #2 governance actions (event source)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 5 AuditLogger — structured JSON event emission (pattern reusable for SOC events)
- Phase 9 Content-Type Dispatcher — single request routing (Phase 20 is an output sink, not a router)
- Phase 11 MetricsService — Prometheus counter patterns (reusable for SOC event counters)
- Phase 8 Policy YAML loader — config file loading pattern (reusable for soc-sinks.yaml, mitre-mapping.yaml)
- Phase 17 Appliance Service — appliance identity available for `appliance_instance_id` field

### Integration Points
- Event bus (asyncio.Queue) between detection engines and SOC event normalizer
- SOC normalizer subscribes to events from all security engines
- Per-sink background tasks consume from per-sink retry queues
- Health check probes use the same sink connections
- AuditLogger records soc events: soc_event_forwarded, soc_sink_unreachable, soc_buffer_overflow, soc_event_dropped, soc_strip_failure

</code_context>

<specifics>
## Specific Ideas

- Single gateway with output sinks reflects real SOC architecture: detection happens in the gateway, events fan out to multiple SIEMs
- In-memory buffer with LRU eviction is standard SIEM connector pattern (Splunk Universal Forwarder, Elastic Beat, etc.)
- No raw content in forwarded events is a deliberate overcorrection — even structured metadata might be sensitive, but the requirement specifically targets prompt content
- Generic webhook sink future-proofs against SIEM vendor lock-in
- Environment variable / file-based secrets for sink auth follows SOC integration best practices

</specifics>

<deferred>
## Deferred Ideas

- Hot-reload of sink configuration (Phase 20+)
- Per-sink event filtering (only forward events matching filter criteria per sink)
- SOC event replay from historical buffer (persistent buffer — Phase 25+)
- SIEM integration testing against live sandbox instances (limited to unit/integration mocks for now)
- Event prioritization (critical events bypass buffer)
- Automated SIEM rule deployment
- SOC dashboard within Admin Portal (Phase 14)

</deferred>

---

*Phase: 20-ai-soc-siem-integration*
*Context gathered: 2026-06-26*
