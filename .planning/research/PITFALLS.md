# Domain Pitfalls: LLM Anonymization Proxy Gateway

**Domain:** Self-hosted PII anonymization gateway intercepting LLM API calls
**Researched:** 2026-06-19
**Overall confidence:** HIGH

## Critical Pitfalls

Mistakes that cause rewrites, data exposure, or major production incidents.

---

### Pitfall C1: PII Leak Through Exception Handlers

**What goes wrong:** An unhandled exception in the request pipeline (Presidio timeout, JSON decode failure, provider HTTP error) is caught by a generic FastAPI exception handler that logs the full traceback — including the raw request body containing PII. The exception handler then returns a 500 with the traceback in the response body to the caller. PII is now in both the logs and the external response.

**Why it happens:**
- FastAPI/Starlette's default exception handlers are verbose and may include request bodies in debug output
- Developers add `logger.exception()` in catch blocks without sanitizing — the traceback captures local variables including request payload
- The `traceback.format_exc()` call in middleware captures function arguments and local variables that contain raw PII
- During initial development, `DEBUG=true` is left enabled in production, exposing full stack traces in HTTP responses

**Consequences:**
- PII permanently stored in log aggregation systems (Splunk, Datadog, ELK) — these become secondary data stores requiring their own compliance
- PII may cross the network boundary in the HTTP response body sent to the caller
- GDPR Article 33 breach notification obligation triggered — reportable to DPA within 72 hours
- Legal liability: PII in operational tooling accessible to DevOps/SRE teams who have no legitimate need to see it

**Prevention:**
- Implement a single top-level exception handler that returns HTTP 500 with a static, generic error body — never includes request content, stack traces, or Token values
- Use a structured-log field allowlist (Req 10, AC4): strip any log field not on the allowlist before writing
- Wrap all `logger.exception()` calls in a sanitization layer that redacts known sensitive key patterns (`request_body`, `prompt`, `messages`, `content`)
- Run the gateway with `DEBUG=false` in all environments except local dev; CI should fail if `DEBUG=true`
- Property-based test verifying the no-PII-in-logs invariant (Req 16, AC6) — run this against the exception handler path specifically

**Detection:**
- Monitor the `anonreq_fail_secure_events_total` counter — a spike in 5xx responses followed by a spike in log volume may indicate a leak
- Deploy a PII scanner over log output (periodic scan of log samples using Presidio itself against log store)
- Test: inject known PII values into the pipeline, trigger an exception (e.g., by killing Presidio), then assert the log output contains zero PII substrings

**Phase to address:** Phase 1 (Core Gateway) — the exception handler middleware is part of the initial FastAPI setup. The no-PII-in-logs property test (Req 16, AC6) must be built in Phase 2 (Testing) and pass before any production deployment.

---

### Pitfall C2: Presidio False Positives on Business Terminology

**What goes wrong:** Presidio's regex recognizers flag business-critical terms, product identifiers, or internal codes as PII. Credit-card-like account numbers, 9-digit employee IDs matched by the US driver's license recognizer, or IBAN-like internal reference numbers trigger tokenization. The LLM receives mangled prompts with business terminology replaced by `[PHONE_NUMBER_3]` and produces nonsensical responses.

