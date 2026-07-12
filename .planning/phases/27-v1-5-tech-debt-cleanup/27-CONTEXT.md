# Phase 27: v1.5 Tech Debt Cleanup - Context

**Gathered:** 2026-07-12
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase closes three specific gaps surfaced by the v1.5 milestone audit
(`.planning/v1.5-MILESTONE-AUDIT.md`) — it does not add new capabilities or
re-open any Phase 23-26 scope decisions:

1. HYG-01's CI workflow would fail at collection today due to two broken
   test files unrelated to any v1.5 phase.
2. TRUST-01's Trust Center ships disabled by default, making a "public"
   feature invisible out of the box.
3. HYG-02's SUMMARY.md claims functionality (staged rollout) that isn't
   actually implemented.

</domain>

<decisions>
## Implementation Decisions

### HYG-01: Broken test files
- **D-01:** Delete `tests/test_agent_approval.py` and `tests/test_agent_policy.py` outright — do not exclude via CI `--ignore`, do not skip-mark, do not quarantine.
- **D-02:** Confirmed via `git log --oneline main -- src/anonreq/agent/approval.py` and `.../policy.py` (both empty output) — `anonreq.agent.approval`, `.policy`, `.inspector`, `.registry` never existed anywhere in `main`'s history. These are aspirational tests for a feature that was never built, not tests for code that regressed. Safe to delete with no functional loss.
- **D-03 (explicit non-goal):** Do NOT implement `anonreq.agent.approval`/`.policy`/`.inspector`/`.registry`. Building an agent-approval/policy feature is new scope and belongs in its own future phase if ever prioritized — not part of this cleanup.

### Trust Center default
- **D-04:** Flip `config/trust_center.yaml` from `enabled: false` to `enabled: true`.
- **D-05:** Rationale carried forward from Phase 24's CONTEXT.md (D9): Trust Center was designed as a public, no-auth compliance portal ("Public Access... No API key required"). Shipping it off by default contradicts that design intent — the feature is effectively invisible unless an operator already knows to flip a YAML flag they have no reason to look for.
- **D-06:** No other Phase 24 behavior changes — rate limiting (60 RPM/IP), fail-closed-503, and aggregate-only responses (Phase 24 D8, D10, D11) are unaffected by this default flip.

### HYG-02 doc correction
- **D-07:** Correct `.planning/phases/23-engineering-hygiene/23-01-SUMMARY.md` — remove or rewrite the "staged rollout" claim so it matches the actual implementation: a single global `strict = true` mypy block with per-module `ignore_missing_imports` overrides for untyped third-party packages, and a single global ruff rule set. No functional code change.
- **D-08 (explicit non-goal):** Do NOT build real per-directory/incremental strictness staging. That would be new scope (a genuine ruff/mypy rollout mechanism), not a documentation fix.

### Claude's Discretion
- Exact wording of the corrected SUMMARY.md language (D-07) — no specific phrasing was dictated, just "make it match reality."
- Whether to add a one-line comment in `config/trust_center.yaml` near `enabled: true` noting it can be disabled by operators who want it off — reasonable addition, not required by the discussion.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Audit findings driving this phase
- `.planning/v1.5-MILESTONE-AUDIT.md` — full audit report; see "Tech Debt by Phase" and "Recommendations" sections for the exact findings this phase closes

### Prior phase decisions this phase touches
- `.planning/phases/23-engineering-hygiene/CONTEXT.md` — D6 (ruff config), D8 (mypy config), D14 (CI test selection) — HYG-01/HYG-02 baseline decisions being corrected/fixed here
- `.planning/phases/23-engineering-hygiene/23-01-SUMMARY.md` — contains the "staged rollout" claim to be corrected (D-07)
- `.planning/phases/24-trust-center/CONTEXT.md` — D9 (public access, no auth) — rationale for flipping the default (D-04/D-05)
- `.github/workflows/test.yml` — CI workflow that currently fails at collection; must go green after D-01/D-02

### Requirements
- `.planning/milestones/v1.5-REQUIREMENTS.md` — HYG-01, HYG-02, TRUST-01 original requirement text (all previously marked complete; this phase corrects gaps found post-hoc, not new requirements)

</canonical_refs>

<code_context>
## Existing Code Insights

### Files to delete
- `tests/test_agent_approval.py` — imports `anonreq.agent.approval.{ApprovalStatus,ToolApprovalQueue}` and `anonreq.agent.inspector.{InspectionResult,SensitivityLevel,ToolResultInspector}` — none exist in `src/anonreq/agent/` (confirmed: only `config.py`, `mcp_parser.py`, `metrics.py`, `result_sanitizer.py`, `schema.py`, `tool_inspector.py` exist there)
- `tests/test_agent_policy.py` — imports `anonreq.agent.policy.*` and `anonreq.agent.registry.ToolPermit` — same situation, neither module exists

### Files to modify
- `config/trust_center.yaml` — single field change: `enabled: false` → `enabled: true`
- `.planning/phases/23-engineering-hygiene/23-01-SUMMARY.md` — text correction only, no code

### Established Patterns
- `.github/workflows/test.yml` already uses `--ignore=tests/load -m "not load"` for the load-test exclusion pattern (Phase 23 D14) — confirms the project's existing convention is to exclude via pytest args when files should be skipped, but per D-01 these two files should be deleted rather than added to that ignore list, since they test nothing real.

### Integration Points
- None — this is a cleanup phase touching test files, one YAML config value, and one documentation file. No src/ production code changes beyond what's listed above.

</code_context>

<specifics>
## Specific Ideas

No specific implementation style preferences beyond the decisions above — this is a small, mechanical cleanup phase.

</specifics>

<deferred>
## Deferred Ideas

- **Agent approval/policy feature** (`anonreq.agent.approval`, `.policy`, `.inspector`, `.registry`) — if this capability is ever wanted, it needs its own phase with real requirements, not resurrection of these orphaned tests. Explicitly out of scope here (D-03).
- **Real staged ruff/mypy rollout mechanism** — per-directory or incremental strictness. Explicitly out of scope here (D-08); today's global-strict config works and isn't broken, just under-documented previously.

</deferred>

---

*Phase: 27-v1-5-tech-debt-cleanup*
*Context gathered: 2026-07-12*
