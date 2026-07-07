---
phase: 21-endpoint-visibility-sovereign-control
plan: 05
subsystem: firewall
tags: [ai-firewall, prompt-injection, jailbreak, mitre-atlas, fail-closed]
requires:
  - phase: 21
    plan: 01
    provides: transparent proxy deployment topology and inline interception point
provides:
  - Self-hosted AI Firewall pipeline with ALLOW/BLOCK decisions
  - Local ONNX classifier wrapper with injectable session behavior for tests
  - Locally cached jailbreak pattern database with reload support
  - Deterministic semantic injection scorer with injectable embedding provider
  - System prompt override and role-manipulation detector
  - MITRE ATLAS mappings for firewall events
affects: [phase-21, firewall, proxy, appliance]
tech-stack:
  added: []
  patterns: [fail-closed-firewall, injectable-local-inference, metadata-only-audit, atlas-yaml-mapping]
key-files:
  created:
    - src/anonreq/firewall/config.py
    - src/anonreq/firewall/classifier.py
    - src/anonreq/firewall/jailbreak_db.py
    - src/anonreq/firewall/injection_scorer.py
    - src/anonreq/firewall/override_detector.py
    - src/anonreq/firewall/pipeline.py
    - config/mitre_atlas.yaml
    - tests/test_firewall_classifier.py
    - tests/test_firewall_jailbreak.py
    - tests/test_firewall_injection.py
    - tests/test_firewall_pipeline.py
  modified:
    - src/anonreq/firewall/__init__.py
    - src/anonreq/proxy/transparent_proxy.py
    - src/anonreq/main.py
key-decisions:
  - "Semantic injection scoring is local and deterministic by default, with an injectable embedding provider for production ONNX/sentence-transformer backends, avoiding test-time model downloads."
  - "TransparentProxy evaluates the Phase 21 FirewallPipeline before TLS certificate generation, AI classification, or dispatcher routing."
  - "Firewall errors fail closed by default: pipeline evaluation errors become HTTP 500 unless fail_open is explicitly configured."
requirements-completed:
  - APPL-01/Req52
  - APPL-01/Req60
duration: 28 min
completed: 2026-07-05
status: complete
---

# Phase 21 Plan 05: Self-Hosted AI Firewall Summary

**Self-hosted AI Firewall with local classification, jailbreak pattern matching, semantic injection scoring, system override detection, MITRE ATLAS audit metadata, and fail-closed inline proxy enforcement**

## Performance

- **Started:** 2026-07-05T15:34:56Z
- **Completed:** 2026-07-05T16:03:00Z
- **Tasks:** 3
- **Files modified:** 14
- **Commits:** Not created because the working tree already had unrelated staged files and prior uncommitted Phase 21 edits in shared integration files.

## Accomplishments

- Added `FirewallConfig` and `FIREWALL_DECISIONS` with thresholds, model paths, 20ms latency budget, and fail-open toggle.
- Added `config/mitre_atlas.yaml` with six AI-specific MITRE ATLAS mappings: AML-T0018, AML-T0025, AML-T0021, AML-T0016, AML-T0015, and AML-T0018.002.
- Implemented `JailbreakDB` with JSON loading, reload support, regex compilation, keyword matching, and safe built-in baseline patterns when the policy file is absent.
- Implemented `InjectionScorer` with deterministic local embedding-distance scoring and injectable embedding provider support for production model backends.
- Implemented `OverrideDetector` for system prompt extraction and role-manipulation attempts.
- Implemented `ONNXClassifier` with lazy loading, injectable session support, and fail-closed missing-model behavior.
- Implemented `StructuralClassifier` for fast-path local prompt injection, jailbreak, role manipulation, and model theft detection.
- Implemented `FirewallPipeline` with two-stage structural and semantic evaluation, HTTP 403 block responses, HTTP 500 fail-closed error responses, Prometheus metrics, and metadata-only audit events.
- Integrated `TransparentProxy` with optional inline firewall evaluation before downstream dispatcher routing.

## Verification

