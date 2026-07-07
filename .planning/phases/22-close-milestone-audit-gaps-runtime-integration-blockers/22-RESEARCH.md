# Phase 22: Close Milestone Audit Gaps - Runtime Integration Blockers Research

**Researched:** 2026-07-07  
**Domain:** Python FastAPI runtime integration for AnonReq appliance/security modules  
**Confidence:** HIGH for codebase wiring findings; MEDIUM for plan sequencing

## User Constraints (from CONTEXT.md)

### Locked Decisions
No `## Decisions` section exists in `22-CONTEXT.md`; the phase goal and required closure areas are treated as fixed scope. [VERIFIED: `.planning/phases/22-close-milestone-audit-gaps-runtime-integration-blockers/22-CONTEXT.md`]

### the agent's Discretion
No `## the agent's Discretion` section exists in `22-CONTEXT.md`; the practical plan breakdown is research recommendation. [VERIFIED: `.planning/phases/22-close-milestone-audit-gaps-runtime-integration-blockers/22-CONTEXT.md`]

### Deferred Ideas (OUT OF SCOPE)
No `## Deferred Ideas` section exists in `22-CONTEXT.md`; unrelated rewrites, new product features, and broad planning reconciliation beyond the named audit blockers are out of scope for the runtime closure research. [VERIFIED: `.planning/phases/22-close-milestone-audit-gaps-runtime-integration-blockers/22-CONTEXT.md`]

## Project Constraints (from AGENTS.md)

- AnonReq is alpha but not greenfield; source files and tests are more authoritative than stale planning prose. [VERIFIED: `AGENTS.md`]
- Raw PII must never cross the network boundary. [VERIFIED: `AGENTS.md`]
- Fail-secure/fail-closed behavior must block forwarding on ambiguity, component failure, policy uncertainty, detection failure, cache failure, timeout, TLS/proxy failure, or unsupported content paths. [VERIFIED: `AGENTS.md`]
- Logs, audit, SOC, metrics, and telemetry must be metadata-only and must not contain raw request bodies, raw detected values, raw tool results, or raw encoded exfiltration content. [VERIFIED: `AGENTS.md`]
- Token mappings must remain session-scoped, TTL-bound, and non-durable. [VERIFIED: `AGENTS.md`]
- `/v1/chat/completions` and `/v1/models` must remain OpenAI-compatible. [VERIFIED: `AGENTS.md`]
- Classification must happen before anonymization and external forwarding. [VERIFIED: `AGENTS.md`]
- Tenant-scoped policy, usage, spend, audit, cache, metrics labels, and governance records must not bleed across tenants. [VERIFIED: `AGENTS.md`]
- Appliance proxy, TLS/MITM, endpoint, agent, voice, and SOC paths must follow the same fail-secure and metadata-only rules as the core API. [VERIFIED: `AGENTS.md`]
- Behavior changes should add focused tests near the affected module and preserve property coverage for fail-secure, no-PII telemetry, streaming restoration, tenant isolation, and governance invariants. [VERIFIED: `AGENTS.md`]

## Summary

Phase 22 should be planned as a runtime wiring closure phase, not a redesign. The six audit blockers all point to existing modules that are present but not connected to the live FastAPI or proxy execution paths: proxy dispatch receives `app.state.pipeline` even though the proxy expects `dispatch(...)` or a request callable, DLP exists in `src/anonreq/services/pipeline.py` but the real chat route uses `PipelineManager`, `ContentTypeMiddleware` exists but is not installed, SOC normalizer and sink router are both initialized but not bridged, discovery inventory router exists but is not included in `create_app()`, and agent/tool governance has usable governance modules plus stale tests for missing `anonreq.agent.policy` / `anonreq.middleware.agent`. [VERIFIED: codebase grep]

The primary planning principle is to add narrow adapters and integration stages at existing seams. Use the current `PipelineManager`/`PipelineStage` route path, `create_app()` lifespan/router setup, `SOCNormalizer.register_sink_callback(...)`, `SinkRouter.fan_out(...)`, and existing governance extractors/evaluators instead of building parallel pipelines or duplicate agent policy stacks. [VERIFIED: codebase grep]

