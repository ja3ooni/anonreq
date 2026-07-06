# Codebase Concerns

**Analysis Date:** 2026-07-06

## Tech Debt

### Broad `except Exception:` Swallowing Errors

**Issue:** 102 instances of bare `except Exception:` across `src/anonreq/`, many followed by `pass` or no re-raise. This pattern silently discards errors across critical subsystems.

**Files:** `src/anonreq/governance/router.py` (6 instances), `src/anonreq/services/breach_detector.py` (6 instances), `src/anonreq/dsar/restriction.py` (5 instances), `src/anonreq/dsar/workflow.py` (6 instances), `src/anonreq/breach/notifications.py` (9 instances), `src/anonreq/soc/buffer.py` (2 instances), `src/anonreq/soc/router.py` (4 instances), and ~70 more across 40+ files.

**Impact:** Critical failures in audit chain storage, breach detection, webhook delivery, DLQ processing, and SIEM forwarding are silently ignored. Operators receive no alert when background operations fail.

**Fix approach:**
- Replace with specific exception types where possible
- At minimum log the exception with `logger.warning()` or `logger.exception()` before `pass`
- For fire-and-forget operations (e.g., `src/anonreq/governance/router.py:95-96`), add structured logging

### Silently Swallowed Webhook Config Load Failure

**Issue:** `src/anonreq/services/breach_detector.py:91-92` — YAML config file loading wrapped in `except Exception: pass`. If the webhook config file is malformed YAML, the breach detector silently falls back to environment variable defaults with no warning.

**Files:** `src/anonreq/services/breach_detector.py:79-92`

**Impact:** Misconfigured webhook settings may go unnoticed until breach notifications fail.

**Fix approach:** Log a warning on config load failure instead of `pass`.

### Hardcoded Default MinIO Credentials in Production Code

**Issue:** Both `src/anonreq/storage/minio.py` and `src/anonreq/services/audit_exporter.py` default to `minioadmin`/`minioadmin` for MinIO access when environment variables are not set.

**Files:** `src/anonreq/storage/minio.py:252-253`, `src/anonreq/services/audit_exporter.py:84-87,107-108`, `docker-compose.yml:141-142`

**Impact:** Default credentials (`minioadmin:minioadmin`) are well-known. Deployments that do not override `ANONREQ_MINIO_ACCESS_KEY`/`ANONREQ_MINIO_SECRET_KEY` have an open MinIO instance with default admin credentials.

**Fix approach:**
- Fail at startup if MinIO credentials are not configured (no default fallback)
- Document required env vars explicitly
- Require credentials via Pydantic Settings validation

### Fire-and-Forget Audit Events with No Error Handling

**Issue:** `src/anonreq/governance/router.py:93-98` — The `_emit_sync` function uses `asyncio.ensure_future()` for fire-and-forget audit events. The `except Exception: pass` inside the async task means audit events are silently dropped.

**Files:** `src/anonreq/governance/router.py:57-98`

**Impact:** Governance action audit events (approvals, denials, risk reassessments) can be lost without any indication to the operator.

**Fix approach:** Log a warning when audit chain storage fails; consider retry or DLQ pattern for critical audit events.

### Httpx.Request Monkey Patch at Module Import Time

**Issue:** `src/anonreq/detection/presidio_client.py:20-26` monkey-patches `httpx.Request.json` at module import time. This modifies a third-party library class globally.

**Files:** `src/anonreq/detection/presidio_client.py:20-26`

**Impact:** Any other module using `httpx.Request.json` gets the patched behavior. If httpx adds a `json` property in a future version, the patch causes a silent override.

**Fix approach:** Use `response.json()` directly instead of patching `Request`. The patch exists because httpx < 0.28 didn't expose `Request.json` — upgrade dependency constraint or handle the response parsing locally.

### Direct Access to Private `_redis` Attribute

**Issue:** `src/anonreq/services/breach_detector.py:66` accesses `cache_manager._redis` directly, coupling the breach detector to the internal implementation of `CacheManager`.

**Files:** `src/anonreq/services/breach_detector.py:66`

**Impact:** Any refactor of `CacheManager`'s internal `_redis` attribute (rename, swap to mock, add connection lifecycle) breaks the breach detector silently.