- `pytest tests/test_firewall_jailbreak.py tests/test_firewall_injection.py tests/test_firewall_classifier.py tests/test_firewall_pipeline.py -q` -> 27 passed.
- `pytest tests/test_proxy_topology.py tests/test_proxy_integration.py tests/firewall/test_firewall_integration.py -q` -> 24 passed.
- `pytest tests/firewall/test_firewall_integration.py -q` -> 6 passed.
- `PYTHONPATH=src python3 -c "from anonreq.firewall.config import FirewallConfig, FIREWALL_DECISIONS; cfg = FirewallConfig(); assert cfg.jailbreak_threshold == 0.85; assert cfg.latency_budget_ms == 20; assert cfg.enabled == True; print('Firewall config OK')"` -> passed.
- Artifact line counts satisfy plan minimums: `classifier.py` 128 lines, `jailbreak_db.py` 129 lines, `injection_scorer.py` 97 lines, `pipeline.py` 280 lines, `mitre_atlas.yaml` 40 lines.

## Task Commits

No task commits were created. The repository had pre-existing staged files before this plan started:

- `src/anonreq/proxy/__init__.py`
- `src/anonreq/proxy/tls_interceptor.py`
- `tests/test_proxy_tls.py`

Additionally, `src/anonreq/main.py` and `src/anonreq/proxy/transparent_proxy.py` already contained uncommitted prior-wave integration edits. Committing Plan 21-05 would have captured unrelated earlier work, so changes were left in the working tree.

## Files Created/Modified

- `src/anonreq/firewall/config.py` - Firewall thresholds, model paths, latency budget, and decision enum.
- `src/anonreq/firewall/classifier.py` - ONNX classifier wrapper and structural fast-path classifier.
- `src/anonreq/firewall/jailbreak_db.py` - Locally cached jailbreak pattern database.
- `src/anonreq/firewall/injection_scorer.py` - Semantic injection scoring with injectable embeddings.
- `src/anonreq/firewall/override_detector.py` - System prompt and role-manipulation detector.
- `src/anonreq/firewall/pipeline.py` - Full firewall evaluation, decisions, metrics, audit, and response helpers.
- `config/mitre_atlas.yaml` - AI-specific MITRE ATLAS mapping.
- `src/anonreq/firewall/__init__.py` - Exported Phase 21 config symbols without replacing existing exports.
- `src/anonreq/proxy/transparent_proxy.py` - Optional inline firewall evaluation before dispatcher routing.
- `src/anonreq/main.py` - Transparent deployment proxy factory now supplies `FirewallPipeline`.
- `tests/test_firewall_classifier.py` - Config, ONNX stub, and structural classifier tests.
- `tests/test_firewall_jailbreak.py` - Jailbreak DB loading and matching tests.
- `tests/test_firewall_injection.py` - Injection scorer and override detector tests.
- `tests/test_firewall_pipeline.py` - Pipeline decisions, response handling, fail-closed behavior, MITRE IDs, latency, and proxy inline tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Inline proxy enforcement added**
- **Found during:** Task 3
- **Issue:** Implementing only `FirewallPipeline` would not satisfy the inline-before-downstream requirement.
- **Fix:** Added optional `firewall_pipeline` evaluation to `TransparentProxy.handle_request()` before certificate generation, traffic classification, and dispatcher routing.
- **Files modified:** `src/anonreq/proxy/transparent_proxy.py`, `src/anonreq/main.py`, `tests/test_firewall_pipeline.py`
- **Verification:** Proxy inline test passes and dispatcher call count remains zero for blocked requests.

**2. [Rule 2 - Missing Critical] Heavy model download avoided**
- **Found during:** Task 2
- **Issue:** Loading `sentence-transformers` by default would introduce network/model-download behavior and violate the user's instruction to avoid heavy model downloads.
- **Fix:** Implemented deterministic local embedding scoring with injectable embedding provider support. Production can supply ONNX/sentence-transformer embeddings without changing pipeline contracts.
- **Files modified:** `src/anonreq/firewall/injection_scorer.py`, `tests/test_firewall_injection.py`
- **Verification:** Semantic injection tests pass with both injected and default local scoring paths.

## Known Stubs

None. The ONNX classifier supports injectable sessions and fails closed when a configured model file is absent; this is intentional runtime behavior, not a stub.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: inline_security_gate | `src/anonreq/proxy/transparent_proxy.py` | New firewall block path at the network interception trust boundary; mitigated by fail-closed default and generic HTTP 403/500 bodies. |
| threat_flag: audit_security_event | `src/anonreq/firewall/pipeline.py` | New firewall audit event surface; events include metadata only and do not include raw prompt text. |

## Self-Check: PASSED

- Created files exist.
- Focused firewall and proxy tests pass.
- Summary file exists.
- Commits intentionally skipped due dirty-tree/staged unrelated changes.

---
*Phase: 21-endpoint-visibility-sovereign-control*
*Completed: 2026-07-05*
