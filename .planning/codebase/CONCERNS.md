# Codebase Concerns

**Analysis Date:** 2026-07-17

## Resolved Since 2026-07-06

The following issues from the prior audit have been fixed in commits between 2026-07-06 and 2026-07-17:

| Issue | Resolution | Commit |
|-------|-----------|--------|
| **Timing-safe API key comparison** | `hmac.compare_digest()` applied to `dependencies.py` and `admin/auth.py` | `fb35ca2` |
| **PolicyMiddleware hardcoded tenant_id="default"** | Extracts tenant_id from OIDC principal via `request.state.oidc_principal` | `fb35ca2` |
| **Provider error body leakage** | Provider error details removed from error messages, logged via structlog instead | `fb35ca2` |
| **Hardcoded Postgres/MinIO credentials** | Replaced with `${POSTGRES_USER:?err}`, `${MINIO_ROOT_USER:?err}` required env vars | `fb35ca2` |
| **License router unauthenticated** | Auth dependency added | `58c1d54` |
| **Logging allowlist missing fields** | 13 fields added to `ALLOWLIST` in `logging_config.py` | `58c1d54` |
| **`_redact_value` not recursive into Pydantic models** | Recursive redaction added for `model_dump()` and `__dataclass_fields__` | `58c1d54` |
| **Duplicate `Role.READ_ONLY` alias** | Removed in `middleware/rbac.py` | `58c1d54` |
| **Hardcoded Presidio max_concurrency** | Now configurable via `ANONREQ_PRESIDIO_MAX_CONCURRENCY` | `58c1d54` |
| **SSRF via httpx redirect following** | `follow_redirects=False` applied to all 12 outbound httpx clients | `1a2775c` |
| **CacheManager test fragility (`__new__`)** | `CacheManager._from_client()` factory added for tests | `1a2775c` |
| **main.py 672-line monolith lifespan** | Decomposed into `bootstrap/services.py` domain bootstrappers (main.py now 465 lines) | `3cfae60` |
| **app.state typeless bag** | `AppState` dataclass with typed fields + `get_app_state()` helper | `97ce14a` |
| **E2E round-trip test gap** | Full pipeline integration test added in `tests/integration/test_e2e_round_trip.py` | `17f5f1e` |

## Tech Debt

### Broad `except Exception:` Swallowing Errors

**Issue:** 96 instances of bare `except Exception:` across `src/anonreq/`, many followed by `pass` or no re-raise. Down from 102 (fixed patterns in bootstrap, middleware, provider). This pattern silently discards errors across critical subsystems.

**Files:** `src/anonreq/ediscovery/export.py` (3 instances), `src/anonreq/middleware/policy.py` (2 instances), `src/anonreq/middleware/mtls.py` (2 instances), `src/anonreq/pipeline/provider.py` (1 instance), `src/anonreq/bootstrap/services.py` (1 instance), `src/anonreq/proxy/ca_manager.py` (1 instance), `src/anonreq/retention/legal_hold.py` (4 instances), `src/anonreq/retention/tiers.py` (2 instances), and ~80 more across 40+ files.

**Impact:** Critical failures in audit chain storage, breach detection, webhook delivery, DLQ processing, and SIEM forwarding are silently ignored. Operators receive no alert when background operations fail.

**Fix approach:**
- Replace with specific exception types where possible
- At minimum log the exception with `logger.warning()` or `logger.exception()` before `pass`
- For fire-and-forget operations, add structured logging

### Over-Mixing os.environ and Pydantic Settings

**Issue:** The codebase reads environment variables via both Pydantic Settings (`settings.X`) and raw `os.environ.get()` in 10 files. This creates two paths for configuration that can diverge.

**Files:** `src/anonreq/deployment/modes.py` (8+ `os.environ` calls), `src/anonreq/providers/registry.py:177-182`, `src/anonreq/storage/minio.py:256-263`, `src/anonreq/providers/ollama.py:44`, `src/anonreq/services/breach_detector.py`, `src/anonreq/services/audit_exporter.py`, `src/anonreq/proxy/modes.py:131`, `src/anonreq/soc/sink_config.py:192`, `src/anonreq/main.py:128`, `src/anonreq/secrets/bootstrap.py:38-39`

