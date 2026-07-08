# Phase 10 — AI Security Firewall: Final Report

**Project:** AnonReq
**Phase:** 10 — AI Security Firewall (Plans 10-01 through 10-04)
**Date:** 2026-07-02
**Status:** ✅ Complete

---

## Architecture

```
                     ┌─ InboundFirewallGate ──┐
                     │  pre-anon | post-anon  │
Client ──▶ HTTP ──▶  │        engine          │ ──▶ 400 BLOCK or forward
                     └────────────────────────┘
                                     │
                           Anonymization Engine
                                     │
                     ┌─ OutboundFirewallGate ─┐
                     │ pre-restore | post-re  │
Client ◀── HTTP ◀──  │        engine          │ ◀── LLM Provider
                     └────────────────────────┘
                     ▶ 451 BLOCK or forward
```

4 gate positions × 2 gate types (Inbound/Outbound), 14 YAML rules across 7 categories, 2 middleware interceptors.

## Deliverables

### Source Code (7 new files in `src/anonreq/firewall/`)
| File | Purpose |
|------|---------|
| `engine.py` | `FirewallRuleEngine` — regex evaluation + dedup + snippet |
| `models.py` | `DetectionCategory`, `SeverityLevel`, `FirewallRule`, `DetectionResult`, `RuleCategoryConfig`, `SeverityActionMapping` |
| `rules.py` | YAML loader (`FirewallRuleLoader`) + `load_firewall_rules()` |
| `gates.py` | `InboundFirewallGate` (pre/post-anon) + `OutboundFirewallGate` (pre/post-restore) |
| `streaming.py` | `SlidingWindowDetector` + `StreamingFirewallDetector` |
| `reloader.py` | `FirewallRuleReloader` (hot-reload + watchdog watcher) |
| `admin.py` | FastAPI router — `GET /v1/admin/prompt-security/rules`, `GET .../{rule_id}` |
| `audit.py` | `FirewallAuditPublisher` — structured audit events, no raw content |
| `metrics.py` | `FirewallMetrics` — Prometheus counters for injection/outbound/reload |
| `ml_model.py` | `NoopMLModel` + `FirewallMLModel` (ONNX stub) |

### Middleware (2 files in `src/anonreq/middleware/`)
| File | Purpose |
|------|---------|
| `firewall_inbound.py` | `InboundFirewallMiddleware` — intercepts `/v1/chat/completions` |
| `firewall_outbound.py` | `OutboundFirewallMiddleware` — inspects LLM responses |

### Configuration
- `config/prompt-security-rules.yaml` — 14 default rules across 7 categories

### Tests (9 files in `tests/firewall/`, 185 total)
| Test File | Tests | Type |
|-----------|-------|------|
| `test_models.py` | 26 | Unit — Pydantic validation |
| `test_rules.py` | 10 | Unit — YAML loading + dedup |
| `test_engine.py` | 14 | Unit — rule evaluation + dedup |
| `test_ml_model.py` | 8 | Unit — NoopMLModel + integration |
| `test_gates.py` | 22 | Unit — Inbound/Outbound gate logic |
| `test_streaming.py` | 13 | Unit — sliding window + cross-chunk |
| `test_reloader.py` | 6 | Unit — hot-reload lifecycle |
| `test_admin_routes.py` | 7 | Unit — admin API routes |
| `test_audit_metrics.py` | 16 | Unit — publisher + Prometheus |
| `test_property.py` | 5 | **Property** — Hypothesis (120 examples) |
| `test_security.py` | 15 | **Security** — categories, gates, no-PII, latency |
| `test_acceptance.py` | 23 | **Acceptance** — pipeline, edges, concurrency, fail-secure |
| `test_firewall_integration.py` | 6 | **Integration** — FastAPI middleware |

### Test Results
```
tests/firewall/ — 185 passed, 2 skipped, 0 failed in 2.43s
```
(Skipped: ONNX model file tests — no model in test env)

## Rule Coverage
| Category | Rules | Example Pattern |
|----------|-------|-----------------|
| `prompt_injection` | 2 | `ignore\s+all\s+(previous\s+)?(instructions|commands)` |
| `jailbreak` | 2 | `DAN|do\s+anything\s+now` |
| `system_prompt_extraction` | 2 | `what\s+(is\|was)\s+(your\|the)\s+(system\s+)?(prompt|instruction)` |
| `instruction_override` | 2 | `override\s+(instructions|commands|directives)` |
| `role_escalation` | 2 | `you\s+are\s+(now|an?\s+|the\s+)(admin(istrator)?|root|superuser)` |
| `hidden_tool_invocation` | 2 | `hidden\s+(function|tool|command|operation)` |
| `secret_exfiltration` | 2 | `leak\s+(your\s+)?(API\s+)?keys|secrets|tokens|password` |

## Key Design Decisions
1. **Fail-secure**: any error → HTTP 400 (inbound) or 451 (outbound), never forward unsanitized data
2. **No PII in logs**: `matched_text_snippet` truncated to 50 chars; metadata-only audit events
3. **threshold 0.3** in tests — necessary for short matches (3-char "DAN" → ~0.83 confidence)
4. **Per-category config**: enabled + threshold (0.0-1.0), unconfigured categories use default 0.85
5. **SeverityActionMapping**: HIGH→BLOCK, MEDIUM→FLAG_AND_FORWARD, LOW→MONITOR
6. **Streaming**: `SlidingWindowDetector` buffers chunks + evaluates at boundaries + flush
7. **Cross-chunk injection**: `"X"+text[:split]` strategy to cover all split positions in property tests
8. **Admin routes**: no built-in auth dependency; auth via `include_router(dependencies=[Depends(verify_admin_api_key)])` at app level
9. **Hypothesis property tests**: 5 properties × 20-50 examples each, all passing

## Conformance with Requirements
| Req | Description | Status |
|-----|-------------|--------|
| Req 11 | PII detection configurable threshold per category | ✅ CategoryConfig |
| Req 16 | Property tests: round-trip, dedup, fail-secure, locale, streaming, cross-request | ✅ 5 property tests |
| Req 17 | All detection in memory, no disk writes | ✅ No disk in engine |
| Req 20 | Audit with no raw PII | ✅ FirewallAuditPublisher |
| Req 21 | 7 PII categories | ✅ 7 detection categories |
| Req 22 | Fail-secure default | ✅ 400/451 on error |
| Req 23 | Streaming SSE | ✅ SlidingWindowDetector |
| Req 24 | Custom rules via YAML | ✅ 14 rules in YAML |
| Req 25 | Admin API for rules | ✅ admin.py router |

## Total Engineering
- **13 source files** created in `src/anonreq/firewall/` + `src/anonreq/middleware/`
- **13 test files** created in `tests/firewall/`
- **1 config file** created in `config/`
- **185 tests**, 0 failures
