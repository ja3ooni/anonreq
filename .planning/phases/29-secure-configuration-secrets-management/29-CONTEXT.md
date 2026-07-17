# Phase 29: Secure Configuration & Secrets Management - Context

**Gathered:** 2026-07-12
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers startup secret retrieval, in-memory hot reload of rotated configuration, structured log redaction, and stream-safe key rotation without persisting secrets to environment variables or disk.

</domain>

<baseline>
## What Is Already Implemented

- `Settings` is already centralized in `src/anonreq/config/__init__.py` and uses `pydantic-settings` for non-secret application configuration.
- `ProviderRegistry` already resolves provider adapters and provider keys, but it still reads API keys from environment variables.
- `logging_config.py` already enforces a top-level allowlist, so the phase can extend the processor chain instead of replacing logging entirely.
- `StreamingRestorationStage` already keeps per-session mapping state in memory, which is the closest existing seam for a read-only rotation snapshot.
- `watchdog` is already a runtime dependency and is already used by `proxy/ca_manager.py` for file-watch hot reload, so there is a local pattern for volume monitoring.

</baseline>

<decisions>
## Implementation Decisions

### Secret Retrieval
- **D-01:** Resolve upstream provider credentials at startup from a secret backend instead of persisting them in environment variables or on disk.
- **D-02:** Keep the secret source logic behind a narrow in-memory abstraction so runtime code can consume credentials without learning where they came from.

### Hot Reload
- **D-03:** Use a watchdog-style volume monitor for rotated secret/config files and reload in memory only.
- **D-04:** Keep the app using a single live secret/config snapshot; reload should swap the in-memory snapshot atomically rather than rebuild the app.

### Logs and Rotation
- **D-05:** Redact secret substrings before structured log serialization, not after.
- **D-06:** Preserve the previous key snapshot in a read-only rotation buffer until active SSE streams finish.

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` - Phase 29 definition, goals, and success criteria
- `.planning/REQUIREMENTS.md` - SEC-01 through SEC-04 traceability
- `src/anonreq/config/__init__.py` - env-backed settings baseline
- `src/anonreq/providers/registry.py` - provider credential resolution seam
- `src/anonreq/logging_config.py` - structured log processor chain
- `src/anonreq/proxy/ca_manager.py` - watchdog hot-reload pattern
- `src/anonreq/streaming/restoration.py` - session-local in-memory streaming state

</canonical_refs>

<open_questions>
## Open Questions

- Which secret backend is configured in the deployment target for the first concrete implementation path?
- Should the secret store be exposed to provider adapters through `app.state`, a module-level cache, or both?

</open_questions>

---
# Phase 29: Secure Configuration & Secrets Management - Discussion Log

> Audit trail only. Do not use as input to planning, research, or execution agents.

**Date:** 2026-07-12
**Phase:** 29 - Secure Configuration & Secrets Management

## Secret Retrieval

| Option | Description | Selected |
|--------|-------------|----------|
| Option A | Bootstrap provider credentials from a secret backend into an in-memory store | ✓ |
| Option B | Keep provider credentials env-backed and only wrap them later | |

## Reload Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Option A | Reuse a watchdog-style volume monitor and atomic snapshot swap | ✓ |
| Option B | Poll on a fixed timer without file event integration | |

## Log and Stream Safety

| Option | Description | Selected |
|--------|-------------|----------|
| Option A | Redact secret substrings before JSON serialization and retain previous key snapshots for active streams | ✓ |
| Option B | Rely on allowlist-only logging and stream restarts | |

