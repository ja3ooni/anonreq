# Phase 27: v1.5 Tech Debt Cleanup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-12
**Phase:** 27-v1-5-tech-debt-cleanup
**Areas discussed:** HYG-01 broken test files, Trust Center default, HYG-02 doc correction

---

## HYG-01: Broken test files

| Option | Description | Selected |
|--------|-------------|----------|
| Delete both files | They test nothing that exists; deleting removes dead weight and unblocks CI immediately | ✓ |
| Exclude via --ignore in CI only | Add --ignore flags to test.yml but leave the files as a marker of unfinished work | |
| Something else | Free-text alternative (skip-mark, quarantine dir, etc.) | |

**User's choice:** Delete both files (Recommended option)
**Notes:** Confirmed via git history check that `anonreq.agent.approval`, `.policy`, `.inspector`, `.registry` never existed in `main` — these are aspirational tests for a never-built feature, not regressed tests for real code.

---

## Trust Center default

| Option | Description | Selected |
|--------|-------------|----------|
| Flip to enabled: true | TRUST-01/02 were designed as a public-by-default portal (Phase 24 CONTEXT.md D9: "no auth required"); shipping off by default makes it invisible | ✓ |
| Keep enabled: false, document opt-in | Treat as an enterprise feature operators explicitly turn on | |

**User's choice:** Flip to enabled: true (Recommended option)
**Notes:** No follow-up questions — user accepted the recommendation directly.

---

## HYG-02 doc correction

| Option | Description | Selected |
|--------|-------------|----------|
| Correct the doc language only | Edit Phase 23 SUMMARY.md to remove the "staged rollout" claim; global-strict config already works, no code change needed | ✓ |
| Build real staged rollout | Implement actual per-directory mypy/ruff exemptions or incremental strictness | |

**User's choice:** Correct the doc language only (Recommended option)
**Notes:** User explicitly treated "build real staging" as scope creep beyond "fix the doc."

---

## Claude's Discretion

- Exact wording of the corrected SUMMARY.md language
- Whether to add an explanatory comment near `enabled: true` in `config/trust_center.yaml`

## Deferred Ideas

- Agent approval/policy feature (`anonreq.agent.approval`, `.policy`, `.inspector`, `.registry`) — would need its own phase with real requirements if ever prioritized
- Real staged ruff/mypy rollout mechanism (per-directory or incremental strictness)
