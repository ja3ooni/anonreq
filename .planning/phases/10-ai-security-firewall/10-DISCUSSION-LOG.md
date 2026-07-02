# Phase 10: AI Security Firewall - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md.

**Date:** 2026-06-20
**Phase:** 10-ai-security-firewall
**Areas discussed:** Detection Approach, Pipeline Position (Inbound/Outbound), Phase Boundary, Rule Format, Streaming, Latency, Outbound Violations, Detection Categories

---

## Detection Approach
| Option | Selected |
|--------|----------|
| Rule-based only | |
| ML model only | |
| Hybrid: rules + ML | ✓ |

**User's choice:** Hybrid. Fast rules (≤50ms) + ML when flagged (≤200ms total).

## Inbound Position
| Option | Selected |
|--------|----------|
| After PDP #1 | |
| After PDP #2 | |
| Both (pre-anon + post-anon) | ✓ |

**User's choice:** Both gates.

## Outbound Position
| Option | Selected |
|--------|----------|
| Before restoration | |
| After restoration | |
| Both | ✓ |

**User's choice:** Both gates (pre-restore + post-restore).

## Phase 10 vs 13
| Option | Selected |
|--------|----------|
| Phase 10 foundation, Phase 13 expansion | ✓ |
| Phase 10 MVP, Phase 13 full | |
| Merge them | |

**User's choice:** Phase 10 is foundation (detection engine + rule system). Phase 13 adds DLP + MITRE + deeper.

## Rule Format
| Option | Selected |
|--------|----------|
| Pattern-based rules | |
| Semantic rules + patterns | ✓ |
| Defer to agent | |

**User's choice:** Semantic rules + patterns (both regex + ML descriptions).

## Streaming Detection
| Option | Selected |
|--------|----------|
| Buffer at message boundaries | |
| Chunk-level detection | |
| Buffer + sliding window (~2KB) | ✓ |

**User's choice:** Sliding window.

## Latency Budget
**User's choice:** normal_budget = 50ms (rules only), flagged_budget = 200ms (rules + ML).

## Outbound Violations
| Option | Selected |
|--------|----------|
| HTTP 451 + block | |
| Suppress + log | |
| Configurable per severity | ✓ |

**User's choice:** HIGH→BLOCK, MEDIUM→flag_and_forward, LOW→monitor.

## Detection Categories
**User's choice:** prompt_injection, jailbreak, system_prompt_extraction, instruction_override, role_escalation, hidden_tool_invocation, secret_exfiltration. All with configurable enabled/true.
