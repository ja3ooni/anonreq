---
phase: 29
slug: secure-configuration-secrets-management
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-12
---

# Phase 29 Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest with async mocks, ASGI transport, and watchdog-backed temp dirs |
| **Config file** | `pyproject.toml` |
| **Wave 1 command** | `uv run pytest tests/unit/secrets/test_secret_bootstrap.py tests/integration/test_startup_secret_bootstrap.py -q` |
| **Wave 2 command** | `uv run pytest tests/unit/secrets/test_reloader.py tests/integration/test_secret_hot_reload.py -q` |
| **Wave 3 command** | `uv run pytest tests/test_logging.py tests/unit/streaming/test_rotation_buffer.py -q` |
| **Full suite command** | `uv run pytest` |

## Sampling Rate

- **After Wave 1:** Run the secret bootstrap tests.
- **After Wave 2:** Run the hot reload tests plus the startup regression.
- **After Wave 3:** Run the logging redaction and rotation-buffer tests.
- **Before `$gsd-verify-work`:** Full suite must be green.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Requirement Focus | Test Type | Automated Command | Status |
|---------|------|------|-------------|-------------------|-----------|-------------------|--------|
| 29-01-01 | 01 | 1 | SEC-01 | Startup retrieves credentials from Vault/KMS into memory without env/disk persistence. | async unit + integration | `uv run pytest tests/unit/secrets/test_secret_bootstrap.py tests/integration/test_startup_secret_bootstrap.py -q` | pending |
| 29-02-01 | 02 | 2 | SEC-02 | Secret volume watch reloads the in-memory snapshot without service disruption. | async unit + integration | `uv run pytest tests/unit/secrets/test_reloader.py tests/integration/test_secret_hot_reload.py -q` | pending |
| 29-03-01 | 03 | 3 | SEC-03 | Secret substrings are redacted before log serialization. | unit | `uv run pytest tests/test_logging.py -q` | pending |
| 29-03-02 | 03 | 3 | SEC-04 | Previous keys remain available to active streams through rotation. | unit + integration | `uv run pytest tests/unit/streaming/test_rotation_buffer.py -q` | pending |

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Vault/KMS rotation under deployment | SEC-01, SEC-02, SEC-04 | Real secret backends and active stream lifetimes need deployment-level verification. | Rotate a live secret backend entry while streams are active; confirm reload without service interruption and no secret leakage in logs. |

## Validation Sign-Off

- [x] All tasks have automated verification or manual fallback
- [x] Sampling continuity is maintained
- [x] No watch-mode flags required
- [x] nyquist_compliant set in frontmatter

**Approval:** pending

