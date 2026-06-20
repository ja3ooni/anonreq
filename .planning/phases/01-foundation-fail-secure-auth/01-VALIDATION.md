---
phase: 1
slug: foundation-fail-secure-auth
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-20
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + httpx |
| **Config file** | pyproject.toml (Wave 0 installs) |
| **Quick run command** | `pytest tests/ -x --tb=short` |
| **Full suite command** | `pytest tests/ -v --cov=src --cov-report=term-missing` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x --tb=short`
- **After every plan wave:** Run full test suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | DOCK-01 | — | Config loaded from env, not files | unit | `pytest tests/ -x --tb=short` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | DOCK-02 | — | All deps pinned in pyproject.toml | unit | `pytest tests/ -x --tb=short` | ❌ W0 | ⬜ pending |
| 01-02-01 | 01 | 1 | FAIL-01/02/03 | T-01-01 | Exception handler returns 500, no leaks | unit | `pytest tests/ -x --tb=short` | ❌ W0 | ⬜ pending |
| 01-02-02 | 01 | 1 | AUDT-01/02/03 | T-01-02 | Audit logger strips PII from all fields | unit | `pytest tests/ -x --tb=short` | ❌ W0 | ⬜ pending |
| 01-03-01 | 01 | 1 | DOCK-03/04/05 | T-01-03 | Docker Compose starts all services | integration | `docker-compose up -d` | ❌ W0 | ⬜ pending |
| 01-04-01 | 01 | 1 | DOCK-06/07 | — | Pre-flight checks fail on missing deps | integration | `pytest tests/ -x --tb=short` | ❌ W0 | ⬜ pending |
| 01-05-01 | 01 | 1 | AUTH-MINIMAL-01 | T-01-04 | Static bearer auth rejects bad tokens | unit | `pytest tests/ -x --tb=short` | ❌ W0 | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — shared fixtures
- [ ] `tests/test_config.py`
- [ ] `tests/test_auth.py`
- [ ] `tests/test_exceptions.py`
- [ ] `tests/test_logging.py`
- [ ] `tests/test_health.py`
- [ ] `pytest` + `httpx` + `pytest-cov` in dev deps

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Docker Compose startup | DOCK-03 | Requires Docker daemon | `docker-compose up -d && docker-compose ps` |
| Pre-flight failure on missing Valkey | DOCK-07 | Requires service isolation | Stop valkey container, restart anonreq, verify 500 |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
