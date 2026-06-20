# Phase 7: Developer Experience & Documentation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-20
**Phase:** 7-Developer Experience & Documentation
**Areas discussed:** Quickstart format, SDK examples, README depth, Doc CI/infra

---

## Quickstart Format

| Option | Description | Selected |
|--------|-------------|----------|
| One file per language | 5 separate files (docs/getting-started-en.md, etc.) | |
| Single combined file | One file with sections per language | |
| Separate dir per language | docs/en/, docs/de/, etc. | ✓ |

**User's choice:** Separate directory per language. English is source language; translations are generated artifacts from English and never manually edited. MVP languages: EN + DE only. Expansion criteria: ≥3 enterprise prospects, ≥10% traffic, or paid customer requirement.

**Notes:**
- Structure: `docs/{lang}/` with full doc suite per language (getting-started, installation, deployment, compliance, FAQ)
- Quickstarts are executable scripts in `examples/quickstart/` — CI-tested with verification assertions
- Future rollout: v1.1 FR+ES, v1.2 AR+PT-BR, v1.3 IT+NL
- Language expansion only on-demand — no speculative translation

---

## SDK Examples

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone runnable projects | examples/python/, examples/node/, etc. with own configs | ✓ |
| Inline code snippets | Code in markdown docs only | |
| Hybrid | Runnable for Python/Node, inline for curl | |

**User's choice:** Standalone runnable projects. Languages: curl, Python, TypeScript, Go. 4 examples per language (16 total): Basic Anonymization, Streaming, Compliance Preset (GDPR), Locale-Specific Detection (DE). All CI-tested as acceptance tests. Gateway repo is canonical source of truth.

**Notes:**
- Shared `examples/datasets/` directory with `sample-pii.json` and `expected-results.json`
- Docs reference examples, never contain primary code
- If an example cannot execute in CI, it doesn't belong in `examples/`

---

## README Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal + link to docs | Logo, one-paragraph, install, quickstart link, license | |
| Medium | Badges, TOC, install, quickstart, features, arch diagram, docs links, license | ✓ |
| Full landing page | Everything including API ref, contributing, roadmap, FAQ | |

**User's choice:** Medium+ (~500-1000 lines). 13 sections. Security-first hero section then technical details then community. Architecture diagram: Mermaid source with auto-generated SVG+PNG, CI-validated. Apache 2.0 + brief commercial tier note near end.

**Notes:**
- No startup marketing language, no generic AI hype
- Enterprise features (SSO/SAML, RBAC, etc.) clearly separated from OSS core
- README structure: Security → Architecture → Usage → Docs → Community

---

## Doc CI/Infra

| Option | Description | Selected |
|--------|-------------|----------|
| Markdown linting only | Formatting and broken links | |
| Markdown + quickstart execution | Lint + execute all examples | |
| Full doc pipeline | Lint, quickstart execution, diagram validation, CHANGELOG format, version bump check | ✓ |

**User's choice:** Full CI pipeline. Required: markdown linting, link validation, Mermaid validation, diagram generation, example execution, quickstart execution, OpenAPI sync. Warnings: translation drift, CHANGELOG reminders, roadmap consistency. Nightly: full build + cross-platform checks. CI enforces CHANGELOG format AND version bump.

**Notes:**
- Principle: documentation is executable and testable, not static text
- OpenAPI spec auto-generated from FastAPI in CI

---

## the agent's Discretion

- Example file names and internal organization within each language dir
- Specific markdown tooling choices (linter, link checker)
- Exact Mermaid diagram style and layout
- README image asset generation pipeline details

## Deferred Ideas

- Sales docs (executive one-pager, buyer guide, ROI calculator, competitive comparison) — post-MVP
- Trust Center (security.md, privacy.md, sub-processors.md) — Phase 7.5 candidate
- CI gate for load test thresholds — from Phase 5 deferred
- Performance regression test under Hypothesis — from Phase 6 deferred
- Reasoning stream anonymization — from Phase 3 deferred
