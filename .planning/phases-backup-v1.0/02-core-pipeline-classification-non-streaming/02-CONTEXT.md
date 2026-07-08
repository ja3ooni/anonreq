# Phase 2: Core Pipeline & Classification (Non-Streaming) - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Full non-streaming pipeline — classifies payload first (Block/Route/Anonymize/Pass), then detects PII via regex and NER, tokenizes with `[TYPE_N]` placeholders, forwards sanitized request to OpenAI, caches mapping in Valkey, restores original values, and cleans up. Correctness proven by Hypothesis property tests before Phase 3 begins.

This is the first phase that touches real request data. The foundation (auth, logging, error handling, Docker, health checks) ships in Phase 1.
</domain>

<decisions>
## Implementation Decisions

### Classification Rule Format
- **D-22:** YAML DSL with stable rule IDs, `enabled`, `version`, action, metadata block, conditions
- **D-23:** Conditions are ANDed within a rule: `roles` (list of message roles), `regex` (patterns), `keywords` (case-insensitive word matches)
- **D-24:** Action-based precedence: BLOCK > ROUTE_LOCAL > ANONYMIZE > PASS. No numeric priority field
- **D-25:** No `entity_types` in classification rules — classification runs before Presidio detection
- **D-26:** No expression language (OR/NOT/nested) in MVP
- **D-27:** Classification results record `matched_rule_ids` and `matched_rule_versions` for auditability
- **D-28:** `default_action: PASS` — unaffected requests pass through

### Text Traversal & Scanning
- **D-29:** Recursive JSON walker with configurable text-path allowlist — `TextExtractor → TextNode(path, value)`
- **D-30:** Not a fixed hardcoded field list; not every string leaf scanned indiscriminately.
- **D-31:** `TextNode(path, value)` model reused across classification, detection, tokenization, restoration

### Presidio Integration
- **D-32:** One Analyzer request per TextNode, executed concurrently via `asyncio.gather()`
- **D-33:** Detection interface accepts `list[TextNode]` — future phases can switch to batch inference behind same `DetectionProvider` contract
- **D-34:** Skip Presidio for TextNodes < 20 characters — regex only
- **D-35:** spaCy model: `en_core_web_md` (medium — balance of accuracy, latency, container footprint)
- **D-36:** Configurable recognizer registry loaded from YAML. Not hard-coded. Two tiers:
  - Tier 1 (default enabled): EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, IBAN_CODE, IP_ADDRESS, URL, PERSON, ORGANIZATION, LOCATION, DATE_TIME
  - Tier 2 (configurable): SWIFT_CODE, CRYPTO, US_SSN, UK_NHS, PASSPORT, DRIVER_LICENSE, NATIONAL_ID, CUSTOM_ENTERPRISE_PATTERNS
- **D-37:** Detection confidence threshold configurable per-entity, default 0.70
- **D-38:** Regex for deterministic identifiers (email, phone, IBAN, API keys, credentials). Presidio NER for fuzzy entities (PERSON, ORG, LOCATION, ADDRESS)

### Regex + NER Merge (Span Arbitration)
- **D-39:** Run both independently, then merge via overlap resolution
- **D-40:** Exact span overlap → regex wins. Nested overlap → most specific entity type wins. Partial overlap → preserve most semantically useful span. Non-overlapping → both kept
- **D-41:** Entity specificity ranking: API_KEY > EMAIL > PHONE > CREDIT_CARD > IBAN > SSN > PERSON > LOCATION > ORG

### Session ID & Request ID
- **D-42:** Gateway generates UUIDv7 for every request context. Client never controls session identity.
- **D-43:** UUIDv7 is the mapping-store key owner. Propagated through all pipeline stages and logging
- **D-44:** `X-AnonReq-Request-ID` header exposed for support/debugging/audit correlation. Session ID is internal only — not in the public API contract

### Pipeline Orchestration
- **D-45:** `ProcessingContext`-based stage registry. Sequential stages, internal concurrency within stages
- **D-46:** `ProcessingContext` contains: request_id, tenant_id, context_id (UUIDv7), original_request, text_nodes, classification_result, detections, token_mappings, transformed_request, provider_response, restored_response, audit_metadata
- **D-47:** Stage order: Classification → Detection → Tokenization → ForwardingGuard → Provider → Restoration → Cleanup
- **D-48:** ForwardingGuard runs immediately before ProviderStage. ProviderStage is unreachable unless Classification, Detection, Tokenization, and Mapping commit complete
- **D-49:** Any stage failure aborts pipeline immediately. No downstream stage executes. No outbound call