**Fix approach:** Expose a public `redis` property on `CacheManager` or provide dedicated cache methods for direct Redis operations.

### Over-Mixing os.environ and Pydantic Settings

**Issue:** The codebase reads environment variables via both Pydantic Settings (`settings.X`) and raw `os.environ.get()` in multiple files. This creates two paths for configuration that can diverge.

**Files:** `src/anonreq/deployment/modes.py` (12+ `os.environ` calls), `src/anonreq/providers/registry.py:161-166`, `src/anonreq/storage/minio.py:251-254`, `src/anonreq/providers/ollama.py:43`, `src/anonreq/breach_detector.py:69`, `src/anonreq/services/audit_exporter.py:84-87`

**Impact:** Configuration is scattered. Adding a new config variable requires checking both Pydantic Settings and raw env access. Environment variable defaults defined in `os.environ.get()` calls may conflict with Pydantic Settings defaults.

**Fix approach:** Centralize all configuration in `anonreq.config.settings` (Pydantic Settings). Eliminate raw `os.environ.get()` calls in production code.

## Security Considerations

### PostgreSQL Default Credentials in Docker Compose

**Risk:** `docker-compose.yml:100-101` sets `POSTGRES_PASSWORD: anonreq` (the same as the username). The postgres-exporter also uses `anonreq:anonreq` in its connection string (`line 124`).

**Files:** `docker-compose.yml:100-101,124`

**Current mitigation:** PostgreSQL is behind an internal Docker network (`anonreq-net`), profile-gated to `observability`.

**Recommendations:** Require external `POSTGRES_PASSWORD` env var in compose (use `${POSTGRES_PASSWORD:?err}` pattern) like `ANONREQ_API_KEY` is handled. Document as a required production override.

### Unauthenticated /metrics Endpoint

**Risk:** `src/anonreq/main.py:610-615` — The Prometheus `/metrics` endpoint has no authentication. The comment says "scrapers connect on internal networks; secured at network level."

**Files:** `src/anonreq/main.py:610-615`

**Current mitigation:** Relies on network-level security only.

**Recommendations:** Add optional authentication for `/metrics` or document explicitly that network-level access controls must be configured. If metrics contain any request metadata (even anonymized), it's a data leak vector.

### `presidio-analyzer:latest` and `minio:latest` Tags

**Risk:** `docker-compose.yml:44` and `line 137` use `latest` tags for presidio-analyzer and minio. Builds are non-reproducible — behavior changes silently on image cache invalidation.

**Files:** `docker-compose.yml:44,137`

**Current mitigation:** Specific version tags used for other images (postgres `16-alpine`, prometheus `v2.53.0`, grafana `11.0.0`).

**Recommendations:** Pin presidio-analyzer and minio to specific version tags for reproducible deployments.

### Error Bodies Include Classification Details on 451

**Risk:** `src/anonreq/exceptions.py:321-335` — When returning HTTP 451, the error response body includes classification details (`highest`, `labels`, `reason`). While these are classification labels (not raw PII), they do leak internal policy information that a client could use to probe classification boundaries.

**Files:** `src/anonreq/exceptions.py:321-335`

**Current mitigation:** Only returned on 451 (DLP block) responses. The `reason` field is either the HTTPException detail or a generic message.

**Recommendations:** Consider returning classification details only when an admin-level `X-AnonReq-Debug` header is present, keeping the default 451 envelope generic.

### No Rate Limiting on /v1/admin/ Endpoints

**Risk:** Admin endpoints for config reload, governance records, and oversight have no rate limiting or brute-force protection beyond bearer token auth.

**Files:** Various admin/governance/oversight routes in `src/anonreq/governance/router.py`, `src/anonreq/admin/policy_routes.py`, etc.

**Current mitigation:** Bearer token auth only.

**Recommendations:** Add rate limiting to admin endpoints (can be Valkey-backed). Consider IP-based throttling for failed auth attempts.

## Performance Bottlenecks

### Lazy HTTP Client Initialization in Provider Adapters

**Problem:** Multiple provider adapters (`OpenAIAdapter`, `AnthropicAdapter`, `GeminiAdapter`) create lazy `httpx.AsyncClient` instances on first request. This means the first request to each provider pays connection pool initialization latency.