**Primary recommendation:** Plan six small closure waves plus a final audit-verification wave; each wave should add one runtime connection and one focused integration test proving the audit blocker is closed. [VERIFIED: milestone audit]

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| APPL-01/APPL-02/APPL-03/APPL-06 | Appliance reverse/transparent proxy traffic must route through governed/anonymizing gateway paths. | Proxy classes already route to a dispatcher, but `main.py` passes `app.state.pipeline`, which has `run(ctx)` but no `dispatch(...)`; add an adapter. [VERIFIED: `src/anonreq/main.py`, `src/anonreq/proxy/reverse_proxy.py`, `src/anonreq/proxy/transparent_proxy.py`] |
| APPL-DLP-01 to APPL-DLP-05 | Runtime DLP category/action/enforcement/audit/metrics must run in the real chat path. | `DLPEngine`, `PipelineService`, DLP models, metrics, and tests exist, but `build_pipeline()` does not register DLP stages. [VERIFIED: `src/anonreq/services/pipeline.py`, `src/anonreq/routing/chat.py`, `tests/test_dlp_pipeline.py`] |
| MULTI-05/APPL-CDP-01 | Unsupported content types must return HTTP 415 before forwarding. | `ContentTypeMiddleware` returns 415 for unknown types, but `create_app()` does not add it. [VERIFIED: `src/anonreq/middleware/content_type.py`, `src/anonreq/main.py`, `tests/multimodal/test_dispatcher.py`] |
| APPL-SOC-01 to APPL-SOC-09 | Normalized SOC events must fan out to configured SIEM sinks and expose sink health. | Normalizer and sink router exist and are started, but no callback registration connects them. [VERIFIED: `src/anonreq/soc/normalizer.py`, `src/anonreq/soc/router.py`, `src/anonreq/main.py`] |
| APPL-DISC-04 | Discovery inventory admin API must be reachable in the real app. | `discovery.admin_router.router` exists, but `main.py` does not include it and does not initialize `inventory_service`. [VERIFIED: `src/anonreq/discovery/admin_router.py`, `src/anonreq/main.py`] |
| APPL-AGENT-01/APPL-AGENT-02/APPL-AGENT-05/APPL-AGENT-06 | Agent/tool governance must be invoked from runtime or requirement status corrected. | `PDPToolEvaluator`, `ToolExtractor`, `ToolAuditEvent`, `ToolCallInspector`, and tests exist; stale `tests/test_agent_policy.py` imports missing modules. [VERIFIED: codebase grep] |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Proxy anonymization dispatch | API / Backend | Appliance proxy listener | Proxy receives bytes, but anonymization requires constructing a `ProcessingContext` and running gateway pipeline semantics before upstream forwarding. [VERIFIED: codebase grep] |
| DLP runtime enforcement | API / Backend | Policy/Governance service layer | Enforcement must occur before provider forwarding and after response generation for outbound suppression. [VERIFIED: `src/anonreq/services/pipeline.py`, `src/anonreq/routing/chat.py`] |
| Multimodal content-type enforcement | API / Backend middleware | Browser / Client none | HTTP 415 must be emitted before route/provider work. [VERIFIED: `src/anonreq/middleware/content_type.py`] |
| SOC event fan-out | API / Backend background service | External SIEM sinks | Normalizer consumes internal events and routes normalized metadata to sinks; sinks are external dependencies. [VERIFIED: `src/anonreq/soc/normalizer.py`, `src/anonreq/soc/router.py`] |
| Discovery inventory admin API | API / Backend | In-memory/service inventory | Admin router exposes inventory service state and CSV/JSON export. [VERIFIED: `src/anonreq/discovery/admin_router.py`] |
| Agent/tool governance | API / Backend pipeline stage | Governance service layer | Tool calls are part of chat/MCP request payloads and must be evaluated before provider/tool execution. [VERIFIED: `src/anonreq/governance/pdp_tool_evaluator.py`, `src/anonreq/governance/tool_extractor.py`] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | `>=3.12` project target | Runtime language | Project package declares Python 3.12 support. [VERIFIED: `pyproject.toml`] |
| FastAPI | `>=0.138.0`, locked `0.138.2` | HTTP app, routers, middleware | Current app is FastAPI and all blockers are app/runtime wiring. [VERIFIED: `pyproject.toml`, `uv.lock`, `src/anonreq/main.py`] |
| Pydantic Settings | `>=2.14.2`, locked `2.14.2` | Settings/config | Existing configuration uses project settings and YAML loaders. [VERIFIED: `pyproject.toml`, `uv.lock`] |
| httpx | `>=0.28.1`, locked `0.28.1` | Provider and sink HTTP clients/tests | Provider stage and SIEM sinks use async HTTP behavior. [VERIFIED: `pyproject.toml`, `uv.lock`, `src/anonreq/pipeline/provider.py`] |
| prometheus-client | `>=0.25.0` | Metrics | DLP/SOC/proxy metrics use Prometheus counters. [VERIFIED: `pyproject.toml`, codebase grep] |
| pytest / pytest-asyncio / Hypothesis | `pytest>=9.0`, locked `9.1.1`; `pytest-asyncio>=1.4.0`; `hypothesis>=6.155.0` | Unit, integration, property tests | Existing test suite is pytest with asyncio auto mode and property tests. [VERIFIED: `pyproject.toml`, `uv.lock`] |

### Supporting

