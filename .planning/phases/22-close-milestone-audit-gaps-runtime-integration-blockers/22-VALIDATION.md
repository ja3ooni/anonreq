---
phase: 22
slug: close-milestone-audit-gaps-runtime-integration-blockers
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-07
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest with pytest-asyncio and Hypothesis |
| **Config file** | `pyproject.toml` — `asyncio_mode = "auto"`, `testpaths = ["tests"]` |
| **Quick run command** | `uv run pytest <focused-test-file> -q` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~30s focused / ~10 min full suite |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest <focused-test-file> -q` for the closure area changed
- **After every plan wave:** Run all commands for that wave plus `uv run pytest tests/property/ -q -m "not slow"` when invariants are touched
- **Before `/gsd-verify-work`:** Full suite must be green + milestone audit rerun
- **Max feedback latency:** ~120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 22-01-01 | 01 | 1 | MULTI-05, APPL-CDP-01 | T-22-01-01 | Unsupported content types rejected with HTTP 415 before route/provider work | integration | `uv run pytest tests/integration/test_app_runtime_wiring.py -q` | ⬜ W0 | ⬜ pending |
| 22-01-02 | 01 | 1 | APPL-DISC-04 | T-22-01-02 | Discovery inventory routes reachable via authenticated app | integration | `uv run pytest tests/integration/test_app_runtime_wiring.py -q` | ⬜ W0 | ⬜ pending |
| 22-01-03 | 01 | 1 | APPL-SOC-01..09 | T-22-01-03 | Normalized SOC event fans out to sink router; raw content excluded | integration | `uv run pytest tests/test_soc_runtime_wiring.py -q` | ⬜ W0 | ⬜ pending |
| 22-02-01 | 02 | 1 | APPL-DLP-01..05 | T-22-02-01/02 | Inbound DLP blocks before provider; outbound DLP blocks before delivery | integration | `uv run pytest tests/integration/test_runtime_dlp_pipeline.py -q` | ⬜ W0 | ⬜ pending |
| 22-02-02 | 02 | 1 | APPL-AGENT-01/02/05/06 | T-22-02-03/04 | Tool governance evaluated; blocked tools fail closed; approval-required tools suspend | integration | `uv run pytest tests/integration/test_runtime_tool_governance.py -q` | ⬜ W0 | ⬜ pending |
| 22-03-01 | 03 | 2 | APPL-01/02/03/06 | T-22-03-01 | Proxy adapter dispatches through anonymization-capable pipeline | unit/integration | `uv run pytest tests/test_proxy_pipeline_dispatcher.py tests/test_proxy_topology.py -q` | ⬜ W0 | ⬜ pending |
| 22-04-01 | 04 | 3 | (planning reconciliation) | T-22-04-01 | Verification artifacts exist for all phases | manual | `find .planning/phases -maxdepth 2 -name '*-VERIFICATION.md' -print` | ✅ | ⬜ pending |
| 22-04-02 | 04 | 3 | (checklist reconciliation) | T-22-04-02 | Requirements/roadmap/state totals agree with evidence | manual | `awk ... .planning/REQUIREMENTS.md && .planning/ROADMAP.md` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/integration/test_app_runtime_wiring.py` — content-type + discovery + SOC wiring stubs
- [ ] `tests/test_soc_runtime_wiring.py` — SOC normalizer callback fan-out stubs
- [ ] `tests/integration/test_runtime_dlp_pipeline.py` — DLP pipeline stage stubs
- [ ] `tests/integration/test_runtime_tool_governance.py` — tool governance stage stubs
- [ ] `tests/test_proxy_pipeline_dispatcher.py` — proxy adapter dispatch stubs

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Proxy pipelines closed | APPL-01..06 | Adapter replaces dispatcher in deployment proxy; verifiable by milestone audit rerun | Deploy with reverse/transparent proxy config; send AI chat payload containing PII; assert response body is sanitized |
| SOC sink health | APPL-SOC-08/09 | Integration requires live sink configuration | Run `GET /v1/admin/soc/integration/status` after wiring; assert status returns health data per registered sink |
| Milestone audit rerun | (milestone gate) | Manual audit gate | Run milestone audit command; verify no critical runtime integration blockers remain |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
