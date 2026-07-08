# Phase 15: Financial Services Compliance - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md.

**Date:** 2026-06-20
**Phase:** 15-financial-services-compliance
**Areas discussed:** MNPI Bundle, MRM Integration, Provider Inventory, Context Boosting, DORA, AML Webhook, Compliance Report, SEC 17a-4

---

## MNPI Bundle
| Option | Selected |
|--------|----------|
| New Presilio recognizer | |
| Extend Phase 2 NER | |
| New bundle + tenant restricted-names list | ✓ |

**User's choice:** New bundle + tenant-configurable restricted-names list.

## MRM Integration
| Option | Selected |
|--------|----------|
| Extension of Phase 14 | |
| Standalone MRM | |
| Hybrid: MRM in lifecycle | ✓ |

**User's choice:** Hybrid. MRM concepts in Phase 14 governance lifecycle with model-specific fields.

## Provider Inventory
| Option | Selected |
|--------|----------|
| PostgreSQL | |
| Phase 14 governance records | |
| PostgreSQL + governance versioning | ✓ |

**User's choice:** Both.

## Context Boosting
| Option | Selected |
|--------|----------|
| Presidio context-aware enhancement | ✓ |
| Post-processing confidence adjuster | |
| Rule-based additional analyzer | |

**User's choice:** Presidio context-aware. +0.15 within 50 chars, capped at 1.0.

## DORA Escalation
**User's choice:** Configurable per criticality: critical (slo_breach + auto_incident + notify), important (slo_breach only), standard (none).

## AML Webhook
**User's choice:** Configurable threshold per tenant. Metadata-only payload.

## Compliance Report
**User's choice:** Both — dynamic generation + exportable template.

## SEC 17a-4
**User's choice:** Dedicated MinIO WORM bucket for MNPI (separate from Phase 11 compliance bucket).