| Library/Module | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| `anonreq.pipeline.manager.PipelineManager` | internal | Existing sequential fail-secure pipeline | Use for chat route integration stages and proxy adapter target. [VERIFIED: codebase grep] |
| `anonreq.services.dlp_engine.DLPEngine` | internal | DLP inspection and exfiltration detection | Use for inbound/outbound DLP stages; do not bypass with ad hoc regex. [VERIFIED: codebase grep] |
| `anonreq.middleware.content_type.ContentTypeMiddleware` | internal | HTTP 415 unsupported content-type gate | Install in `create_app()` with a real `ContentTypeDispatcher`. [VERIFIED: codebase grep] |
| `anonreq.soc.normalizer.SOCNormalizer` + `anonreq.soc.router.SinkRouter` | internal | Metadata normalization and SIEM fan-out | Register sink router as a normalizer callback during lifespan. [VERIFIED: codebase grep] |
| `anonreq.governance.PDPToolEvaluator` + `ToolExtractor` | internal | Tool permission/runtime governance | Add runtime stage or correct requirements; avoid missing `anonreq.agent.policy` stack. [VERIFIED: codebase grep] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pipeline adapter for proxy dispatch | Modify proxy classes to know `PipelineManager` internals | Higher coupling and larger blast radius; adapter keeps proxy contract stable. [ASSUMED] |
| Add DLP stages to `PipelineManager` | Route chat through `services.PipelineService` | `PipelineService` has stub methods for core stages, while `PipelineManager` is the live chat path. [VERIFIED: `src/anonreq/services/pipeline.py`, `src/anonreq/routing/chat.py`] |
| Use stale `tests/test_agent_policy.py` modules | Use current `governance` and `agent` modules | Stale tests import missing modules; current modules already cover PDP/tool inspection/audit pieces. [VERIFIED: codebase grep] |

**Installation:** No new package installation is recommended for this phase. [VERIFIED: codebase grep]

## Package Legitimacy Audit

No external packages should be installed for this phase. The planner should only reuse existing project dependencies and internal modules. [VERIFIED: `pyproject.toml`]

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| None | — | — | — | — | OK | No install |

**Packages removed due to [SLOP] verdict:** none  
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```text
FastAPI HTTP request or Appliance proxy bytes
        |
        v
Content-Type middleware gate ---- unknown/unsupported ----> HTTP 415, no forwarding
        |
        v
Request/Proxy adapter builds ProcessingContext
        |
        v
Classification -> Locale -> Detection -> Sensitivity -> DLP inbound -> PDP/PEP/tool governance
        |                                                         |
        | block/quarantine/approval required                      v
        +----------------------------------------------------> 4xx/451/202, no provider
        |
        v
Tokenization -> ForwardingGuard -> Provider -> Restoration -> DLP outbound -> Cleanup
        |                                        |
        v                                        v
SOC raw metadata events -> SOCNormalizer -> SinkRouter.fan_out -> Splunk/QRadar/Sentinel/Elastic/Datadog/Webhook
```

### Recommended Project Structure

```text
src/anonreq/
├── pipeline/          # Add narrow PipelineStage classes for DLP/tool governance if needed
├── proxy/             # Add proxy-to-chat/pipeline dispatcher adapter if needed
├── middleware/        # Install existing ContentTypeMiddleware from main.py
├── soc/               # Wire existing normalizer callback to existing SinkRouter
├── discovery/         # Include existing admin router and initialize inventory service
└── governance/        # Reuse PDPToolEvaluator, ToolExtractor, and audit emitter
tests/
├── integration/       # Add create_app/chat-route wiring tests
├── test_proxy_*.py    # Extend proxy adapter tests
├── test_dlp_*.py      # Add live chat route DLP tests
└── test_soc_*.py      # Add normalizer-to-sink fan-out test
```

### Pattern 1: Adapter at Contract Mismatch

**What:** Add a small object exposing `dispatch(content_type, body, ctx)` for proxy classes and translating OpenAI-compatible JSON bytes into the existing chat/pipeline processing contract. [VERIFIED: `src/anonreq/proxy/reverse_proxy.py`, `src/anonreq/proxy/transparent_proxy.py`]

**When to use:** Use when a caller has byte-level proxy requests but the target system expects `ProcessingContext`/pipeline execution. [VERIFIED: codebase grep]

**Example:**

```python
# Source: current proxy contract in src/anonreq/proxy/reverse_proxy.py and transparent_proxy.py
if hasattr(self.content_dispatcher, "dispatch"):
    result = await self.content_dispatcher.dispatch(content_type, request.body, ctx={"path": request.path})
```

### Pattern 2: PipelineStage Integration

**What:** Runtime enforcement belongs as explicit `PipelineStage` objects in `build_pre_provider_pipeline()` or `build_pipeline()`, not as a separate unused `PipelineService`. [VERIFIED: `src/anonreq/routing/chat.py`, `src/anonreq/pipeline/manager.py`, `src/anonreq/services/pipeline.py`]

**When to use:** Use for DLP inbound, DLP outbound, and tool governance so fail-secure errors stop later stages before provider forwarding or response delivery. [VERIFIED: codebase grep]

### Pattern 3: Lifespan Bridge

**What:** When lifespan initializes two long-lived services, register the producing side with the consuming side in the same try block or immediately after both exist. [VERIFIED: `src/anonreq/main.py`]

**When to use:** Use for `SOCNormalizer.register_sink_callback("sink_router", sink_router.fan_out)` after sink router creation. [VERIFIED: `src/anonreq/soc/normalizer.py`, `src/anonreq/soc/router.py`]

### Anti-Patterns to Avoid

