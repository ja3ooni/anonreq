---
phase: 27
slug: v1-5-tech-debt-cleanup
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-12
---

# Phase 27 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x, asyncio_mode = auto |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_trust_center.py -q` |
| **Full suite command** | `uv run pytest tests/ --ignore=tests/load -m "not load"` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_trust_center.py -q`
- **After every plan wave:** Run `uv run pytest tests/ --ignore=tests/load -m "not load"`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 27-01-01 | 01 | 1 | HYG-01 | T-27-SC | N/A | smoke | `uv run pytest tests/ --collect-only -q --ignore=tests/load` | ✅ | ⬜ pending |
| 27-01-02 | 01 | 1 | TRUST-01 | T-27-01 | Endpoints rate-limited, no PII | integration | `uv run pytest tests/test_trust_center.py -q` | ✅ | ⬜ pending |
| 27-01-03 | 01 | 1 | HYG-02 | — | N/A | manual | N/A | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Documentation text accuracy | HYG-02 | Prose content accuracy check cannot be automated | Verify `.planning/phases/23-engineering-hygiene/23-01-SUMMARY.md` is updated to accurately document the global strict mypy configuration and overrides. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-12
