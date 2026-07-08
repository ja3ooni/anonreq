# Phase 14: AI Governance & Oversight - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md.

**Date:** 2026-06-20
**Phase:** 14-ai-governance-oversight
**Areas discussed:** Kill-Switch, Approval Storage, Risk Dimensions, Transparency, Lifecycle Stages, Conformity Package, Notifications, Governance Versioning

---

## Kill-Switch
| Option | Selected |
|--------|----------|
| Global only | |
| Per-tenant only | |
| Both (global + per-tenant) | ✓ |

**User's choice:** Both.

## Approval Storage
| Option | Selected |
|--------|----------|
| PostgreSQL (Phase 11) | |
| In-memory + Valkey | |
| PostgreSQL + audit trail | ✓ |

**User's choice:** PostgreSQL + immutable audit trail (Phase 11 hash chain).

## Risk Dimensions
| Option | Selected |
|--------|----------|
| Fixed ISO 42001 core | |
| Configurable per tenant | |
| Hybrid: core + extensions | ✓ |

**User's choice:** Fixed core (privacy, security, bias, explainability, fairness, safety) + tenant extensions.

## Transparency
| Option | Selected |
|--------|----------|
| Per-session headers only | |
| Per-session + periodic reports | ✓ |
| Real-time status endpoint | ✓ |

**User's choice:** Headers + periodic reports + status endpoint.

## Lifecycle Stages
**User's choice:** DRAFT → REVIEW → APPROVED → PRODUCTION → DEPRECATED → RETIRED (6 stages).

## Conformity Package
| Option | Selected |
|--------|----------|
| Dynamic generation | |
| Static release snapshot | |
| Both | ✓ |

**User's choice:** Both.

## Review Notifications
| Option | Selected |
|--------|----------|
| Webhook only | |
| Webhook + API | |
| Webhook + API + email | ✓ |

**User's choice:** Full set.

## Governance Versioning
**User's choice:** Version forever (append-only, never overwrite). For policies, providers, presets. Includes approval history, diff history, rollback support.