- **Parallel pipeline rewrite:** Do not switch chat to `PipelineService`; its core stage methods are stubs. [VERIFIED: `src/anonreq/services/pipeline.py`]
- **Duplicate agent governance stack:** Do not create `anonreq.agent.policy` solely to satisfy stale tests; current governance modules already implement evaluator/extractor/audit patterns. [VERIFIED: codebase grep]
- **Permissive fallback on missing security component:** Do not silently allow traffic when DLP/tool governance/content-type enforcement setup fails in modes where requirements claim enforcement. [VERIFIED: `AGENTS.md`]
- **Raw event forwarding:** Do not fan out SOC events before `SOCNormalizer` strips raw content fields. [VERIFIED: `src/anonreq/soc/normalizer.py`]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Proxy anonymization | A second chat parser/provider client inside proxy classes | Adapter to existing `PipelineManager` / chat pipeline | Existing route already handles detection, tokenization, forwarding, restoration, cleanup. [VERIFIED: codebase grep] |
| DLP category/action logic | New regex/action engine | `DLPEngine`, `DLPResult`, `PipelineBlockedError`, `OutboundDLPError` | Existing DLP tests cover action ordering and outbound suppression. [VERIFIED: `tests/test_dlp_pipeline.py`] |
| Content type policy | New middleware | `ContentTypeMiddleware` + `ContentTypeDispatcher` | Existing middleware already returns structured HTTP 415. [VERIFIED: `src/anonreq/middleware/content_type.py`] |
| SIEM delivery | Direct sink calls from producers | `SOCNormalizer` -> `SinkRouter.fan_out` | Normalizer strips raw content and enriches MITRE metadata first. [VERIFIED: `src/anonreq/soc/normalizer.py`, `src/anonreq/soc/router.py`] |
| Tool policy | New missing `anonreq.agent.policy` API | `PDPToolEvaluator`, `ToolExtractor`, `ToolAuditEvent`, `ToolCallInspector` | Current modules and property tests exist; stale tests should be retired or rewritten. [VERIFIED: codebase grep] |

**Key insight:** The risky work is not algorithm design; it is proving existing security modules are actually in the runtime path before provider forwarding, external fan-out, or admin exposure. [VERIFIED: milestone audit]

## Existing Modules and Tests to Reuse

| Closure Area | Modules to Reuse | Tests to Reuse/Extend |
|--------------|------------------|-----------------------|
| Proxy anonymization | `proxy.reverse_proxy`, `proxy.transparent_proxy`, `routing.chat.build_pipeline`, `pipeline.manager`, `models.processing_context` | `tests/test_proxy_topology.py`, `tests/test_firewall_pipeline.py`, add adapter tests proving no raw body echo and sanitized provider body. [VERIFIED: codebase grep] |
| DLP runtime wiring | `services.dlp_engine`, `services.pipeline` logic as reference, `models.dlp`, `exceptions.PipelineBlockedError`, `exceptions.OutboundDLPError` | `tests/test_dlp_pipeline.py`, `tests/test_dlp_properties.py`, `tests/test_dlp_audit.py`, add chat route integration tests. [VERIFIED: codebase grep] |
| Multimodal middleware | `middleware.content_type`, `multimodal.dispatcher`, `multimodal.json_analyzer`, `multimodal.multipart_analyzer` | `tests/multimodal/test_dispatcher.py`, `tests/test_dispatcher_backward_compat.py`, add `create_app()` middleware installation test. [VERIFIED: codebase grep] |
| SOC fan-out | `soc.normalizer`, `soc.router`, `soc.sink_factory`, `soc.health`, `soc.api` | `tests/test_soc_normalizer.py`, `tests/test_soc_sink_factory.py`, `tests/test_soc_api.py`, add normalizer-to-router callback test. [VERIFIED: codebase grep] |
| Discovery admin | `discovery.admin_router`, `discovery.inventory`, `discovery.cost_attribution` | `tests/discovery/test_discovery_inventory.py`, add app route registration test for `/v1/admin/discovery/inventory`. [VERIFIED: codebase grep] |
| Agent/tool governance | `governance.pdp_tool_evaluator`, `governance.tool_extractor`, `governance.tool_policy_parser`, `governance.audit`, `agent.tool_inspector`, `agent.result_sanitizer` | `tests/test_pdp_tool_evaluator.py`, `tests/property/test_tool_governance.py`, `tests/test_governance_audit.py`, `tests/test_agent_tool_inspector.py`; replace or xfail stale `tests/test_agent_policy.py`. [VERIFIED: codebase grep] |

## Recommended Phase Plan Breakdown

### Wave 0 - Guardrails and Regression Harness

Add targeted failing tests first for each runtime blocker without changing behavior. [ASSUMED]

Dependencies: none. [ASSUMED]

Deliverables:
- App wiring tests proving `ContentTypeMiddleware`, discovery router, SOC callback, and DLP/tool stages are present in the real app or pipeline. [VERIFIED: codebase grep]
- Proxy adapter tests proving reverse/transparent proxy no longer echo raw bodies or status-only `"routed"` responses for AI chat payloads. [VERIFIED: `src/anonreq/proxy/transparent_proxy.py`, `src/anonreq/proxy/reverse_proxy.py`]

### Wave 1 - Low-Risk App Installation Closures

