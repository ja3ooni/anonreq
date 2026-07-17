# Phase 29 Research

## Local Codebase Findings

1. `src/anonreq/config/__init__.py` is the current non-secret settings hub. It is env-backed today, so startup secrets should not be stuffed into `Settings` as raw secret values.
2. `src/anonreq/providers/registry.py` still resolves provider API keys from `os.environ`. That is the main credential seam to redirect into an in-memory secret store.
3. `src/anonreq/logging_config.py` already has a strict allowlist processor. That is a useful base for a second processor that redacts secret substrings before serialization.
4. `src/anonreq/proxy/ca_manager.py` already demonstrates file-watch hot reload with `watchdog` and atomic in-memory replacement. That is the right pattern for rotated secret/config volumes.
5. `src/anonreq/streaming/restoration.py` already keeps per-session state in memory. The phase can reuse that style for a read-only rotation snapshot that survives stream lifetime.
6. There is no current `hvac`/Vault client or cloud KMS client dependency in `pyproject.toml` or `uv.lock`, so phase 29 needs to add the secret-backend runtime surface explicitly.

## Planning Implications

- The phase should introduce a narrow secret-source abstraction instead of letting provider code read environment variables directly.
- Hot reload should be atomic and in-memory; it should not rewrite env files, config files, or other disk-backed secret material.
- Log redaction should operate on string payloads before JSON rendering, because allowlisting alone does not remove sensitive substrings embedded in allowed fields.
- The stream rotation buffer should keep prior keys read-only until active streams end, not just until the next request arrives.

