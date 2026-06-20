# Phase 13: AI Firewall & Data Loss Prevention - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md.

**Date:** 2026-06-20
**Phase:** 13-ai-firewall-data-loss-prevention
**Areas discussed:** Phase 10/13 Relationship, DLP Categories Location, Quarantine, Exfiltration Detection, MITRE ATT&CK, Contextual Rules, Redact vs Anonymize, DLP Evaluation Order, DLP Categories Fixed/Configurable

---

## Phase 10 vs 13
| Option | Selected |
|--------|----------|
| DLP alongside Threat Engine | ✓ |
| DLP wraps Threat Engine | |
| DLP replaces Threat Engine | |

**User's choice:** AI Firewall ├── Threat Engine (Phase 10) └── DLP Engine (Phase 13). Parallel, shared infra.

## DLP Categories Location
| Option | Selected |
|--------|----------|
| Phase 8 policy YAML | |
| Dedicated DLP configuration | ✓ |
| Hardcoded | |

**User's choice:** Dedicated dlp.yaml.

## Quarantine
| Option | Selected |
|--------|----------|
| Block + store payload | |
| Block + metadata only | ✓ |
| Route to approval queue | |

**User's choice:** Block + metadata only. No payload stored.

## Exfiltration Detection
| Option | Selected |
|--------|----------|
| Heuristic patterns | |
| Entropy-based | |
| Hybrid: heuristics + entropy | ✓ |

**User's choice:** Hybrid.

## MITRE ATT&CK
| Option | Selected |
|--------|----------|
| Metadata tags on rules | |
| Dedicated MITRE mapping config | ✓ |
| Log-level only | |

**User's choice:** Dedicated mapping config.

## Contextual Rules
| Option | Selected |
|--------|----------|
| Priority-based merge | |
| AND condition | |
| Category wins, then filter | ✓ |

**User's choice:** Category determines base action. Unit + classification tighten, never loosen.

## Redact vs Anonymize
**User's choice:** Anonymize = tokenize (restorable). Redact = remove entirely (not restorable).

## DLP Evaluation Order
**User's choice:** Threat Detection → Classification → DLP → PDP #2 → Provider.

## DLP Categories
**User's choice:** Fixed core (8 categories) in code + tenant custom categories in dlp.yaml. Core: PII, Financial, Health, Source Code, Credentials, Legal, Export Controlled, Intellectual Property.