Wire `ContentTypeMiddleware` and discovery inventory admin router in `create_app()`, and initialize an `inventory_service` compatible with `discovery.admin_router`. [VERIFIED: codebase grep]

Dependencies: Wave 0 tests. [ASSUMED]

Why first: These are route/middleware registration gaps with small blast radius. [ASSUMED]

### Wave 2 - SOC Normalizer to Sink Fan-Out

After sink router creation, register `sink_router.fan_out` as a callback on `app.state.soc_normalizer`; keep sink failures isolated inside `SinkRouter.fan_out`. [VERIFIED: `src/anonreq/soc/normalizer.py`, `src/anonreq/soc/router.py`, `src/anonreq/main.py`]

Dependencies: Wave 0 tests. [ASSUMED]

### Wave 3 - DLP in Real Chat Pipeline

Add explicit inbound and outbound DLP `PipelineStage` classes or equivalent live `PipelineManager` integration. Inbound DLP must run before provider forwarding; outbound DLP must run before response delivery. [VERIFIED: `src/anonreq/services/pipeline.py`, `src/anonreq/routing/chat.py`]

Dependencies: Wave 0 tests; preferably after Wave 1 so content-type rejection is already before pipeline. [ASSUMED]

### Wave 4 - Agent/Tool Governance Runtime Decision

Prefer a runtime `PipelineStage` that uses `ToolExtractor` and `PDPToolEvaluator` against `ProcessingContext.original_request`, emits metadata-only `ToolAuditEvent`s, blocks denied tools, and returns/suspends approval-required tools consistently with existing approval manager behavior. If this cannot be made requirement-correct in scope, update requirement/planning status rather than claiming runtime enforcement. [VERIFIED: codebase grep]

Dependencies: Wave 3 if tool governance should see DLP/classification context; otherwise can run in parallel after Wave 0. [ASSUMED]

### Wave 5 - Appliance Proxy Dispatch Adapter

Create a dispatcher adapter that accepts proxy `dispatch(content_type, body, ctx)` calls, rejects unsupported/non-JSON content fail-closed, builds a chat-compatible processing path, and never returns raw request bodies. [VERIFIED: codebase grep]

Dependencies: Wave 3 for DLP/tool governance if proxy traffic must share the same runtime controls; Wave 1 for content-type consistency. [ASSUMED]

### Wave 6 - Evidence and Audit Gate

Run closure commands, update only allowed phase verification artifacts if execution scope permits, and re-run milestone audit. [VERIFIED: `.planning/v1.0-MILESTONE-AUDIT.md`]

Dependencies: Waves 1-5. [ASSUMED]

## Common Pitfalls

### Pitfall 1: Passing `PipelineManager` Directly to Proxy

**What goes wrong:** Proxy classes call `dispatch(...)` or callable request objects, but `PipelineManager` exposes `run(ctx)`, so the proxy can fall through to raw/status behavior or invalid stringification. [VERIFIED: `src/anonreq/proxy/reverse_proxy.py`, `src/anonreq/proxy/transparent_proxy.py`, `src/anonreq/main.py`]  
**Why it happens:** `main.py` assigns `dispatcher = app.state.pipeline` before creating deployment proxies. [VERIFIED: `src/anonreq/main.py`]  
**How to avoid:** Add a contract adapter and test the proxy with an AI chat body containing detectable PII. [ASSUMED]  
**Warning signs:** Response body equals the input body, `b"{'status': 'routed'}"`, or raw PII appears in outbound provider mock. [VERIFIED: codebase grep]

### Pitfall 2: Testing `PipelineService` Instead of the Live Route

**What goes wrong:** DLP tests pass while `/v1/chat/completions` still never invokes DLP. [VERIFIED: `tests/test_dlp_pipeline.py`, `src/anonreq/routing/chat.py`]  
**Why it happens:** `PipelineService` is not used by `chat_completions`; the route runs `request.app.state.pipeline`. [VERIFIED: codebase grep]  
**How to avoid:** Add tests that post through the route or run the actual `PipelineManager` stages built by `build_pipeline()`. [ASSUMED]

### Pitfall 3: SOC Sink Health Is Mistaken for SOC Delivery

**What goes wrong:** `/v1/admin/soc/integration/status` can report sinks while no normalized event is delivered. [VERIFIED: `src/anonreq/main.py`, `src/anonreq/soc/api.py`]  
**Why it happens:** Sink router is stored on app state but not registered with normalizer callbacks. [VERIFIED: codebase grep]  
**How to avoid:** Test `normalizer.publish_raw(...)` through `_consume_one()` or the background loop and assert a fake sink receives a `NormalizedEvent`. [VERIFIED: `src/anonreq/soc/normalizer.py`]

### Pitfall 4: Stale Agent Tests Drive a Duplicate Implementation

**What goes wrong:** Planner creates new `anonreq.agent.policy`, `anonreq.agent.registry`, or `anonreq.middleware.agent` modules while current governance modules already exist. [VERIFIED: `tests/test_agent_policy.py`, codebase grep]  
**Why it happens:** `tests/test_agent_policy.py` imports missing modules. [VERIFIED: codebase grep]  
**How to avoid:** Decide whether APPL-AGENT runtime closure uses current governance modules or requirement status is corrected; do not satisfy stale imports by duplicating policy engines. [ASSUMED]