### Fail-Secure (Presidio-specific)
- **D-50:** Classification failure → BLOCK (500). Presidio timeout (default 2s) → BLOCK (503). Presidio unavailable → BLOCK (503). Presidio malformed response → BLOCK (500). Detection merge failure → BLOCK (500). Tokenization failure → BLOCK (500). Valkey mapping failure → BLOCK (500)
- **D-51:** Circuit breaker opens after N Presidio failures
- **D-52:** Health endpoint exposes Presidio dependency status

### Phase 2 Property-Test Invariants
- **D-53:** 10 required invariants must pass under Hypothesis before Phase 2 closes:
  1. TEST-01: Round-trip — `Restore(Tokenize(x)) == x`, byte-for-byte
  2. TEST-02: Token uniqueness — N distinct values → N distinct tokens
  3. TEST-03: Token deduplication — same value K times → same token
  4. TEST-04: Fail-secure — injected failure in any stage → request not forwarded, error returned, no outbound call
  5. TEST-05: ForwardingGuard — ProviderStage unreachable unless all prerequisites complete
  6. TEST-06: No-PII-in-logs — generated PII never appears in structured logs
  7. TEST-07: Mapping integrity — each token maps to exactly one original value
  8. TEST-08: Restoration completeness — every token restored or causes fail-secure
  9. TEST-09: Context isolation — Context A tokens never restore from Context B
  10. TEST-10: Tenant isolation — Tenant A mappings never visible to Tenant B

### From Phase 1 (carried forward)
- D-01 to D-21 from Phase 1 CONTEXT.md apply fully — error model, logging, config, tenant isolation, Valkey HASH, capability registry, testing bar
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — PIPE-01 to PIPE-06, FAIL-01 to FAIL-02, DET-01 to DET-06, TOKN-01 to TOKN-07, CACH-01 to CACH-06, PROV-01, AUDT-04 to AUDT-05, CLASS-AC-01 to 05, TEST-01 to TEST-03
- `.planning/ROADMAP.md` § Phase 2 — Success criteria, 5 plans (02-01 to 02-05)

### Phase 1 Decisions
- `.planning/phases/01-foundation-fail-secure-auth/01-CONTEXT.md` — All decisions carry forward (D-01 through D-21)

### Project Decisions
- `.planning/PROJECT.md` — Python 3.12 + FastAPI, Presidio sidecar, Valkey, Docker Compose, Apache 2.0, fail-secure mandate
- `.planning/REQUIREMENTS.md` § Hardening Decisions — Classification runs before Presidio (Plan 02-02); property tests alongside code
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
None — Phase 2 is the first pipeline code. Phase 1 scaffolding (config, logging, error handling, auth) is the foundation.

### Established Patterns
- ProcessingContext-based stage pipeline (D-45 to D-49)
- TextExtractor → TextNode(path, value) abstraction (D-29 to D-31)
- DetectionProvider interface for Presidio/resolver swapping (D-33)

### Integration Points
- Presidio Analyzer at `ANONREQ_PRESIDIO_URL` (Docker sidecar) — per-TextNode HTTP calls
- Valkey at `ANONREQ_VALKEY_URL` — HASH mapping store for token↔value pairs
- OpenAI /v1/chat/completions — native schema passthrough as upstream provider (Phase 3 adds more)
</code_context>

<specifics>
## Specific Ideas

- Pipeline stages operate on shared `ProcessingContext` — no shared mutable state outside the context
- Classification rule example:
  ```yaml
  - id: CLS-001
    enabled: true
    version: 1
    name: block_credentials
    action: BLOCK
    metadata:
      owner: security-team
      category: credentials
      severity: critical
    conditions:
      roles: [user]
      regex: ['(?i)(password|secret|api.?key)\s*[:=]\s*\S+']
  ```
- ALL detection/pipeline failures → BLOCK — never forward incomplete data
- Circuit breaker for Presidio dependency
</specifics>

<deferred>
## Deferred Ideas

- Entity-based classification conditions — possible when detection runs before classification (not MVP)
- Expression language (OR/NOT) — deferred post-MVP
- Client-controlled session IDs — deferred post-MVP
- Batch Presidio inference — deferred to future phase if profiling shows bottleneck
- Streaming-specific invariants — deferred to Phase 3
- Cross-request token randomization (TEST-08) — deferred to Phase 5/6
</deferred>

---

*Phase: 2-Core Pipeline & Classification (Non-Streaming)*
*Context gathered: 2026-06-20*
