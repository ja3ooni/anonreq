# Phase 2: Core Pipeline & Classification (Non-Streaming) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-20
**Phase:** 2-Core Pipeline & Classification (Non-Streaming)
**Areas discussed:** Classification Rule Format, Text Traversal & Scanning, Presidio Integration, Session ID Source, Pipeline Orchestration, Property-Test Invariants

---

## Classification Rule Format

**User's choice:** Multi-condition AND rules with action-based precedence (BLOCK > ROUTE_LOCAL > ANONYMIZE > PASS)

| Option | Selected |
|--------|----------|
| Content-match only (regex patterns) | |
| Multi-condition (regex + keywords + roles) | ✓ |
| Expression-based (AND/OR/NOT) | |

**Notes:** Rules have stable IDs, `enabled` flag, `version` integer, metadata block. Conditions: roles, regex, keywords — ANDed within a rule. No entity_types (classification runs before detection). No numeric priority — action-based precedence. No expression language in MVP. matched_rule_ids and matched_rule_versions recorded in results.

### Schema refinement (follow-up)

| Option | Selected |
|--------|----------|
| Proposed schema (priority, entity_types, no IDs) | |
| Modified schema (action precedence, no entity_types, rule IDs, metadata) | ✓ |
| Further refinement (+ enabled, version) | ✓ |

---

## Text Traversal & Scanning

**User's choice:** Hybrid — recursive walker + path allowlist

| Option | Selected |
|--------|----------|
| Recursive JSON walker (all string leaves) | |
| Targeted field extraction (hardcoded fields) | |
| Hybrid (walker + path allowlist) | ✓ |

**Notes:** TextExtractor → TextNode(path, value) reusable component. Not hardcoded fields, not all strings scanned. Future-proof against OpenAI schema changes. Reusable across classification, detection, tokenization, restoration.

---

## Presidio Integration Strategy

### Call Pattern
| Option | Selected |
|--------|----------|
| Batch all text into one Analyzer call | |
| One Analyzer per TextNode concurrently | ✓ |

**Notes:** asyncio.gather() for concurrency. DetectionProvider interface for future batch-swapping. Skip Presidio for TextNodes < 20 chars.

### Detection Merge
| Option | Selected |
|--------|----------|
| Regex first, filter Presidio overlap | |
| Span arbitration with specificity ranking | ✓ |

**Notes:** Run both independently. Overlap resolution rules. Specificity ranking: API_KEY > EMAIL > PHONE > CREDIT_CARD > IBAN > SSN > PERSON > LOCATION > ORG.

### Recognizers & Model
| Option | Selected |
|--------|----------|
| en_core_web_sm + core recognizers | |
| en_core_web_lg + core recognizers | |
| en_core_web_md + configurable registry | ✓ |

**Notes:** Tier 1 (default): EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, IBAN_CODE, IP_ADDRESS, URL, PERSON, ORGANIZATION, LOCATION, DATE_TIME. Tier 2 (configurable): SWIFT_CODE, CRYPTO, US_SSN, UK_NHS, PASSPORT, DRIVER_LICENSE, NATIONAL_ID, CUSTOM_ENTERPRISE_PATTERNS. Regex for deterministic, Presidio NER for fuzzy. Threshold default 0.70.

### Fail-Secure Behavior
**User's choice:** Every Presidio/detection/tokenization failure → BLOCK. No request forwarded if detection incomplete. Presidio timeout default 2s. Circuit breaker after N failures. Health endpoint exposes dep status.

---

## Session ID Source

| Option | Selected |
|--------|----------|
| Gateway auto-generates UUIDv7 | ✓ |
| Client provides via X-AnonReq-Session-ID | |
| Both (client-optional, auto-fallback) | |

**Notes:** UUIDv7 on ingress. Session ID is internal only — never accepted from clients. X-AnonReq-Request-ID exposed for debugging/correlation. Session ID = mapping key owner.

---

## Pipeline Orchestration

| Option | Selected |
|--------|----------|
| Sequential stage chain (hardcoded) | |
| ProcessingContext with stage registry | ✓ |

**Notes:** Sequential stages: Classification → Detection → Tokenization → ForwardingGuard → Provider → Restoration → Cleanup. Internal stage work may be parallelized (regex + Presidio concurrently). ProcessingContext shared object. Any stage failure aborts pipeline.

---

## Property-Test Invariants

| Option | Selected |
|--------|----------|
| Round-trip + uniqueness only (3 tests) | |
| + fail-secure (4 tests) | |
| All non-streaming invariants (10 tests) | ✓ |

**Notes:** 10 invariants required. Security invariants mandatory. Streaming-specific deferred. Cross-request randomization deferred.