## Code Examples

### SOC Fan-Out Callback Pattern

```python
# Source: existing APIs in src/anonreq/soc/normalizer.py and src/anonreq/soc/router.py
soc_normalizer.register_sink_callback("sink_router", sink_router.fan_out)
```

### Existing Middleware Contract

```python
# Source: src/anonreq/middleware/content_type.py
if result.action == "ROUTE_LOCAL" and result.content_type == ContentType.UNKNOWN:
    await send({"type": "http.response.start", "status": 415, "headers": [...]})
```

### Existing Pipeline Abort Pattern

```python
# Source: src/anonreq/pipeline/manager.py
try:
    ctx = await stage.execute(ctx)
except Exception as exc:
    ctx.fail_secure(exc)
    break
```

## State of the Art

| Old Approach | Current Required Approach | When Changed | Impact |
|--------------|---------------------------|--------------|--------|
| Component-only tests for appliance modules | Runtime integration tests through `create_app()`, proxy objects, and `/v1/chat/completions` | Phase 22 audit, 2026-07-07 | Prevents completed modules from remaining unreachable. [VERIFIED: milestone audit] |
| Proxy receives arbitrary dispatcher object | Proxy receives a contract-compatible anonymization dispatcher | Phase 22 audit, 2026-07-07 | Prevents raw body echo/status-only responses. [VERIFIED: milestone audit] |
| SOC normalizer and sinks started independently | Normalized events are registered to fan out to sink router | Phase 22 audit, 2026-07-07 | Makes APPL-SOC delivery requirement testable. [VERIFIED: milestone audit] |

**Deprecated/outdated:**
- `tests/test_agent_policy.py` appears stale because it imports modules not present in `src/anonreq`. [VERIFIED: codebase grep]
- Planning status that marks unchecked runtime blockers complete should not be trusted until route/proxy integration tests pass. [VERIFIED: `.planning/v1.0-MILESTONE-AUDIT.md`, `AGENTS.md`]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Proxy dispatch should be solved by an adapter rather than rewriting proxy classes. | Alternatives, Plan Wave 5 | Proxy implementation tasks may be structured differently, but tests should still enforce no raw forwarding. |
| A2 | Wave order should close low-risk app registrations before DLP/tool/proxy behavior. | Plan Breakdown | Planner may reorder if dependency analysis finds hidden coupling. |
| A3 | Agent/tool governance should reuse current governance modules rather than recreate missing stale-test APIs. | Plan Wave 4 | If product explicitly needs the stale API surface, a compatibility layer may be required. |

## Open Questions

1. **Should `proxy_only` deployment mode remain intentionally non-anonymizing?**  
   What we know: `ProxyMode.PROXY_ONLY` is documented and tested as skipping detection/anonymization. [VERIFIED: `tests/test_proxy_modes.py`, codebase grep]  
   What's unclear: Phase 22 audit targets reverse/transparent appliance paths, not necessarily `PROXY_ONLY`. [VERIFIED: milestone audit]  
   Recommendation: Scope proxy anonymization closure to reverse/transparent/full modes and preserve explicit `PROXY_ONLY` semantics unless requirements are updated. [ASSUMED]

2. **What should approval-required tool governance return on the chat route?**  
   What we know: `PDPToolEvaluator` sets `context.requires_approval = True`; `ApprovalManager` exists on app state. [VERIFIED: `src/anonreq/governance/pdp_tool_evaluator.py`, `src/anonreq/main.py`]  
   What's unclear: The runtime chat response shape for suspended tool execution is not defined in the inspected route. [VERIFIED: `src/anonreq/routing/chat.py`]  
   Recommendation: Planner should add a small design checkpoint before implementing APPL-AGENT-05 response semantics. [ASSUMED]