**Impact:** Configuration is scattered. Adding a new config variable requires checking both Pydantic Settings and raw env access. Environment variable defaults defined in `os.environ.get()` calls may conflict with Pydantic Settings defaults.

**Fix approach:** Centralize all configuration in `anonreq.config.settings` (Pydantic Settings). Eliminate raw `os.environ.get()` calls in production code.

### Silently Swallowed Webhook Config Load Failure

**Issue:** `src/anonreq/services/breach_detector.py` — YAML config file loading wrapped in `except Exception: pass`. If the webhook config file is malformed YAML, the breach detector silently falls back to environment variable defaults with no warning.

**Files:** `src/anonreq/services/breach_detector.py`

**Impact:** Misconfigured webhook settings may go unnoticed until breach notifications fail.

**Fix approach:** Log a warning on config load failure instead of `pass`.

### Httpx.Request Monkey Patch at Module Import Time

**Issue:** `src/anonreq/detection/presidio_client.py` monkey-patches `httpx.Request.json` at module import time. This modifies a third-party library class globally.

**Files:** `src/anonreq/detection/presidio_client.py`

**Impact:** Any other module using `httpx.Request.json` gets the patched behavior. If httpx adds a `json` property in a future version, the patch causes a silent override.

**Fix approach:** Use `response.json()` directly instead of patching `Request`. The patch exists because httpx < 0.28 didn't expose `Request.json` — upgrade dependency constraint or handle the response parsing locally.

### Direct Access to Private `_redis` Attribute

**Issue:** `src/anonreq/services/breach_detector.py` and `src/anonreq/cache/health.py` access `cache_manager._redis` directly, coupling consumers to the internal implementation of `CacheManager`.

**Files:** `src/anonreq/services/breach_detector.py:66`, `src/anonreq/cache/health.py:108-113`

**Impact:** Any refactor of `CacheManager`'s internal `_redis` attribute (rename, swap to mock, add connection lifecycle) breaks downstream consumers silently.

**Fix approach:** Expose a public `redis` property on `CacheManager` or provide dedicated cache methods for direct Redis operations.

### Duplicate `_network_proxy_autostart_enabled` Import

**Issue:** `src/anonreq/main.py` — `os` is imported at module level (line 18) but also re-imported locally in `_network_proxy_autostart_enabled()` (line 141).

**Files:** `src/anonreq/main.py:141`

**Impact:** Redundant import, no functional impact but code hygiene issue.

**Fix approach:** Remove the local `import os`.

## Security Considerations

### Hardcoded Default MinIO Credentials in Production Code

**Risk:** `src/anonreq/storage/minio.py:257-258` still defaults to `minioadmin`/`minioadmin` for MinIO access when environment variables are not set. Docker-compose has been fixed to require env vars, but the Python fallback in code persists.

**Files:** `src/anonreq/storage/minio.py:257-258`

**Current mitigation:** Docker-compose now uses `${MINIO_ROOT_USER:?err}` pattern.

**Recommendations:** Fail at startup if MinIO credentials are not configured (no default fallback in Python code). Document required env vars explicitly. Require credentials via Pydantic Settings validation.

### Unauthenticated /metrics Endpoint

**Risk:** `src/anonreq/main.py:356-361` — The Prometheus `/metrics` endpoint has no authentication. The comment says "scrapers connect on internal networks; secured at network level."

**Files:** `src/anonreq/main.py:356-361`

**Current mitigation:** Relies on network-level security only.

**Recommendations:** Add optional authentication for `/metrics` or document explicitly that network-level access controls must be configured. If metrics contain any request metadata (even anonymized), it's a data leak vector.

### PAC File Endpoint Unauthenticated

**Risk:** `src/anonreq/main.py:398` — `pac_router` is included without `Depends(auth_context)`. The PAC file reveals all proxy domains and the gateway's network position.

**Files:** `src/anonreq/main.py:398`

**Current mitigation:** PAC is designed for browser/proxy consumption.

**Recommendations:** If PAC endpoint exposes sensitive network topology, consider restricting to internal networks or adding optional auth.

### `presidio-analyzer:latest` and `minio:latest` Tags

**Risk:** `docker-compose.yml` uses `latest` tags for presidio-analyzer and minio. Builds are non-reproducible — behavior changes silently on image cache invalidation.