**Files:** `src/anonreq/providers/openai.py:39-42`, `src/anonreq/providers/anthropic.py:55-59`, `src/anonreq/providers/gemini.py` (similar pattern)

**Cause:** `@property` pattern that creates `httpx.AsyncClient` on first access.

**Improvement path:** Create clients during lifespan startup alongside other initialized services (`src/anonreq/main.py`). Pre-warm connections during pre-flight checks.

### Presidio Request Semaphore Bottleneck

**Problem:** `src/anonreq/detection/presidio_client.py:63` hardcodes `max_concurrency=10` for the Presidio request semaphore. For large payloads with many text nodes, this limits throughput to 10 concurrent Presidio requests.

**Files:** `src/anonreq/detection/presidio_client.py:63`

**Cause:** Hardcoded default, configured only via constructor parameter.

**Improvement path:** Make `max_concurrency` configurable via settings (Pydantic Settings) so operators can tune based on Presidio instance capacity.

### In-Memory Streaming Buffer for SSE Restoration

**Problem:** The streaming restoration pipeline (TailBuffer FSM) buffers partial SSE chunks in memory for split-token matching. Under high-throughput streaming scenarios, memory pressure from buffered chunks could become significant.

**Files:** `src/anonreq/restore/` (streaming restoration)

**Cause:** Necessity of stateful streaming matching — split tokens require buffer-until-complete strategy.

**Improvement path:** Add streaming buffer size limits with configurable max buffer size per stream connection. Emit warning logs when buffer utilization is high.

## Fragile Areas

### Provider Credential Resolution Chain

**Issue:** `src/anonreq/providers/registry.py:161-166` resolves provider API keys via a fallback chain — provider-specific env var, then `settings.PROVIDER_API_KEY`, then `settings.API_KEY`. This means the gateway's own API key can be used as the LLM provider API key.

**Files:** `src/anonreq/providers/registry.py`, `src/anonreq/routing/chat.py:146`

**Why fragile:** If `PROVIDER_API_KEY` and the provider-specific env var are both unset, the gateway's auth key is sent to the LLM provider. An operator may inadvertently reuse the same key value for both gateway auth and provider auth, then change one without the other.

**Safe modification:** Log a warning when falling through to `settings.API_KEY` for provider credentials. Better: require explicit provider credential configuration and fail at startup if missing.

### 848-Line Governance Router Monolith

**Issue:** `src/anonreq/governance/router.py` is 848 lines with 42 route handlers/functions. It mixes route definitions, inline business logic, audit event emission, risk assessment, approval management, and supplier governance.

**Files:** `src/anonreq/governance/router.py` (848 lines)

**Why fragile:** High cognitive load for modifications. Risk of accidental cross-route state coupling. Difficult to unit test individual behaviors without spinning up the full route layer.

**Safe modification:** Extract inline business logic into service classes (e.g., `GovernanceService`, `RiskAssessmentService`). Keep router layer thin — route → service call → response.

### 672-Line main.py Lifespan Context

**Issue:** `src/anonreq/main.py` (672 lines) contains the entire application factory, lifespan context, middleware setup, route registration, and shutdown logic in a single file.

**Files:** `src/anonreq/main.py` (672 lines)

**Why fragile:** The `lifespan` context manager (lines 184-574) initializes ~20 services sequentially. Any failure mid-initialization requires careful cleanup (see the partial cleanup pattern on exceptions). The cleanup/shutdown section (lines 551-574) uses `hasattr` guards on 10+ services.

**Safe modification:** Extract service initialization into a `ServiceRegistry` or `ApplicationContext` class that handles dependency ordering and cleanup. Split lifespan into composable initializer modules.

### Provider Adapter Schema Translation

**Issue:** Provider adapters (`AnthropicAdapter`, `GeminiAdapter`) translate from OpenAI schema to provider-specific schemas and back. These are complex bidirectional mappings with many edge cases (tools, streaming, multi-modal, system messages).

**Files:** `src/anonreq/providers/anthropic.py` (416 lines), `src/anonreq/providers/gemini.py` (390 lines), `src/anonreq/providers/openai.py` (228 lines)

**Why fragile:** Provider API changes (e.g., Anthropic adding new message roles, Gemini restructing content blocks) silently break translation without contract tests. The error normalization layer may mask schema drift.