**Why it happens:**
- Presidio's off-the-shelf recognizers use broad regex patterns with high confidence: the US driver's license recognizer matches any 9-digit number with a confidence of 1.0 if context words are present (Presidio issue #1071 documents this pattern)
- The IBAN recognizer matches any string matching the IBAN format, even if it's an internal reference code
- Checksum validation for credit cards (Luhn) runs _before_ context word scoring — a random 16-digit sequence that passes Luhn gets a confidence of 1.0 regardless of surrounding text
- Alvaro et al. (2024) found Presidio achieves only 22.7% precision on real-world business datasets with mixed languages
- The `allkeys-lru` eviction policy in Valkey works against session data: if memory pressure is high, early sessions' mappings get evicted while their streams are still in flight

**Why it happens (exclusion list gap):**
- The Exclusion_List (Req 11) is loaded at startup but the hot-reload (60s window) creates a gap: between file modification and atomic swap, a newly deployed product name triggers a false positive
- Exclusion_List matching uses NFKC normalization + case-folding, but wildcard patterns like `GraphAPI.*` may not cover all format variants (e.g., `graph-api-v2`)

**Consequences:**
- LLM produces incorrect or incoherent responses because business terms have been replaced with unrelated token types
- Developer trust in the gateway is destroyed — teams start bypassing it
- False positives become a critical support burden ("why does my prompt always break on this account code?")
- False tokenization of identifiers may cause downstream processing errors (hash lookups fail, API calls to internal services break)

**Prevention:**
- Ship a comprehensive Exclusion_List seed file with known false-positive patterns for common business domains
- Implement multi-stage detection: NER first, regex second, with regex confidence penalized when no PII-relevant context words are nearby (override Presidio's scoring order)
- Use the custom recognizer system (Req 11) to register domain-specific patterns as _recognizers with lower confidence_ rather than as exclusion list items — this preserves detection but reduces false positive rate
- Set conservative Confidence_Thresholds per entity type (default 0.85 for structured types, 0.95 for weak patterns like driver's license)
- Add a per-tenant false-positive feedback loop: allow operators to mark false positives via API, which auto-adds to an exclusion list override

**Detection:**
- Monitor `anonreq_entities_detected_total` by entity type — a sudden spike in `DRIVER_LICENSE` or `CREDIT_CARD` detections after a new product deployment is a red flag
- Deploy a canary endpoint that processes known-safe prompts and alerts if entities are detected
- Build a CI step that runs Presidio against a corpus of known business terminology and asserts zero detections

**Phase to address:** Phase 1 (Core Gateway) for Exclusion_List and Confidence_Threshold defaults. Phase 3 (Multilingual & Customization) for the false-positive feedback loop. Phase 2 (Testing) for regression tests against business terminology corpus.

---

### Pitfall C3: Premature Cache Eviction During Long LLM Streams

**What goes wrong:** An LLM streaming response takes longer than the configured TTL (default 300 seconds). The Cache_Manager evicts the `anonreq:{Session_ID}` key mid-stream. The Restoration_Engine's pre-fetched local copy of the Mapping still works for tokens it already has, but any new tokens arriving that reference indices not in the pre-fetched copy (e.g., if the Mapping was partially written before eviction, or if the stream includes restored tokens that happen to match values in the evicted portion) fail to resolve. The stream delivers unreplaced `[NAME_3]` tokens to the end user.

**Why it happens:**
- The TTL extension mechanism (Req 5, AC6) triggers at 80% of configured TTL, but if the stream pauses (provider rate limit, network stall), the TTL may expire before the extension fires
- The extension is a single `EXPIRE` command — if Valkey is under memory pressure with `allkeys-lru` policy, LRU eviction can remove a key even if its TTL hasn't expired
- The initial Mapping `HMSET` + `EXPIRE` is not atomic in Redis/Valkey — a race exists between the SET and the EXPIRE where eviction could occur on a transient key
- The Mapping write for a streaming request is a single `HMSET` before the stream begins — but if the Mapping is very large (many detected entities), the write takes measurable time, during which the key is visible but partially written

**Consequences:**
- End users see raw `[TYPE_N]` tokens in LLM responses (compliance red flag — proves the gateway can leak its internal state to users)
- The post-stream Token verification scan (Req 13, AC3) catches unreplaced Tokens and logs a warning, but the response is already delivered — the user has seen the artifact
- Support escalations spike: customers see placeholder tokens in production

**Prevention:**
- Use `SET` with `EX` (or `SETEX`) for atomic key creation + TTL in a single command — eliminates the race between write and expiration
- Set a much longer base TTL (e.g., 7200 seconds = 2 hours) for streaming sessions specifically, with fast explicit `DEL` on stream completion — this makes TTL expiration a safety net, not the primary deletion mechanism
- Implement a periodic TTL refresh heartbeat during streaming: on every Nth SSE chunk, extend the TTL by the session TTL value (not just at 80% threshold)
- Use `volatile-lru` eviction policy instead of `allkeys-lru` — this restricts LRU eviction to keys that have TTLs, preventing Valkey from evicting keys that haven't expired yet under memory pressure
- Pre-fetch the complete Mapping as a local dictionary before stream start (Req 6, AC2 already requires this), but also add a defensive fallback: if a Token lookup fails in the local copy, attempt a cache read before leaving it unresolved

**Detection:**
- Monitor `anonreq_tokens_unrestored_total` counter — any non-zero value for streaming sessions needs immediate investigation
- Add a Prometheus gauge `anonreq_cache_key_ttl_seconds` tracking remaining TTL for active sessions
- Alert on `HGETALL` latency > 50ms (indicates Valkey under memory pressure that could lead to eviction)

**Phase to address:** Phase 1 (Core Gateway) — Cache_Manager implementation must use atomic SETEX and volatile-lru. Phase 6 (Performance) for TTL heartbeat optimization.

---

### Pitfall C4: Token Split Across SSE Chunk Boundary

**What goes wrong:** An LLM response contains `[NAME_1]` but the streaming provider sends `[NAME_` in chunk N and `1]` in chunk N+1. The Restoration_Engine's simple substring search fails to match the split pattern. The Tail_Buffer accumulates `[NAME_` but the completion arrives in a subsequent chunk. The final output delivered to the client contains `[NAME_1]` — an unreplaced Token.

**Why it happens:**
- LLM tokenization does not respect user-defined token boundaries — the model may emit `[NAME_` as a single byte sequence or split across its own tokenization boundaries
- The SSE protocol delivers chunks as they are generated at the provider's discretion — no guarantee of alignment with semantic units
- The Tail_Buffer (Req 6, AC3) is limited to 512 characters — if the partial prefix at the boundary exceeds this, the buffer silently truncates and the split is unrecoverable
- Case-insensitive and bracket-optional matching (Req 6, AC4-5) compounds the problem: `[name_` in chunk N and `1]` in chunk N+1 requires the matcher to handle three-way variation (case, brackets, split) simultaneously

**Consequences:**
- Token leaks through to end users as raw placeholder text — same compliance impact as Pitfall C3
- The post-stream verification scan detects the unreplaced Token and logs it, but the response is already delivered
- Intermittent and non-deterministic — only occurs with specific LLM outputs and specific chunk boundary alignments, making it nearly impossible to reproduce in testing

**Prevention:**
- Extend the Tail_Buffer to check partial matches _prefix-first_: buffer the last N characters (N = max token length + safety margin) and scan for partial Token prefixes (`[NAME_`, `[EMAIL_`, `NAME_`, etc.) after every chunk
- Use a generalized partial-token FSM (finite state machine) rather than a static buffer: track potential partial matches by comparing the suffix of the current chunk against all known Token prefixes from the Mapping
- Implement bracket-optional matching at the chunk boundary level: if a chunk ends with a partial Token prefix, strip the incomplete suffix into the buffer and re-emit it only after the next chunk completes or times out (Req 6, AC6 flush condition)
- Add a post-stream retry pass: if unreplaced Tokens are detected after stream end, attempt an offline re-scan of the assembled text with relaxed matching (case-insensitive, bracket-optional, split-aware)

**Detection:**
- `anonreq_tokens_unrestored_total` with label `reason=split_token` must be instrumented separately from other restoration failures
- During testing, use the streaming round-trip property test (Req 16, AC7) that splits Tokens at every possible index — this is the primary detection mechanism
- In production, sample streaming sessions for post-hoc analysis: reassemble the raw SSE chunks as received and check for Token artifacts

**Phase to address:** Phase 1 (Core Gateway) — the Restoration_Engine and Tail_Buffer are core components. The FSM-based partial match logic must be part of the initial implementation because retrofitting it later requires changing the streaming pipeline architecture.

---

### Pitfall C5: Provider Schema Translation Incompatibility — Silent Data Loss

**What goes wrong:** The Provider_Adapter translates an OpenAI schema request to Anthropic's Messages API format. During translation, a `system` message with `name` field (OpenAI supports named system messages) is dropped because Anthropic's API doesn't support named system prompts. The response is anonymized and restored correctly from the Anthropic perspective, but the LLM's behavior is subtly different because it never received part of the system prompt.

**Why it happens:**
- Schema translation (Req 7, AC2-4) is inherently lossy: provider schemas overlap in intent but diverge in expressiveness
- OpenAI's `messages` array supports: `system` (with optional `name`), `user` (with `name`, `content` array), `assistant` (with `name`, `tool_calls`, `function_call`), `tool` (with `tool_call_id`), `function` (legacy)
- Anthropic's Messages API supports: `system` (top-level parameter, no `name`), `user` (with `content` array), `assistant` (with `content` array)
- Gemini's API supports: `contents[]` with `role` (user/model/function) and `parts[]`
- Differences that cause silent drops: `name` field on messages (OpenAI → Anthropic loses identity), multiple system messages (OpenAI allows, Anthropic concatenates), tool call results with multiple parts, refusal messages (OpenAI has `refusal` field, no other provider equivalent)
- The risk is not in the happy path translation — it's in the edge cases that the adapter developer didn't know about

**Consequences:**
- LLM produces wrong answers because context was silently dropped during translation
- The audit log shows "entities anonymized: 0" and a successful response — no indication that data was lost
- Debugging is extremely difficult because the translation is a black box: the gateway's internal representation matches the source schema, but the wire format to the provider is different
- Fail-secure translation property (Req 7, AC10) only catches adapter crashes, not semantic loss

**Prevention:**
- Implement a schema completeness check: for each provider translation, log a warning when a field or property from the source schema has no equivalent in the target schema — this makes silent drops visible
- Add a test suite with all known schema variations from each provider: named messages, multi-system messages, refusal content, function-calling with empty arguments, tool calls with zero tools
- For fields that cannot be translated, inject the information into the system prompt as an annotation (e.g., append "Note: the original message from user 'Alice' was..." when the `name` field is dropped)
- Create a provider capability matrix documented in `PROVIDER_CAPABILITIES.md` that lists which OpenAI schema features each provider supports, and return HTTP 400 with a clear error message when a client requests a feature the target provider cannot support

**Detection:**
- Run the "round-trip with translated schema" test: send a request to the adapter, capture the wire-format payload sent to the provider, and verify it preserves all semantic content from the original request
- Version the adapter translation logic and add CI checks that compare output against known-good snapshots
- Add integration tests with real provider sandboxes (OpenAI/Anthropic/Gemini free-tier accounts) that verify the LLM's behavior is consistent across providers for the same anonymized prompt

**Phase to address:** Phase 1 (Core Gateway) — Provider_Adapter is a core module. The capability matrix and semantic-preservation tests must be implemented alongside the adapter, not as an afterthought.

---

### Pitfall C6: Presidio Latency Blows the 100ms Processing Budget

**What goes wrong:** A prompt containing 1,000+ words with multiple languages triggers NER processing across all loaded spaCy models (one per locale). Presidio's `analyze()` call takes 600ms-3s for the full pipeline. The gateway's 100ms p95 processing overhead target (Req 1, AC9) is violated on the very first request. Every request is delayed, the proxy becomes a bottleneck, and applications time out waiting for the gateway.

**Why it happens:**
- Presidio's AnalyzerEngine loads the full spaCy pipeline (`en_core_web_lg` by default, ~500MB model) plus locale-specific models. The first `analyze()` call includes lazy-loading overhead
- The NER model's inference time scales roughly linearly with text length and quadratically with the number of loaded recognizers — each recognizer runs pattern matching against the full text
- The PhoneRecognizer is particularly slow (uses multiple regex patterns across international formats)
- When multiple locale recognizer bundles are active (Req 8, AC5), the Detection_Engine runs all matching recognizers sequentially — O(n * m) where n = recognizers, m = text length
- The Docker Compose setup runs Presidio as a separate container — each HTTP call from the Gateway to Presidio adds network round-trip time (~1-5ms localhost) plus serialization overhead for the response
- spaCy model initialization on container startup takes 5-15 seconds, contributing to slow health-check pass

**Consequences:**
- The 100ms SLO is impossible to meet — every request violates it
- Client applications configure their own timeouts (typically 5-10s for LLM calls), and the gateway adds unacceptable overhead
- The gateway is blamed for "being slow" and teams bypass it, defeating the entire compliance purpose
- The Presidio container itself may become a bottleneck under load, queuing requests and increasing latency non-linearly

**Prevention:**
- Use `en_core_web_sm` (small spaCy model) instead of `en_core_web_lg` — reduces NER latency from ~200ms to ~20ms per 1K tokens at the cost of some recall. Presidio maintainers confirmed this is the fastest setup (GitHub discussion #1097)
- Pre-cache the NLP model by calling `analyzer.analyze("warmup", language="en")` during startup — avoids first-request cold-start penalty
- Split detection into two tiers: (1) fast regex-only pre-scan (sub-millisecond) for high-confidence structured entities, (2) full NER scan only if regex scan finds entities or the prompt has no structured content — this avoids NER for the common case of "no PII present"
- Cache the AnalysisEngine instance (singleton) — don't create a new one per request
- For multi-locale detection, run locale recognizers in parallel using asyncio.gather — Presidio's AnalyzerEngine is thread-safe for concurrent calls
- Implement prompt truncation scanning: for prompts exceeding a configurable word limit, sample the first N words and last N words rather than scanning the full text (heuristic: most PII appears in message boundaries, not middle content)
- Add a detection timeout middleware: if `analyze()` exceeds 95ms, cancel and fall through to fail-secure (HTTP 504 per Req 2, AC4)

**Detection:**
- `anonreq_detection_latency_seconds` histogram will show p95 exceeding 100ms immediately
- Compare `anonreq_detection_latency_seconds` across locale combinations — `ar-*` with NER models for Arabic script is typically 2-3x slower than English
- Monitor Presidio container CPU usage: sustained >1vcpu per request indicates NER bottleneck

**Phase to address:** Phase 1 (Core Gateway) — must select the right spaCy model and parallelize recognizers from the start. Phase 6 (Performance) for prompt truncation and optimization work.

---

## Moderate Pitfalls

---

### Pitfall M1: Client Disconnect Leaves Upstream Provider Stream Running

**What goes wrong:** A user closes their browser tab mid-stream. The Gateway detects the client disconnect (via `request.is_disconnected()` or a write error), but the upstream HTTP connection to OpenAI/Anthropic/Gemini continues running. The provider finishes generating the full response and bills for all output tokens. At 1,000 requests/second with a 5% client-drop rate and 500 average output tokens, this wastes ~25,000 tokens/second — potentially hundreds of dollars/day.

**Why it happens:**
- FastAPI's `StreamingResponse` and Starlette's `Request.is_disconnected()` detection is async and cooperative — the generator must yield to detect a disconnect. If the generator is blocked on reading from the upstream provider, it never checks for disconnect
- The provider's SDK doesn't receive a cancellation signal unless the underlying HTTP request context is cancelled
- Python's asyncio task cancellation (`CancelledError`) is only raised when `await` yields to the event loop — a tight sync loop in the generator can't be cancelled
- The default `httpx.AsyncClient` (used by OpenAI SDK) does not automatically cancel requests when the response iterator is abandoned

**Consequences:**
- Wasted spend on tokens that were generated but never delivered
- Inflated provider bills with no corresponding user benefit
- The disconnect is invisible in standard metrics — the request appears successful from the gateway's perspective

**Prevention:**
- Pass the HTTP request context (`request.scope['asgi']['spec_version']` yields the ASGI disconnect channel) to the upstream provider call and explicitly cancel the upstream request on disconnect
- Use `asyncio.create_task` with cancellation: wrap the upstream stream iterator in a task and cancel it on client disconnect
- In the SSE generator, after each `await` on the upstream read, check `if await request.is_disconnected()` and break + cancel the upstream context
- Implement a maximum idle timeout per stream chunk: if no data arrives from the upstream provider within 60 seconds (configurable), close the stream and emit a partial-response warning
- Add a `X-AnonReq-Stream-Cancelled: true` header to the response when early termination occurs due to disconnect (so clients can differentiate from errors)

**Detection:**
- Create a Prometheus counter `anonreq_stream_client_disconnects_total` — track rate per provider
- Compare upstream provider token usage (from provider API billing) vs. gateway-delivered tokens — large discrepancies indicate upstream leaks
- Add structured log events with `event_type: stream_cancelled_disconnect` and `session_id`

**Phase to address:** Phase 1 (Core Gateway) — disconnect handling must be built into the SSE streaming pipeline, not added later. The architecture requirement to propagate context cancellation to upstream providers is a fundamental design decision.

---

### Pitfall M2: Cache Key Collision Under Concurrent Requests

**What goes wrong:** Two concurrent requests from the same client or different clients generate the same Session_ID (UUID collision, or deterministic Session_ID from a bug in random generation). The second request's Mapping overwrites the first's in the Cache_Manager. When the first request's response arrives, its Tokens resolve to the second request's values — or fail to resolve entirely because the Mapping has changed.

**Why it happens:**
- Session_ID is generated with `uuid.uuid4()` (Python's UUID4 from `random` module before Python 3.9, or from `os.urandom` after) — but if the application is forked (e.g., uvicorn workers with `--workers N`), all workers share the same random seed if not properly reseeded after fork
- `uuid.uuid4()` before Python 3.9 used `random.randrange()` which was seeded from system time — collisions possible under rapid fork
- Even with cryptographically secure UUID4, the key namespace `anonreq:{Session_ID}` is only 128 bits — theoretical collision at scale is negligible, but a non-crypto random source (e.g., `random.randint` for "simplicity" in early development) creates collision risk
- The `anonreq:{Session_ID}` key prefix has no tenant scope — if multi-tenancy is added later (Req 17+), keys from different tenants can collide

**Consequences:**
- Cross-request data leakage: Request A's response contains Request B's original PII values (because B's Mapping overwrote A's)
- This is a _data breach_ — PII from one request leaks into another's response
- Extremely difficult to detect because it's non-deterministic and rare with proper UUID4

**Prevention:**
- Use `secrets.token_hex(32)` (64-character hex string from OS entropy) instead of UUID for Session_ID — 256 bits of entropy eliminates collision risk
- After process fork (uvicorn workers), re-seed the random module by calling `import random; random.seed()` in each worker's startup
- Namespace keys with `tenant_id` when multi-tenancy is active: `anonreq:{tenant_id}:{session_id}`
- Add a cache write check: before writing a Mapping, check if the key already exists. If it does, generate a new Session_ID and retry (fail-safe collision handling)
- Implement key-level locking: use Redis/Valkey `SETNX` with the Session_ID as a lock before writing the Mapping — if another request holds the lock, treat as collision

**Detection:**
- Monitor Redis/Valkey key overwrites: run `INFO keyspace` and track `expired_keys` vs `evicted_keys` — a sudden change may indicate key collision
- Add a Prometheus counter `anonreq_cache_key_collisions_total` that increments when `SETNX` fails or when a pre-write collision check finds an existing key
- Property-based test: generate 100K Session_IDs and assert zero duplicates (Req 16 implicitly covers this through uniqueness invariants)

**Phase to address:** Phase 1 (Core Gateway) — the Cache_Manager implementation must enforce key uniqueness from day one. Retrofitting tenant namespacing later requires migrating all active sessions.

---

### Pitfall M3: Unicode Normalization Mismatch in Token Deduplication

**What goes wrong:** A prompt contains the same name written in two Unicode forms: composite (e.g., `é` as U+00E9) and decomposed (e.g., `e` + U+0301). The Detection_Engine flags both as PII (correctly) but Tokenization_Engine compares them byte-for-byte (Req 4, AC2) and treats them as different values. The output contains `[NAME_1]` for the first occurrence and `[NAME_2]` for the second — even though they are the same name. The LLM receives two different tokens for the same entity, breaking the deduplication invariant.

**Why it happens:**
- Unicode normalization has four forms: NFC (canonical composite), NFD (canonical decomposed), NFKC (compatibility composite), NFKD (compatibility decomposed)
- Req 4, AC2 specifies NFC normalization for byte-for-byte comparison — but the Detection_Engine's regex recognizers may or may not normalize text before matching, depending on the regex pattern and the spaCy tokenizer
- Python's `unicodedata.normalize('NFC', text)` and C++ implementations (in spaCy) may produce different results for edge cases (e.g., Hangul syllables, CJK compatibility characters)
- The Exclusion_List comparison uses NFKC (Req 11, AC4) — but NFKC can merge characters that NFC keeps separate (e.g., ﬁ ligature → fi), creating a mismatch between exclusion list matching and token deduplication

**Consequences:**
- The deduplication invariant (Req 4, AC8) is violated: same entity value → different Tokens
- The LLM sees `[NAME_1]` and `[NAME_2]` for what should be the same person — may affect reasoning about identity and relationships
- Round-trip correctness (Req 16, AC1) still holds because restoration maps each Token back to its original string, but the _semantic_ round-trip is broken: the LLM received different tokens for the same entity

**Prevention:**
- Normalize all input text to NFC at the HTTP request boundary _before_ any processing — the Detection_Engine, Tokenization_Engine, and Exclusion_List all operate on NFC-normalized text
- Apply NFC normalization to all regex patterns that detect PII — normalizing patterns and text ensures consistency
- Use NFC everywhere consistently: `unicodedata.normalize('NFC', text)` in the Gateway's request middleware, and configure spaCy to use NFC in its tokenizer
- Add a property-based test that generates Unicode text with mixed normalization forms and asserts the deduplication invariant holds (this is a bug farm: combos like é, ñ, ü, CJK, emoji sequences)
- Document the normalization strategy in `docs/architecture/unicode-handling.md` so future developers don't introduce inconsistent normalization

**Detection:**
- Add a Prometheus counter `anonreq_unicode_normalization_events_total` for texts that had different normalization than expected
- Run the deduplication property test (Req 16, AC3) with Unicode strategy that generates NFC/NFD variants of the same character sequence
- In production, sample requests and log the detected normalization form (but not the sensitive values)

**Phase to address:** Phase 1 (Core Gateway) — request normalization middleware. Phase 2 (Testing) — property tests with Unicode strategies.

---

### Pitfall M4: Mid-Stream Provider Error After HTTP 200

**What goes wrong:** The Gateway receives a streaming response from OpenAI. The HTTP status code is 200, so the Gateway begins forwarding SSE events to the client. Mid-stream, OpenAI hits an internal rate limit or server error. The provider closes the connection with a truncated stream — no `[DONE]` sentinel, no error event. The client receives an incomplete response that looks like a clean response (HTTP 200 is already committed). The Gateway has no mechanism to communicate failure retroactively.

**Why it happens:**
- HTTP status codes are sent before the response body — once `200 OK` is written, neither the Gateway nor the upstream provider can change it
- Provider APIs may return 200 with partial content on internal errors — this is technically correct from HTTP perspective but semantically wrong
- OpenAI's API documentation warns that streaming responses may end abruptly if the model hits a content filter or rate limit
- The SSE protocol has no mechanism for mid-stream error signaling (it's a one-way protocol) — providers use in-band error events in `data:` payloads, but not all do this consistently

**Consequences:**
- Client receives a partial response with no error indication — may cache it, display it, or act on incomplete information
- The Gateway's audit log shows success (200 was returned to client) — the error is invisible in metrics
- The client retries a request that was already partially charged — double billing

**Prevention:**
- Send an in-band error SSE event before closing the stream on upstream disruption: `data: {"error": {"code": "upstream_stream_interrupted", "message": "Upstream provider closed connection mid-stream"}}\n\n`
- Document in the API integration guide that clients must check for error keys in _every_ SSE `data:` payload, not just the HTTP status code
- Set `stream_options: {"include_usage": true}` on OpenAI requests — the final usage chunk before `[DONE]` serves as a stream-completeness signal; its absence indicates truncation
- Implement a stream completeness check: if the stream ends without `[DONE]` or a usage chunk, flag it as truncated in audit logs and metrics
- Add a configurable stream timeout: if no SSE event arrives within N seconds (default 120), close the stream and flag it as incomplete

**Detection:**
- `anonreq_requests_total` label mismatch between `status=200` and count of streams that ended with `[DONE]`
- Add `anonreq_stream_truncated_total` counter — monitor baseline rate per provider
- Compare average completion token count across providers — an unusually low average for a provider may indicate truncation

**Phase to address:** Phase 1 (Core Gateway) — in-band error signaling is part of the SSE streaming pipeline. Phase 2 (Testing) — integration tests that simulate mid-stream provider failures.

---

### Pitfall M5: Presidio Hot-Reload Race Condition

**What goes wrong:** An operator updates the custom recognizer YAML file while the gateway is processing requests. The hot-reload mechanism (Req 11, AC6) detects the file change and atomically swaps the recognizer registry. However, an in-flight request started before the swap holds a reference to the old registry. The swap completes, the new registry is active, but the in-flight request's `analyze()` call runs partially with old recognizers and partially with new — detection results are inconsistent.

**Why it happens:**
- Presidio's `AnalyzerEngine` holds an internal `Registry` that stores all recognizers. The engine instance is created once at startup and reused across requests
- The atomic swap (Req 11, AC6) replaces the registry reference with a new one, but in-flight requests that have already started `analyze()` may still hold a reference to the old registry's data
- If the hot-reload modifies an entity type's confidence threshold, two concurrent requests started within the 60-second reload window may see different thresholds for the same entity
- The Exclusion_List hot-reload has the same issue: a request that starts Pre-Swap and finishes Post-Swap may have used the old exclusion list during detection but the new exclusion list during post-processing

**Consequences:**
- Non-deterministic detection results: the same prompt may produce different tokenization output depending on whether it arrived before or after a hot-reload
- Debugging becomes impossible — support engineers can't reproduce detection behavior because the configuration changed between observations
- Audits may flag inconsistent anonymization of similar prompts as a control failure

**Prevention:**
- Implement a generation counter on the registry: each hot-reload increments the generation number. Each request captures the generation at the start of detection and logs it in the audit entry — enables detection-pattern analysis by config version
- Use a copy-on-write pattern: the recognizer registry is immutable once created; hot-reload creates a new registry and the old one remains reachable until all in-flight requests referencing it complete
- For the Exclusion_List, apply filtering at the Tokenization_Engine level (not the Detection_Engine level): the Detection_Engine always returns all entity candidates above threshold, and the Tokenization_Engine applies the Exclusion_List as a post-filter using the generation-consistent version
- Add a minimum hot-reload interval (default 30 seconds): rapid successive changes are batched into a single atomic swap

**Detection:**
- Monitor `anonreq_config_reload_total` counter — a spike in reload events increases the probability of mid-reload races
- In audit logs, include the `config_generation` field — dashboard queries for "same prompt, different config_generation → different entity counts" flag the problem

**Phase to address:** Phase 3 (Multilingual & Customization) — hot-reload logic is part of the custom recognizer system. Phase 2 (Testing) — concurrent reload + request tests.

---

### Pitfall M6: E.164 Phone Numbers Overlapping with Other Number Formats

**What goes wrong:** A prompt contains a number that matches both the `PHONE_NUMBER` recognizer (E.164 format: `+1-212-555-0198`) and the `CREDIT_CARD` recognizer (a contiguous digit substring that passes Luhn). The Detection_Engine produces overlapping entity spans, resolves the conflict (Req 3, AC3 — regex wins over NER), and tokenizes the phone number. But the phone number contains a digit sequence that happens to pass Luhn validation, causing the credit card recognizer to also fire at high confidence. The conflict resolution picks the wrong entity type, and the phone number is labeled as `[CREDIT_CARD_1]` instead of `[PHONE_NUMBER_1]`.

**Why it happens:**
- E.164 phone numbers can contain digit sequences that match other recognizers: `+1 (800) 424-5454` (US IRS phone) contains `4245454` which is Luhn-valid for some checksum algorithms
- Cross-provider numbers (e.g., German service hotlines) may match local ID patterns
- Req 3, AC3 mandates regex wins over NER for overlapping spans, but when two regex recognizers overlap, the conflict resolution depends on the order recognizers are registered — which is an implementation detail
- Presidio's default recognizer ordering is alphabetical by entity type, not semantic priority

**Consequences:**
- Wrong entity type in the response output: `[CREDIT_CARD_1]` is semantically incorrect for a phone number
- The LLM may misinterpret the token type — if it knows `[CREDIT_CARD_1]` represents a financial instrument, it handles the token differently than a contact number
- Audit logs show the wrong entity type, skewing PII classification reports
- False positive `CREDIT_CARD` detection triggers compliance alerts unnecessarily

**Prevention:**
- Implement a definite overlap prioritization matrix: when two regex recognizers overlap, prioritize by an explicit `priority` field in the recognizer configuration (phone > credit card > national ID > generic number)
- For phone numbers: prefer E.164 pattern match if the number starts with `+` — this is unambiguous and should always win
- Add an overlap resolution pass that considers the _nature_ of the overlap: if a CREDIT_CARD entity is entirely contained within a PHONE_NUMBER entity, the phone number context takes precedence
- Configure entity-type-specific confidence operators: for PHONE_NUMBER, require the `+` prefix or country code context to reach the default confidence threshold

**Detection:**
- Run a domain-specific corpus through the gateway and manually audit entity type assignments — particularly for prompts containing phone numbers + codes
- Add a CI test that feeds known phone numbers and asserts they are never classified as CREDIT_CARD or NATIONAL_ID

**Phase to address:** Phase 1 (Core Gateway) — overlap prioritization matrix in the Detection_Engine. Phase 2 (Testing) — entity-type accuracy tests.

---

### Pitfall M7: The LLM Rephrases or Mutates Tokens in Its Response

**What goes wrong:** The anonymized prompt sent to the LLM contains `[NAME_1]` for "John Smith." The LLM's response includes the name but in a different form: "John S.", "J. Smith", "John" (without surname), or "Mr. Smith". The Restoration_Engine cannot match any of these variants to the original `[NAME_1]` token because the LLM invented new forms. The response delivered to the user contains the rephrased version rather than the original value — semantic round-trip is broken.

**Why it happens:**
- LLMs are generative models that paraphrase, abbreviate, and generalize — they do not echo tokens verbatim
- When asked "What did [NAME_1] say?", the LLM may respond with "John said..." or "He said..." — neither of which matches the original Mapping
- Context-preserving Tokens (Req 4) preserve entity type and index count, but they cannot constrain the LLM's output format
- The bracket-optional + case-insensitive matching (Req 6, AC4-5) only helps if the LLM emits the _same text_ with cosmetic variations — it cannot handle semantic transformations

**Consequences:**
- The response contains partial or no replacement of the original value — the user may see "John S." when the original was "John Alexander Smith"
- This is not a security failure (no PII leaked) but a _fidelity_ failure — the user expects restored output that matches their input
- In financial or legal contexts, this is unacceptable: "Send payment to John S." vs. "Send payment to John Alexander Smith" has different legal implications
- The user perceives the gateway as "corrupting" their data

**Prevention:**
- This is an inherent limitation of tokenization-based anonymization — there is no technical fix inside the gateway
- Mitigation strategy: add a response-side PII scan on the restored output (Req 36 AC4 for output policy violation). If the response contains PII patterns that weren't in the original prompt (LLM-invented PII), flag and suppress
- Document this limitation prominently in the integration guide: "LLMs may rephrase tokenized entities. AnonReq restores tokens to their original values when the LLM echoes them verbatim. When the LLM transforms or abbreviates an entity, the transformed version appears in the output."
- For high-fidelity requirements, recommend users pass a system prompt instruction: "When referring to [NAME_1], always use the full name as written."
- Add a post-restoration comparison: compute a similarity score between the restored output and what a "perfect echo" response would look like — if similarity is below a threshold, log a structural warning

**Detection:**
- Compare `total_entities_detected` (from audit log) with the count of Tokens that were actually restored to original values — a large discrepancy indicates LLM rephrasing
- Add `anonreq_semantic_roundtrip_mismatch_total` counter — instrumentation is approximate (can't detect all rephrasings) but trending indicates degradation
- Sample sessions where entity count > 3 and perform manual review of restoration quality

**Phase to address:** Phase 1 (Core Gateway) — documented limitation. Phase 5 (Observability) — restoration quality monitoring.

---

## Minor Pitfalls

---

### Pitfall N1: Masked PII in JSON Tool Call Arguments Breaks JSON Validity

**What goes wrong:** A request contains a tool call with JSON arguments that include a detectable entity (e.g., `{"account": "john@example.com"}`). The Detection_Engine finds the email, and the Tokenization_Engine replaces it: `{"account": "[EMAIL_1]"}`. The resulting JSON is no longer valid because `[EMAIL_1]` is not a valid email format if the target schema expects an email pattern. The provider rejects the request with a validation error.

**Why it happens:**
- Tokenization replaces entity values with `[TYPE_N]` placeholders that don't respect schema validation rules
- For structured data (JSON tool call arguments), the replacement may violate format constraints (email, date, UUID patterns)
- Req 23, AC2 requires preserving JSON structural validity but doesn't address schema-level format validation
- Presidio's AnalyzerEngine.nlp_engine.process_text doesn't respect JSON structure — it treats the entire JSON string as flat text

**Consequences:**
- Provider returns 400 validation error on the tool call arguments
- The user sees a cryptic error from the provider, not from the gateway
- The gateway's audit log shows a successful anonymization but no indication that the provider rejected the payload

**Prevention:**
- For JSON tool call arguments, use JSON-aware scanning: parse the JSON, traverse string leaf nodes individually, scan each with Presidio, and replace within the string value only — this preserves JSON structure and avoids replacing format markers
- Maintain a per-field schema map (from the tool definition) that identifies which fields have format constraints — skip tokenization for format-constrained fields and use masking instead (e.g., replace email with anonymous@domain.com)
- If tokenization of a format-constrained field is required, wrap the token in a valid format: for email fields, use `email-Token_1@anonreq.local` instead of `[EMAIL_1]`

**Detection:**
- Monitor provider error response rates — a spike in 400 errors from a provider after a deployment change may indicate JSON-invalid tokenization
- Add a CI test with tool call arguments containing various PII types and verify the output JSON is valid against the tool's JSON Schema

**Phase to address:** Phase 1 (Core Gateway) — JSON-aware scanning in the Detection_Engine. The quick fix (format-safe tokens) should be in the initial implementation.

---

### Pitfall N2: Overlapping Entity Spans from Regex + NER

**What goes wrong:** A prompt contains "Dr. Jane Smith works at 123 Main St." The NER model detects "Jane Smith" as a PERSON entity (span [4,14]). The regex recognizer detects a street address ("123 Main St") which partially overlaps with the NER span if the address detection is over-eager. The Detection_Engine's conflict resolution (Req 3, AC3: regex wins over NER) discards the NER result for the overlapping region, losing the "Jane Smith" detection because it overlaps with the address entity.

**Why it happens:**
- Regex recognizers may capture broader spans than needed — a street address recognizer configured with context-based matching might capture "Jane Smith works at 123 Main St" as a single address span
- Overlap detection uses character-position containment, and a single large regex span can "shadow" multiple NER spans underneath it
- Req 3, AC3's conflict resolution rule is simple (regex wins) but produces counterintuitive results: a weak regex match of a large span can suppress a confident NER match of a smaller contained span

**Consequences:**
- Entity loss: "Jane Smith" is not tokenized because it was suppressed by the overlapping address detection
- If the address detection is a false positive (no actual address), the trade-off is pure loss — zero value from the winning regex span
- The fail-secure property guarantees no PII is forwarded, but it doesn't guarantee all PII is detected — this is a recall failure

**Prevention:**
- Use a smarter overlap resolution: when a regex span contains an NER span, retain the NER span if the regex span's confidence is below a threshold (e.g., 0.85) and the NER span's confidence is above the entity type threshold
- Implement a contain/contain-by hierarchy: if a high-confidence NER entity (PERSON > 0.9) is inside a lower-confidence regex entity (STREET_ADDRESS > 0.7), retain both as separate entities
- After conflict resolution, run a final pass to extract any NER-detected entities that were suppressed but whose entity type is in the mandatory detection set for the active compliance preset
- Document the overlap resolution algorithm with examples in `docs/architecture/detection-pipeline.md`

**Detection:**
- Add a Prometheus gauge `anonreq_entity_overlap_suppressed_total` — count of NER entities suppressed by regex overlap
- During audit log generation, include `overlaps_resolved` count per session
- Property-based test: generate texts with deliberately overlapping entity patterns and verify both entities appear in the output when expected

**Phase to address:** Phase 1 (Core Gateway) — overlap resolution logic. Phase 3 (Multilingual) when locale-specific recognizers add more overlap complexity.

---

### Pitfall N3: Arabic/BiDi Text Rendering in Logs and Error Messages

**What goes wrong:** A request contains Arabic text (right-to-left script). The Detection_Engine correctly processes it (with the `ar-*` locale bundle), but the tokenization produces replacement spans that, when mixed with the original BiDi text in diagnostic output or error messages, produce visually confusing or illegible output. Log entries containing mixed RTL/LTR strings render differently in different log viewers.

**Why it happens:**
- Unicode BiDi (Bidirectional) algorithm controls how RTL and LTR text is displayed — mixing `[NAME_1]` (LTR characters with brackets) with Arabic text (RTL) creates ambiguous display
- When a log aggregation system displays a JSON log entry containing mixed-direction strings, the visual order may be incorrect, making it appear that PII is present when it's actually the token
- spaCy's Arabic model has known tokenization issues with the Presidio integration (Presidio NER models for Arabic are less accurate than English)

**Consequences:**
- Operators cannot visually verify audit log entries for Arabic requests — the log display is confusing
- False impression of PII in logs: a BiDi rendering artifact makes a token look like a name
- Debugging Arabic detection failures requires Unicode expertise that most team members lack

**Prevention:**
- Use Unicode control characters (LRM, RLM, LRE, RLE, PDF) to mark token boundaries in mixed-direction output: wrap `[NAME_1]` in LTR markers (`\u200E[NAME_1]\u200E`) when the surrounding text is RTL
- In structured log output, always include explicit `locale` field so operators know when BiDi text is involved
- Document BiDi handling in `docs/operations/unicode-and-bidi.md`
- Add a CI test that generates prompts with Arabic text + English entities and verifies the tokenization output is BiDi-correct

**Detection:**
- The `locale` field in audit logs will show `ar-*` — operators should be trained to use JSON-aware log viewers that handle Unicode correctly
- Monitor detection recall for Arabic locale: compare entity counts per locale to detect systematic under-detection

**Phase to address:** Phase 3 (Multilingual) — the `ar-*` locale bundle is implemented here. BiDi correctness tests are part of this phase.

---

### Pitfall N4: Non-Deterministic Property Test Failures

**What goes wrong:** The property-based test suite (Req 16) runs 1,000+ random inputs for the round-trip correctness property. Test 843 fails: an input string containing a Unicode control character (e.g., U+200B zero-width space) embedded in a phone number causes the detection pipeline to produce different tokenization output than expected. The test fails. You run the test again with the same seed — it passes. The failure is non-deterministic.

**Why it happens:**
- The system has non-deterministic components: spaCy NER model inference is deterministic for fixed input but may vary with batch size, worker state, or model version
- The cross-request token randomization property (Req 16, AC8) _deliberately_ introduces non-determinism — Token indices are randomized per session
- Hypothesis's strategy for generating PII-like text may produce inputs at the boundary of spaCy's tokenization, where different runs produce slightly different NER results
- Concurrent test execution (pytest-xdist parallel workers) can create race conditions in shared test fixtures (Presidio AnalyzerEngine is reused across tests but has internal mutable state)

**Consequences:**
- Flaky tests reduce developer confidence — teams start ignoring failures and merging with red CI
- A real regression is hidden among the flaky failures
- The round-trip correctness guarantee is no longer provable because the test is unreliable
- The Hypothesis shrinking mechanism finds a "minimal failing example" that actually passes — confusing and eroding trust in the testing framework

**Prevention:**
- Fix the random seed for property tests: use `hypothesis.settings(max_examples=1000, derandomize=True)` — this makes Hypothesis use deterministic sequences from the profile configuration
- Pin spaCy model version and disable automatic model updates in CI — model changes should be a conscious upgrade step
- Isolate the Detection_Engine in tests: use a mock or in-process AnalyzerEngine with a known, small spaCy model (`en_core_web_sm`) and preload it before any tests run
- For the cross-request token randomization property, separate it into its own test class that explicitly tests randomization behavior without relying on NER determinism
- Use `hypython` profile system: create a `ci` profile with `derandomize=True` and a `dev` profile with faster examples for local development
- Add a `@flaky` detection mechanism: if a property test fails, save the failing example and re-run it 10 times in isolation — if it passes 10/10, the failure was non-deterministic and needs investigation

**Detection:**
- Track test failure rate in CI: if the same property test fails >5% of CI runs despite a correct fix, it's flaky due to non-determinism
- Add a CI step that runs flaky tests with `--hypothesis-seed` fixed to the failing seed and reports stability
- The `round-trip` property test should always pass with `derandomize=True` — if it doesn't, there is a real bug

**Phase to address:** Phase 2 (Testing) — the testing infrastructure must be designed for determinism from the start. Adding `derandomize=True` after finding flaky failures is possible but requires rewriting test strategies.

---

### Pitfall N5: Response-Side PII Reconstruction by the LLM

**What goes wrong:** The anonymized prompt sent to the LLM contains `[NAME_1]` for "John Smith" and `[EMAIL_1]` for "john@example.com". The LLM, relying on its training data, reconstructs or guesses the original values in its response: "I see that John Smith (john@example.com) is mentioned." The LLM leaked PII that was correctly removed from the outbound request but appeared in the inbound response — and the Restoration_Engine's Token replacement only fixes existing Tokens, not newly-invented PII.

**Why it happens:**
- LLMs are trained on vast internet data and may recognize token placeholders as signals of the underlying entity type — some models can infer "John Smith" from context clues and emit it in the response
- The response-side PII scan (Req 36, AC4 for output policy violation) is not part of the core specification — Req 13 only checks for unreplaced Tokens, not for new PII
- The Restoration_Engine does not scan for novel PII because its job is to restore Tokens, not detect new entities
- The Gateway has no mechanism to detect "LLM-invented" PII that wasn't in the original prompt

**Consequences:**
- PII that was correctly anonymized outbound appears in the response — the Gateway has failed its primary mission
- The enterprise's PII has now been sent to the LLM provider twice: once in the user's prompt (anonymized) and once in the LLM's training data (inferred)
- Legal liability: the enterprise exposed PII to a third-party provider despite running an anonymization gateway
- Extremely hard to detect because the audit log shows "0 entities detected" for the response side

**Prevention:**
- Implement a response-side PII scan on the LLM's output before delivering to the client: run the Detection_Engine on the restored response text, and if any PII is found that has entity type matches to the original prompt's entity types, block the response with HTTP 451 and log an incident
- Use a similarity check: compare entities detected in the response against entities detected in the prompt — if the response contains values similar to (but not identical with) prompt entities, it may be a reconstruction attempt
- Add a compliance header `X-AnonReq-Response-PII-Scanned: true/false` indicating whether response-side PII scanning was applied
- For high-sensitivity deployments, configure the response-side scan to use a stricter threshold (e.g., confidence 0.95) and a blocking action

**Detection:**
- Add `anonreq_response_pii_detected_total` counter — any non-zero value is a critical incident
- The response-side scan creates an audit log entry with `event_type: response_pii_detected`
- Periodic manual audit: sample 100 responses and scan for novel PII to validate the detection rate

**Phase to address:** Phase 4 (Security & Compliance) — response-side PII scanning is an advanced feature that builds on the core pipeline. Phase 1 must include the mechanism to pass response content through the Detection_Engine, even if the strict blocking policy is configurable off by default.

---

### Pitfall N6: Redis/Valkey `MONITOR` or Keyspace Notification Leaks

**What goes wrong:** An operator connects to the Valkey container using `redis-cli` to debug a cache issue. They run `MONITOR` to watch command traffic and see: `SET anonreq:{session_id} {"NAME_1": "John Smith", "EMAIL_1": "john@example.com"}`. The operator now has unfiltered access to all sensitive values. The commands are also written to Valkey's slow log or AOF buffer if enabled.

**Why it happens:**
- Req 5, AC3 explicitly disables `MONITOR`, `SLOWLOG`, and keyspace notifications — but configuration drift in production deployments may leave these enabled
- The `redis-cli MONITOR` command shows all key-value pairs in plaintext — no access control within the Valkey instance
- If the Valkey container is bound to a Docker network that's shared with other containers, any process on that network can connect and run `MONITOR`
- Valkey's default configuration has `MONITOR` enabled (it's a per-connection command, not a config toggle), and disabling it requires ACL rules

**Consequences:**
- All PII values stored in the Mapping are exposed to anyone with Valkey network access
- Compliance violation: the cache was represented as "ephemeral, no persistence, no monitoring commands" but monitoring commands leaked data
- The leak is invisible: `MONITOR` doesn't log to Valkey's regular log files, so there's no record that it was used

**Prevention:**
- Configure Valkey ACLs at startup: create a default user with no permissions and a gateway-specific user with only Hash command access (`HGET`, `HSET`, `HDEL`, `EXPIRE`, `TTL`, `PING`) — no `MONITOR`, `KEYS`, `SCAN`, `SLOWLOG`, or `CONFIG` commands
- Bind Valkey to a dedicated Docker network that only the Gateway container can access (Req 12 already requires this)
- Add a CI test that starts Valkey, runs the Gateway's health check, then attempts `MONITOR` and `SLOWLOG` commands and asserts they are rejected
- Include the Valkey ACL configuration in the `docker-compose.yml` as a config file mount — not as runtime commands that can be overridden
- For maximum security: use a Unix socket for Valkey access instead of TCP — eliminates network-based access entirely

**Detection:**
- Monitor Valkey's `total_commands_processed` — a sudden increase from unknown sources may indicate unauthorized access
- Add a Prometheus gauge `anonreq_valkey_unauthorized_command_attempts_total` by configuring Valkey's `acl-log-max` and reading `ACL LOG` entries
- Regular security scan: connect to the Valkey port from a test container and attempt `MONITOR` — if it succeeds, escalate

**Phase to address:** Phase 1 (Core Gateway) — Valkey ACL configuration is part of the Docker Compose setup. The CI test must be in Phase 2 (Testing).

---

### Pitfall N7: SSL/TLS Certificate Validation in Proxy Mode

**What goes wrong:** The Gateway is deployed behind a corporate firewall where outbound HTTPS connections are intercepted by a MITM proxy (e.g., Zscaler, Palo Alto). The Python `httpx` or `requests` library used by the Provider_Adapter to call the upstream LLM API fails with `SSL: CERTIFICATE_VERIFY_FAILED` because it doesn't trust the corporate CA. The Gateway returns HTTP 500 for all requests — effectively a denial of service — because the upstream connection can't be established.

**Why it happens:**
- The Gateway runs in a container (Python 3.12-slim) that has only system CA certificates installed — not the enterprise's internal CA
- Corporate MITM proxies present a certificate signed by the enterprise CA, which the container doesn't trust
- Python's `ssl` module in Alpine/slim images may not include the `certifi` package or may use the system CA bundle which differs from the host OS
- The `requests` library's default behavior is to verify certificates — without `REQUESTS_CA_BUNDLE` or `SSL_CERT_FILE`, it uses the system bundle

**Consequences:**
- Complete service outage in enterprise environments with SSL inspection
- The fail-secure behavior (HTTP 500) is correct but unhelpful — the gateway is blocked by infrastructure configuration, not a real error
- Debugging requires networking expertise that most Python developers don't have

**Prevention:**
- Document the corporate MITM proxy configuration requirement in the deployment guide: include steps for mounting the enterprise CA certificate into the container and setting `SSL_CERT_FILE` or `REQUESTS_CA_BUNDLE` environment variable
- Add a startup check that attempts to connect to each configured provider endpoint and logs a clear error message if certificate validation fails, including the expected CA path
- Provide a config option to specify custom CA bundle path (`ca_bundle_path` in gateway config)
- In the Docker Compose file, mount a volume for custom CA certificates: `- ./certs/ca-bundle.crt:/etc/ssl/certs/ca-certificates.crt`
- Document that disabling `verify=False` is NOT an acceptable workaround — it would disable all certificate validation, making the gateway vulnerable to MITM on the provider connection

**Detection:**
- Monitor `anonreq_fail_secure_events_total` with `failure_type=provider_connection_error` — a sustained 100% rate indicates an infrastructure issue
- The health check should include upstream provider connectivity: if all providers' endpoints fail with certificate errors, emit a specific `healthcheck` failure message identifying SSL configuration as the likely cause

**Phase to address:** Phase 1 (Core Gateway) — deployment configuration documentation. Phase 5 (Observability) — health check integration with provider endpoint verification.

---

### Pitfall N8: Unicode Latin Letter Lookalike Bypass

**What goes wrong:** A user submits a prompt with PII that uses Unicode homoglyph characters — replacing Latin letters with visually identical Cyrillic or Greek counterparts (e.g., using Cyrillic `а` U+0430 instead of Latin `a` U+0061 in "john@example.com" — `jоhn@example.com`). The Detection_Engine's regex recognizers for email addresses use Latin-character patterns and miss the homoglyph PII. The email passes through unsanitized.

**Why it happens:**
- Regex-based recognizers match specific Unicode ranges — an email regex `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` only matches Latin letters
- Cyrillic, Greek, or other-script lookalikes are not matched by Latin patterns
- The NER model may also miss these because its training data doesn't include homoglyph variants
- Unicode normalization (NFC/NFKC) does NOT convert homoglyphs to their Latin equivalents — NFKC normalizes `ﬁ` (ligature) to `fi` but does not convert Cyrillic `а` to Latin `a`
- This is a well-known attack vector for email filtering bypass

**Consequences:**
- PII bypasses the anonymization gateway entirely — the email/name/identifier is sent raw to the LLM provider
- The fail-secure guarantee holds (no error) but the detection guarantee is violated
- Attackers who understand the gateway's detection mechanisms can deliberately craft prompts to bypass detection
- Regulatory exposure: the gateway was presented as "detecting all PII" but uses a mechanism that is trivially bypassed

**Prevention:**
- Add a Unicode homoglyph detection and normalization pass before the Detection_Engine: use `unidecode` or a confusable detection library to flag text containing mixed-script characters and normalize them to their Latin equivalents
- Implement a "confusable detection" module that maps common homoglyph pairs (Cyrillic `а` → Latin `a`, Greek `ο` → Latin `o`, Cyrillic `е` → Latin `e`) and either normalizes the prompt or flags it for additional scrutiny
- Add a `homoglyph_detected` field to the audit log when mixed-script content is found — enables post-hoc analysis of bypass attempts
- Extend regex patterns with Unicode character classes where appropriate: use `[a-zA-Z\u0430-\u044Fа-я]` for locale-specific patterns that should capture both Latin and Cyrillic variants
- Document this limitation in the security guide: "AnonReq's regex detection operates on the Unicode code point level. Homoglyph attacks using visually identical characters from different scripts may bypass detection. We recommend deploying AnonReq with a web application firewall (WAF) that normalizes Unicode before routing to the gateway."

**Detection:**
- Add a Prometheus counter `anonreq_homoglyph_events_total` — any non-zero value indicates active bypass attempts
- Property-based test: generate email addresses and names using homoglyph variants and assert they are detected (or at minimum, that the system logs a warning)
- Regular security audit: run known homoglyph attack patterns through a staging gateway and verify they are flagged

**Phase to address:** Phase 1 (Core Gateway) — basic Unicode normalization. Phase 3 (Multilingual) — homoglyph detection module, as it's most relevant when multiple scripts are active.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|---|---|---|
| **Phase 1: Core Gateway** (FastAPI, Presidio integration, cache, streaming, provider adapter) | Presidio latency blows 100ms budget (Pitfall C6) | Use `en_core_web_sm`, pre-warm models, parallelize locale recognizers |
| | Token splits on SSE chunk boundaries (Pitfall C4) | FSM-based Tail_Buffer with partial Token prefix detection |
| | Exception handler leaks PII to logs/responses (Pitfall C1) | Generic 500 handler, log field allowlist, `DEBUG=false` enforcement |
| | Cache key collision (Pitfall M2) | `secrets.token_hex(32)` for Session_ID, `SETNX` collision check |
| | Provider schema translation loses data (Pitfall C5) | Schema completeness check, capability matrix, semantic preservation tests |
| **Phase 2: Testing** (property-based tests, CI) | Non-deterministic property test failures (Pitfall N4) | `derandomize=True` in CI, pinned spaCy model, separate randomization test |
| | Missing failure mode coverage for streaming split tests | Exhaustive stream splitting at all Token boundary positions (Req 16, AC7) |
| | Flaky integration tests due to Presidio model loading | Pre-warm models in conftest.py, serialized execution for model-dependent tests |
| **Phase 3: Multilingual** (8 locale bundles, custom rules) | Presidio false positives on business terminology (Pitfall C2) | Exclusion_List seed, domain-specific recognizers at lower confidence |
| | Arabic/BiDi rendering issues in logs (Pitfall N3) | Unicode control characters, `locale` field in logs, BiDi documentation |
| | Unicode normalization mismatch (Pitfall M3) | NFC at request boundary, consistent normalization across all components |
| | Hot-reload race condition (Pitfall M5) | Generation counter, copy-on-write registry, minimum reload interval |
| **Phase 4: Security & Compliance** (fail-secure hardening, response-side scan, auth) | LLM reconstructs PII in response (Pitfall N5) | Response-side PII scan on restored output, block/flag on detection |
| | Valkey `MONITOR` command leaks cache contents (Pitfall N6) | Valkey ACLs restricting commands, dedicated Docker network |
| | Homoglyph bypass attacks (Pitfall N8) | Confusable detection module, mixed-script normalization |
| **Phase 5: Observability** (metrics, audit logging, health checks) | Mid-stream provider error after HTTP 200 (Pitfall M4) | In-band error SSE event, stream completeness check |
| | SSL/TLS certificate validation in proxy environments (Pitfall N7) | Health check for provider connectivity, CA bundle documentation |
| | Audit log field allowlist gaps | CI test that injects PII and validates log output contains zero matches |
| **Phase 6: Performance** (latency optimization, scaling) | Premature cache eviction during long streams (Pitfall C3) | Atomic SETEX, volatile-lru, TTL refresh heartbeat |
| | Client disconnect leaves upstream stream running (Pitfall M1) | Context propagation to upstream, disconnect check after every `await` |
| | Response-side PII scan adds duplicate latency | Cache Detection_Engine results for the response pass if prompt is still in context |

## Sources

| Source | Confidence | Key Finding |
|---|---|---|
| [Presidio FAQ — False Positive Guidance](https://microsoft.github.io/presidio/faq/) | HIGH (official docs) | Trade-off between FP and FN; use exclusion lists, confidence thresholds, custom recognizers |
| [Presidio Issue #1071 — TFN/PCI recognizer scoring order](https://github.com/microsoft/presidio/discussions/1071) | HIGH (direct from maintainers) | Checksum validation before context scoring produces false positives at confidence 1.0 |
| [Presidio Issue #999 — German word segmentation](https://github.com/microsoft/presidio/discussions/999) | HIGH (community report) | spaCy German model splits compound nouns, producing false name detections |
| [Alvaro et al. 2024 — Presidio precision study](https://anonym.legal/hr/blog/false-positive-tax-pii-detection-precision-2025) | MEDIUM (third-party academic) | 22.7% precision on mixed-language business datasets |
| [Presidio Discussion #1097 — NER latency bottleneck](https://github.com/microsoft/presidio/discussions/1097) | HIGH (maintainers confirmed) | `en_core_web_sm` gives <10ms/1K tokens; PhoneRecognizer is slowest |
| [Streaming SSE Proxying — The Hard Parts](https://dev.to/gauravdagde/streaming-sse-proxying-for-llm-apis-the-hard-parts-4d60) | HIGH (production experience, 5000+ req/s) | Four failure modes: chunk boundaries, token leaks, backpressure, mid-stream 200 errors |
| [FastAPI StreamingResponse client disconnect behavior](https://github.com/fastapi/fastapi/discussions/13349) | HIGH (official discussion) | `StreamingResponse` raises `CancelledError` on disconnect; upstream provider is NOT auto-cancelled |
| [sse-starlette library](https://github.com/sysid/sse-starlette) | HIGH (used by FastAPI ecosystem) | Production SSE implementation with disconnect detection and graceful shutdown |
| [LLM Provider Quirks — FutureSearch](https://futuresearch.ai/blog/llm-provider-quirks/) | HIGH (production experience) | JSON Schema interpretation differences, force-tool-call restrictions, caching disparities |
| [LiteLLM Issue #25172 — Streaming drops text_delta](https://github.com/BerriAI/litellm/issues/25172) | HIGH (reproduced bug) | Empty `tool_calls: []` in streaming deltas silently drops text content during Anthropic→OpenAI translation |
| [Redis/Valkey Key Eviction Documentation](https://redis.io/docs/latest/develop/reference/eviction) | HIGH (official docs) | LRU eviction under maxmemory can remove keys before TTL expiry |
| [Valkey CVE-2025-49844 and related advisories](https://github.com/orgs/valkey-io/discussions/2706) | HIGH (official security advisory) | Use-after-free and other vulnerabilities require version pinning and ACL configuration |
| [Your Logs Are a Security Risk — DEV](https://dev.to/suhteevah/your-logs-are-a-security-risk-6-patterns-that-leak-pii-5jd) | MEDIUM (community best practices) | Six PII leak patterns in logging, including exception stack traces with credentials |
| [Hypothesis Documentation — Derandomize](https://hypothesis.readthedocs.io/en/latest/settings.html) | HIGH (official docs) | `derandomize=True` makes property tests deterministic for CI |
| [Unicode Confusable Detection (UTS #39)](https://www.unicode.org/reports/tr39/) | HIGH (Unicode standard) | Identifies homoglyph characters across scripts for security detection |