**Files:** `docker-compose.yml:44,137`

**Current mitigation:** Specific version tags used for other images (postgres `16-alpine`, prometheus `v2.53.0`, grafana `11.0.0`).

**Recommendations:** Pin presidio-analyzer and minio to specific version tags for reproducible deployments.

### Error Bodies Include Classification Details on 451

**Risk:** `src/anonreq/exceptions.py:321-335` — When returning HTTP 451, the error response body includes classification details (`highest`, `labels`, `reason`). While these are classification labels (not raw PII), they do leak internal policy information that a client could use to probe classification boundaries.

**Files:** `src/anonreq/exceptions.py:321-335`

**Current mitigation:** Only returned on 451 (DLP block) responses.

**Recommendations:** Consider returning classification details only when an admin-level `X-AnonReq-Debug` header is present, keeping the default 451 envelope generic.

### Docker Runs as Root Initially

**Risk:** `docker-compose.yml:72` — The `anonreq` service starts as `root` before switching to the `anonreq` user via `su`. While it does drop privileges, the initial root execution could be exploited.

**Files:** `docker-compose.yml:72`

**Current mitigation:** Privilege drop happens early in startup.

**Recommendations:** Use Docker's `USER` directive directly or run `chown` in a build step. Avoid runtime privilege escalation patterns.

## Performance Bottlenecks

### Lazy HTTP Client Initialization in Provider Adapters

**Problem:** Multiple provider adapters (`OpenAIAdapter`, `AnthropicAdapter`, `GeminiAdapter`, `OllamaAdapter`) create lazy `httpx.AsyncClient` instances on first request. This means the first request to each provider pays connection pool initialization latency.

**Files:** `src/anonreq/providers/openai.py:41-42`, `src/anonreq/providers/anthropic.py:58-59`, `src/anonreq/providers/gemini.py:60`, `src/anonreq/providers/ollama.py:70`

**Cause:** `@property` pattern that creates `httpx.AsyncClient` on first access.

**Improvement path:** Create clients during lifespan startup alongside other initialized services (`src/anonreq/main.py`). Pre-warm connections during pre-flight checks. Or use `bootstrap/providers.py` to init all provider clients at startup.

### Presidio Request Semaphore Bottleneck

**Problem:** `src/anonreq/detection/presidio_client.py` hardcodes a default `max_concurrency=10` for the Presidio request semaphore. For large payloads with many text nodes, this limits throughput to 10 concurrent Presidio requests.

**Files:** `src/anonreq/detection/presidio_client.py:63`

**Cause:** Default set via constructor parameter, now configurable via `ANONREQ_PRESIDIO_MAX_CONCURRENCY` setting.

**Improvement path:** Tune the setting based on Presidio instance capacity. Consider auto-scaling based on latency metrics.

### In-Memory Streaming Buffer for SSE Restoration

**Problem:** The streaming restoration pipeline (TailBuffer FSM) buffers partial SSE chunks in memory for split-token matching. Under high-throughput streaming scenarios, memory pressure from buffered chunks could become significant.

**Files:** `src/anonreq/restore/` (streaming restoration)

**Cause:** Necessity of stateful streaming matching — split tokens require buffer-until-complete strategy.

**Improvement path:** Add streaming buffer size limits with configurable max buffer size per stream connection. Emit warning logs when buffer utilization is high.

## Fragile Areas

### 859-Line Governance Router Monolith

**Issue:** `src/anonreq/governance/router.py` is 859 lines with 42+ route handlers/functions. It mixes route definitions, inline business logic, audit event emission, risk assessment, approval management, and supplier governance.

**Files:** `src/anonreq/governance/router.py` (859 lines)

**Why fragile:** High cognitive load for modifications. Risk of accidental cross-route state coupling. Difficult to unit test individual behaviors without spinning up the full route layer.

**Safe modification:** Extract inline business logic into service classes (e.g., `GovernanceService`, `RiskAssessmentService`). Keep router layer thin — route → service call → response.

### 496-Line routing/chat.py

**Issue:** `src/anonreq/routing/chat.py` is 496 lines handling both routing logic and pipeline construction. It's the second-largest non-governance file.

**Files:** `src/anonreq/routing/chat.py` (496 lines)

**Why fragile:** Pipeline construction interleaved with route handling. Changes to pipeline stages affect routing logic and vice versa.

