# Phase 12: Data Classification & Handling Policies - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md.

**Date:** 2026-06-20
**Phase:** 12-data-classification-handling
**Areas discussed:** Mapping Location, Policy Integration, Client Classification, Audit Integration, Per-Level Actions, Classification Tiers, Entity Mapping, Response Header, Highest Sensitivity Calculation

---

## Mapping Location
| Option | Selected |
|--------|----------|
| Phase 8 Policy YAML | ✓ |
| Dedicated classification config | |
| Hardcoded defaults | |

**User's choice:** In Phase 8 Policy YAML.

## Policy Integration
| Option | Selected |
|--------|----------|
| Phase 12 feeds into PDP #2 | ✓ |
| Classification before PDP #2 | |
| Classification overrides PDP | |

**User's choice:** Classification result is input to PDP #2.

## Client Classification
**User's choice:** Client may increase, never decrease. Enterprise critical for M&A docs, board materials, trade secrets.

## Audit Integration
| Option | Selected |
|--------|----------|
| Stamped on RequestContext | ✓ |
| Added at emission | |
| Middleware stamps headers | |

**User's choice:** Classification stamped on RequestContext.

## Per-Level Actions
| Option | Selected |
|--------|----------|
| Static mapping | |
| Dynamic YAML | |
| Hybrid: defaults + overridable | ✓ |

**User's choice:** Public/Internal → PASS, Confidential → ANONYMIZE, Restricted → ANONYMIZE+AUDIT, Highly Restricted → BLOCK. Overridable in YAML.

## Classification Tiers
| Option | Selected |
|--------|----------|
| Fixed enum | |
| Configurable in YAML | |
| Fixed enum + display names | ✓ |

**User's choice:** Fixed enum in code, display names configurable.

## Entity Mapping
| Option | Selected |
|--------|----------|
| Default mapping in code | ✓ |
| Mapping only in YAML | |
| Code defaults + YAML override later | |

**User's choice:** Default in code, tenant override in YAML.

## Response Header
**User's choice:** Only when X-AnonReq-Return-Classification: true. X-AnonReq-Debug does NOT trigger classification response headers — classification is only returned when explicitly and separately requested. Audit always stores classification.

## Highest Sensitivity Calculation
**User's choice:** Deterministic max. No AI, no scoring, no confidence blending. `highest = max(entity_mapping[e] for e in entities)`. All labels preserved.