**Test coverage:** Contract tests exist but may not cover all endpoint variants. Each new model capability (extended thinking, image inputs, tool use v2) requires adapter updates.

### Casual LLM Provider Hostname Detection

**Issue:** `src/anonreq/gateway/detector.py:64-95` uses simple regex patterns to detect AI provider hostnames. Duplicate pattern for `api.openai.com` (lines 66-67), no support for custom/self-hosted providers beyond the hardcoded list.

**Files:** `src/anonreq/gateway/detector.py:64-106`

**Why fragile:** New providers require code changes. Custom deployments (e.g., on-prem Azure OpenAI) may use non-standard hostnames. Pattern match order is implicit.

## Scaling Limits

### Single-Process Event Loop

**Current capacity:** Single uvicorn worker, single asyncio event loop.

**Limit:** Under high concurrent request load, all request handling (Presidio calls, provider calls, streaming, audit) contends on one event loop. Long-running streaming connections block event loop responsiveness.

**Scaling path:** Add `uvicorn` worker count configuration. Consider dedicated connections for streaming vs. non-streaming traffic. Evaluate moving Presidio calls to a thread pool executor.

### In-Memory Token Mapping

**Current capacity:** Token mappings stored in Valkey with TTL-based eviction. No fallback for Valkey outage beyond fail-secure 503.

**Limit:** Cache key space grows linearly with request volume. TTL of 60-3600s means mappings for long-running sessions may expire before restoration completes.

**Scaling path:** Add local in-memory LRU cache as L1 with Valkey as L2. Implement mapping persistence (encrypted) for long-running agent sessions.

## Dependencies at Risk

### presidio-analyzer (unpinned version)

**Risk:** `docker-compose.yml:44` uses `mcr.microsoft.com/presidio-analyzer:latest`. Breaking changes in Presidio Analyzer image can break detection pipeline without warning.

**Impact:** Gateway starts successfully (no pre-flight contract test against Presidio API shape), but detection fails silently or returns unexpected results.

**Migration plan:** Pin to a specific major version tag (e.g., `:2.2.35` or newer). Add Presidio API contract tests to pre-flight checks.

### httpx Monkey-patch Dependency

**Risk:** `src/anonreq/detection/presidio_client.py:20-26` depends on `httpx.Request` not having a `json` property. A minor httpx version bump could add this and break the patch.

**Impact:** `AttributeError` on `PresidioClient.analyze()` — breaks detection pipeline.

**Migration plan:** Pin httpx to a specific minor version or remove the monkey patch entirely by using `response.json()` for response parsing.

### onnxruntime + openai-whisper Dependencies

**Risk:** `pyproject.toml:39-40` includes `onnxruntime` and `openai-whisper` as core dependencies. These are large (~500MB combined with CUDA deps) and only needed for the voice pipeline (speech-to-text), which is a secondary feature.

**Impact:** Docker image bloat. CI/CD pipeline time increases. Potential build failures on ARM64 (Apple Silicon) for onnxruntime without `--extra-index-url`.

**Migration plan:** Move voice dependencies to an optional extras group (e.g., `[voice]`). Document that voice features require additional build steps.

## Test Coverage Gaps

### Governance Router Routes

**What's not tested:** The 42 route handlers in `src/anonreq/governance/router.py` (848 lines) — inline business logic for risk assessment, approval management, and supplier governance.

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

## Missing Critical Features

### No Audit Event Retention Policy (Beyond Config)

**Issue:** `src/anonreq/main.py:371` sets `retention_days=2557` (7 years) for audit chain. There is no automated archival/purge mechanism beyond the config value — it's just metadata stored in the database.

**Files:** `src/anonreq/services/audit_chain.py`, `src/anonreq/main.py:371`

**Problem:** Database grows unbounded. No storage budget enforcement for audit logs.

### No Presidio Circuit Breaker

**Issue:** The `PresidioClient` has a semaphore for concurrency control but no circuit breaker for repeated failures. If Presidio is degraded (responding slowly or with errors), the gateway continues to send requests and accumulate backpressure.

**Files:** `src/anonreq/detection/presidio_client.py`

**Blocks:** Graceful degradation during Presidio partial outages.

---

*Concerns audit: 2026-07-06*