**Safe modification:** Extract `build_pre_provider_pipeline()` into its own module (e.g., `pipeline/builder.py`) and keep routing focused on request dispatch.

### Provider Adapter Schema Translation

**Issue:** Provider adapters (`AnthropicAdapter`, `GeminiAdapter`) translate from OpenAI schema to provider-specific schemas and back. These are complex bidirectional mappings with many edge cases (tools, streaming, multi-modal, system messages).

**Files:** `src/anonreq/providers/anthropic.py` (428 lines), `src/anonreq/providers/gemini.py` (406 lines), `src/anonreq/providers/openai.py` (244 lines)

**Why fragile:** Provider API changes (e.g., Anthropic adding new message roles, Gemini restructuring content blocks) silently break translation without contract tests. The error normalization layer may mask schema drift.

**Test coverage:** Contract tests exist but may not cover all endpoint variants. Each new model capability (extended thinking, image inputs, tool use v2) requires adapter updates.

### Casual LLM Provider Hostname Detection

**Issue:** `src/anonreq/gateway/detector.py` uses simple regex patterns to detect AI provider hostnames. No support for custom/self-hosted providers beyond the hardcoded list.

**Files:** `src/anonreq/gateway/detector.py`

**Why fragile:** New providers require code changes. Custom deployments (e.g., on-prem Azure OpenAI) may use non-standard hostnames. Pattern match order is implicit.

### Provider Credential Resolution Chain

**Issue:** `src/anonreq/providers/registry.py` resolves provider API keys via a fallback chain — `RuntimeSecretStore` → provider-specific env var → `settings.PROVIDER_API_KEY` → `settings.API_KEY`. This means the gateway's own API key can be used as the LLM provider API key.

**Files:** `src/anonreq/providers/registry.py:161-182`, `src/anonreq/routing/chat.py:146`

**Why fragile:** If `PROVIDER_API_KEY` and the provider-specific env var are both unset, the gateway's auth key is sent to the LLM provider. An operator may inadvertently reuse the same key value for both gateway auth and provider auth, then change one without the other.

**Safe modification:** Log a warning when falling through to `settings.API_KEY` for provider credentials. Better: require explicit provider credential configuration and fail at startup if missing.

## Scaling Limits

### Single-Process Event Loop

**Current capacity:** Single uvicorn worker, single asyncio event loop.

**Limit:** Under high concurrent request load, all request handling (Presidio calls, provider calls, streaming, audit) contends on one event loop. Long-running streaming connections block event loop responsiveness.

**Scaling path:** Add `uvicorn` worker count configuration. Consider dedicated connections for streaming vs. non-streaming traffic. Evaluate moving Presidio calls to a thread pool executor.

### In-Memory Token Mapping

**Current capacity:** Token mappings stored in Valkey with TTL-based eviction. No fallback for Valkey outage beyond fail-secure 503. Cache now supports standalone, Sentinel, and Cluster topologies (Phase 28).

**Limit:** Cache key space grows linearly with request volume. TTL of 60-3600s means mappings for long-running sessions may expire before restoration completes. Tenacity retry adds resilience but bounded at 30s total retry window.

**Scaling path:** Add local in-memory LRU cache as L1 with Valkey as L2. Implement mapping persistence (encrypted) for long-running agent sessions.

## Dependencies at Risk

### onnxruntime + openai-whisper Dependencies

**Risk:** `pyproject.toml` includes `onnxruntime` and `openai-whisper` as optional extras (`[ml]`, `[voice]`). These are large (~500MB combined with CUDA deps) and only needed for the voice pipeline (speech-to-text), which is a secondary feature.

**Impact:** Docker image bloat. CI/CD pipeline time increases. Potential build failures on ARM64 (Apple Silicon) for onnxruntime without `--extra-index-url`.

**Migration plan:** Voice dependencies correctly in optional extras group (Partially resolved — `[voice]` and `[ml]` groups exist). Ensure Docker build uses `--extra all` only when voice features are needed.

### httpx Monkey-patch Dependency

**Risk:** `src/anonreq/detection/presidio_client.py` depends on `httpx.Request` not having a `json` property. A minor httpx version bump could add this and break the patch.

**Impact:** `AttributeError` on `PresidioClient.analyze()` — breaks detection pipeline.