3. **Should discovery inventory be seeded from live `FlowAnalyzer`/allowlist state at startup?**  
   What we know: Admin router expects `app.state.inventory_service`; lifespan currently initializes flow analyzer/allowlist but not inventory service. [VERIFIED: codebase grep]  
   What's unclear: Whether empty inventory with manual POST support is acceptable for APPL-DISC-04 closure. [ASSUMED]  
   Recommendation: Initialize `InventoryService` and add route registration tests first; seed/merge behavior can be a follow-up if audit requires non-empty inventory. [ASSUMED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | Running focused pytest commands | yes | `0.11.0` | Use project venv/python if uv unavailable. [VERIFIED: shell probe] |
| Python runtime | Tests and app imports | yes | system `3.14.6`; project target `>=3.12` | Use `uv run` to respect locked environment. [VERIFIED: shell probe, `pyproject.toml`] |
| FastAPI/httpx/pytest dependencies | Runtime integration tests | yes in `uv.lock` | see Standard Stack | No new install recommended. [VERIFIED: `uv.lock`] |
| Redis/Valkey/Presidio external services | Full `create_app()` lifespan / end-to-end app tests | not probed in this research | — | Prefer unit/integration tests with app-state fakes or existing fixtures unless full stack verification is required. [ASSUMED] |

**Missing dependencies with no fallback:** none identified for research and planning. [VERIFIED: shell probe]  
**Missing dependencies with fallback:** external Redis/Valkey/Presidio may be avoided in focused tests using existing fakes/mocks. [ASSUMED]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio and Hypothesis. [VERIFIED: `pyproject.toml`] |
| Config file | `pyproject.toml` with `asyncio_mode = "auto"` and `testpaths = ["tests"]`. [VERIFIED: `pyproject.toml`] |
| Quick run command | `uv run pytest <focused-test-file> -q` [VERIFIED: `pyproject.toml`] |
| Full suite command | `uv run pytest` [VERIFIED: `AGENTS.md`] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| APPL-01/02/03/06 | Reverse/transparent proxy uses anonymization-capable dispatcher and does not return raw request body. | unit/integration | `uv run pytest tests/test_proxy_topology.py tests/test_proxy_integration.py -q` | Existing, extend. [VERIFIED: codebase grep] |
| APPL-DLP-01..05 | DLP blocks before provider and outbound DLP suppresses unsafe response on real chat path. | integration | `uv run pytest tests/test_dlp_pipeline.py tests/test_dlp_audit.py tests/test_dlp_properties.py -q` plus new chat-route test | Existing, add route test. [VERIFIED: codebase grep] |
| MULTI-05/APPL-CDP-01 | Unsupported content type returns HTTP 415 from real app. | integration | `uv run pytest tests/multimodal/test_dispatcher.py -q` plus new `create_app()` middleware test | Existing, add app test. [VERIFIED: codebase grep] |
| APPL-SOC-01..09 | Normalized event fans out to configured sink router and health endpoint remains available. | unit/integration | `uv run pytest tests/test_soc_normalizer.py tests/test_soc_sink_factory.py tests/test_soc_api.py -q` plus new callback test | Existing, add callback test. [VERIFIED: codebase grep] |
| APPL-DISC-04 | `/v1/admin/discovery/inventory` is registered and reaches inventory service. | integration | `uv run pytest tests/discovery/test_discovery_inventory.py -q` plus new app route test | Existing, add route test. [VERIFIED: codebase grep] |
| APPL-AGENT-01/02/05/06 | Tool/MCP calls evaluated in runtime path; block/approval/audit decisions are emitted. | unit/property/integration | `uv run pytest tests/test_pdp_tool_evaluator.py tests/property/test_tool_governance.py tests/test_governance_audit.py tests/test_agent_tool_inspector.py -q` plus new route-stage test | Existing, add route test; stale `tests/test_agent_policy.py` needs decision. [VERIFIED: codebase grep] |

### Sampling Rate

- **Per task commit:** Run the focused command for the closure area changed. [ASSUMED]
- **Per wave merge:** Run all commands listed for that wave plus `uv run pytest tests/property/ -q -m "not slow"` when invariants are touched. [ASSUMED]
- **Phase gate:** Run `uv run pytest` and rerun milestone audit after all blockers close. [VERIFIED: `AGENTS.md`, milestone audit]

### Wave 0 Gaps

- [ ] Add proxy dispatcher adapter tests proving no raw body passthrough for AI requests. [ASSUMED]
- [ ] Add chat route DLP integration tests using provider mocks/fakes. [ASSUMED]
- [ ] Add `create_app()` middleware/route registration tests for content type and discovery. [ASSUMED]
- [ ] Add SOC normalizer callback-to-sink-router fan-out test. [ASSUMED]
- [ ] Add agent/tool governance runtime test or explicit requirement correction test/evidence. [ASSUMED]

## Concrete Verification Commands

```bash
# Proxy closure
uv run pytest tests/test_proxy_topology.py tests/test_proxy_integration.py -q
rg -n "dispatcher = app.state.pipeline|content_dispatcher=dispatcher|return request.body|status.*routed" src/anonreq/main.py src/anonreq/proxy

# DLP closure
uv run pytest tests/test_dlp_pipeline.py tests/test_dlp_audit.py tests/test_dlp_properties.py -q
rg -n "DLP|DLPEngine|dlp_inbound|dlp_outbound|OutboundDLP" src/anonreq/routing src/anonreq/pipeline src/anonreq/main.py

# Multimodal content-type closure
uv run pytest tests/multimodal/test_dispatcher.py tests/test_dispatcher_backward_compat.py -q
rg -n "ContentTypeMiddleware|add_middleware\\(ContentTypeMiddleware|ContentTypeDispatcher" src/anonreq/main.py src/anonreq/middleware src/anonreq/multimodal

# SOC fan-out closure
uv run pytest tests/test_soc_normalizer.py tests/test_soc_sink_factory.py tests/test_soc_api.py -q
rg -n "register_sink_callback|fan_out|soc_sink_router|soc_normalizer" src/anonreq/main.py src/anonreq/soc

# Discovery inventory admin closure
uv run pytest tests/discovery/test_discovery_inventory.py -q
rg -n "discovery.admin_router|include_router\\(.*discovery|inventory_service" src/anonreq/main.py src/anonreq/discovery

# Agent/tool governance closure
uv run pytest tests/test_pdp_tool_evaluator.py tests/property/test_tool_governance.py tests/test_governance_audit.py tests/test_agent_tool_inspector.py -q
rg -n "PDPToolEvaluator|ToolExtractor|ToolCallInspector|requires_approval|tool_blocked|tool_approval_required" src/anonreq/routing src/anonreq/pipeline src/anonreq/governance src/anonreq/agent

# Phase gate
uv run pytest
```

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | Existing `auth_context` dependency on protected routers must remain applied. [VERIFIED: `src/anonreq/main.py`] |
| V3 Session Management | yes | Token mappings remain session/context scoped and cleaned up by cache cleanup stages. [VERIFIED: `src/anonreq/routing/chat.py`, `AGENTS.md`] |
| V4 Access Control | yes | Admin discovery and SOC status routes must keep auth dependencies. [VERIFIED: `src/anonreq/main.py`, `src/anonreq/discovery/admin_router.py`] |
| V5 Input Validation | yes | FastAPI/Pydantic request models plus content-type middleware and tool schema validation should gate unsupported/malformed input. [VERIFIED: `src/anonreq/models/chat.py`, `src/anonreq/middleware/content_type.py`, `src/anonreq/agent/tool_inspector.py`] |
| V6 Cryptography | yes | Proxy TLS/MITM code must preserve existing TLS/cert handling; do not hand-roll crypto. [VERIFIED: `src/anonreq/proxy/transparent_proxy.py`, `src/anonreq/proxy/reverse_proxy.py`] |
| V9 Communications | yes | External provider and SIEM forwarding must never receive raw PII when policy requires anonymization/blocking. [VERIFIED: `AGENTS.md`] |
| V10 Malicious Code | yes | Tool governance and AI firewall should block command/code injection in tool args. [VERIFIED: `src/anonreq/agent/tool_inspector.py`] |
| V14 Configuration | yes | Sink, DLP, policy, and deployment mode wiring should fail closed when required config is unavailable. [VERIFIED: `AGENTS.md`] |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Raw PII bypass via proxy dispatcher mismatch | Information Disclosure | Contract adapter plus tests asserting sanitized provider body / no raw body response. [VERIFIED: milestone audit] |
| DLP absent from live route | Information Disclosure / Tampering | Live `PipelineManager` DLP stages before provider and before response delivery. [VERIFIED: codebase grep] |
| Unsupported content type reaches chat route | Information Disclosure | Install `ContentTypeMiddleware` before route handling. [VERIFIED: `src/anonreq/middleware/content_type.py`] |
| Raw SOC content forwarded to SIEM | Information Disclosure | Always route via `SOCNormalizer` before `SinkRouter.fan_out`. [VERIFIED: `src/anonreq/soc/normalizer.py`] |
| Admin route accidentally unauthenticated | Elevation of Privilege | Include discovery router with existing auth dependency pattern. [VERIFIED: `src/anonreq/main.py`, `src/anonreq/discovery/admin_router.py`] |
| Tool call executes destructive action | Tampering / Elevation of Privilege | `PDPToolEvaluator`/`ToolCallInspector` block or require approval before forwarding/execution. [VERIFIED: codebase grep] |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/22-close-milestone-audit-gaps-runtime-integration-blockers/22-CONTEXT.md` - phase goal and closure areas. [VERIFIED: file read]
- `.planning/v1.0-MILESTONE-AUDIT.md` - blocker evidence and required closure order. [VERIFIED: file read]
- `.planning/ROADMAP.md` Phase 22 section - requirements and success criteria. [VERIFIED: file read]
- `AGENTS.md` - project constraints and testing expectations. [VERIFIED: file read]
- `req/requirements.md`, `req/requirements_v2.md`, `.planning/REQUIREMENTS.md` - requirement definitions and checklist status. [VERIFIED: file read/grep]
- `src/anonreq/main.py`, `src/anonreq/routing/chat.py`, `src/anonreq/proxy/*`, `src/anonreq/services/pipeline.py`, `src/anonreq/middleware/content_type.py`, `src/anonreq/soc/*`, `src/anonreq/discovery/admin_router.py`, `src/anonreq/governance/*`, `src/anonreq/agent/*` - runtime wiring evidence. [VERIFIED: codebase grep]
- Existing tests under `tests/` named in Validation Architecture. [VERIFIED: codebase grep]

### Secondary (MEDIUM confidence)

- `pyproject.toml` and `uv.lock` - dependency and test infrastructure versions. [VERIFIED: file read/grep]

### Tertiary (LOW confidence)

- Assumptions about wave ordering and adapter shape are marked in the Assumptions Log. [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - verified from `pyproject.toml` and `uv.lock`. [VERIFIED: file read]
- Architecture: HIGH - based on direct source inspection of app, route, proxy, DLP, SOC, discovery, and governance modules. [VERIFIED: codebase grep]
- Pitfalls: HIGH for current gaps, MEDIUM for remediation sequencing. [VERIFIED: codebase grep]

**Research date:** 2026-07-07  
**Valid until:** 2026-08-06, or earlier if Phase 22 source changes land before planning. [ASSUMED]