**Migration plan:** Pin httpx to a specific minor version or remove the monkey patch entirely by using `response.json()` for response parsing.

## Test Coverage Gaps

### Governance Router Routes

**What's not tested:** The 42+ route handlers in `src/anonreq/governance/router.py` (859 lines) — inline business logic for risk assessment, approval management, and supplier governance.

**Files:** `src/anonreq/governance/router.py`

**Risk:** Route handler bugs (wrong status codes, missing audit events, incorrect permission checks) are caught only by manual testing or production incidents.

**Priority:** High — governance routes manage compliance-critical operations.

### Provider Adapter Translation Edge Cases

**What's not tested:** Non-standard request shapes (empty tool calls, multi-modal with images, system messages with structured content, parallel tool calls in streaming mode).

**Files:** `src/anonreq/providers/anthropic.py`, `src/anonreq/providers/gemini.py`

**Risk:** Provider schema drift silently breaks translation for edge-case payloads. Restored responses may be malformed for certain request shapes.

**Priority:** Medium — contract tests exist but edge case coverage is unknown.

### SOC/SIEM Sink Error Recovery

**What's not tested:** SIEM sink reconnection behavior, DLQ overflow behavior, sink health monitor recovery after partial outage.

**Files:** `src/anonreq/soc/sinks/` (all sinks)

**Risk:** SOC event loss during sink outages. If DLQ fills up (`dlq_max_entries`), older events are silently evicted.

**Priority:** Medium — evidence loss impacts compliance posture.

### Voice/Speech Pipeline

**What's not tested:** End-to-end voice processing (STT → sanitize → restore → TTS). The voice pipeline has heavy dependencies (whisper, onnxruntime) that may not be exercised in CI.

**Files:** `src/anonreq/voice/`

**Risk:** Voice feature may be broken without CI catching it. Model loading failures at runtime silently degrade service.

**Priority:** Medium — voice is a secondary feature path.

### Endpoint Agent/Discovery

**What's not tested:** The endpoint discovery module, agent lifecycle, and hostname-based AI traffic detection.

**Files:** `src/anonreq/endpoint/`, `src/anonreq/discovery/`

**Risk:** Network-level discovery may miss hosts, generate false positives, or fail to detect AI traffic patterns.

**Priority:** Medium — discovery failures mean unseen AI traffic bypasses policy controls.

### CacheManager Sentinel/Cluster Paths

**What's not tested:** Sentinel and Cluster Redis topology paths. Only standalone Redis is tested via fakeredis.

**Files:** `src/anonreq/cache/manager.py`

**Risk:** Production topology support for HA deployments is unverified. Sentinel failover or Cluster redirection behavior may not match expectations.

**Priority:** Medium — only relevant for production HA deployments.

### Lifespan Startup/Shutdown Sequence

**What's not tested:** The startup sequence in `lifespan()` (`src/anonreq/main.py:242-311`) and shutdown in `_shutdown()` (`src/anonreq/main.py:431-457`). The 11 domain bootstrap functions and their error paths are untested.

**Files:** `src/anonreq/main.py:242-311,431-457`, `src/anonreq/bootstrap/services.py`

**Risk:** Startup/shutdown bugs could cause resource leaks (unclosed DB connections, lingering background tasks) or fail-secure violations.

**Priority:** High — startup/shutdown lifecycle is critical for reliability.

## Missing Critical Features

### No Audit Event Retention Policy (Beyond Config)

**Issue:** `src/anonreq/bootstrap/services.py:204` sets `retention_days=2557` (7 years) for audit chain. There is no automated archival/purge mechanism beyond the config value — it's just metadata stored in the database.

**Files:** `src/anonreq/services/audit_chain.py`, `src/anonreq/bootstrap/services.py:204`

**Problem:** Database grows unbounded. No storage budget enforcement for audit logs.

### No Presidio Circuit Breaker

**Issue:** The `PresidioClient` has a semaphore for concurrency control but no circuit breaker for repeated failures. If Presidio is degraded (responding slowly or with errors), the gateway continues to send requests and accumulate backpressure.

**Files:** `src/anonreq/detection/presidio_client.py`

**Blocks:** Graceful degradation during Presidio partial outages.

---

*Concerns audit: 2026-07-17*
