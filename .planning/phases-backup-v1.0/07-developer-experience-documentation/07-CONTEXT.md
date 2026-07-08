# Phase 7: Developer Experience & Documentation - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Open-source ready repository with quickstarts, SDK examples, legal files, and documentation that enables a developer to evaluate and deploy AnonReq in under 15 minutes. No code changes — pure content creation and packaging.

Phase 7 covers technical documentation (getting-started, installation, deployment, API reference, FAQ), enterprise documentation (architecture overview, security model, compliance mapping), and adoption tooling (executable quickstarts, CI-tested SDK examples). The README positions AnonReq as a "Fail-secure AI Security Gateway for regulated enterprises" — security-first messaging followed by technical implementation details.

Three plans: 07-01 (quickstarts + doc structure), 07-02 (SDK examples + README), 07-03 (CHANGELOG, LICENSE, NOTICE, SECURITY.md, doc CI).

</domain>

<decisions>
## Implementation Decisions

### Quickstart Format
- **D-190:** Directory structure: `docs/{lang}/` per language (docs/en/, docs/de/, etc.). Each language has its own getting-started, installation, deployment, compliance, and FAQ pages.
- **D-191:** English is the source language. All other languages are generated artifacts from English and never manually edited. No language-to-language translation chain.
- **D-192:** MVP ships with EN + DE only. Future languages added on demand: ≥3 enterprise prospects request, or ≥10% website traffic from locale, or paid customer requirement.
- **D-193:** Language rollout plan: v1.0 = EN + DE; v1.1 = FR + ES; v1.2 = AR + PT-BR; v1.3 = IT + NL.
- **D-194:** Quickstarts are executable scripts in `examples/quickstart/` — not markdown with inline commands. Documentation references scripts rather than duplicating command text.
- **D-195:** Every quickstart script is CI-executed on every PR with verification assertions: gateway starts, health endpoint 200, sample anonymization succeeds, restoration succeeds, zero errors in logs.

### SDK Examples
- **D-196:** Standalone runnable projects in `examples/{lang}/` per language. Languages: curl, Python, TypeScript, Go. No markdown-only snippets as primary artifacts.
- **D-197:** 4 examples per language (16 total): Basic Anonymization, Streaming, Compliance Preset (GDPR), Locale-Specific Detection (DE). Each includes cleanup logic, failure assertions, and expected outputs.
- **D-198:** Examples are production-grade and CI-tested as acceptance tests. If an example cannot execute in CI, it does not belong in `examples/`.
- **D-199:** Gateway repository is canonical source of truth for examples. SDK repos may mirror examples but must never drift.
- **D-200:** Documentation references examples; docs never contain primary code. Single source of truth enforced by convention.
- **D-201:** Shared `examples/datasets/` directory with `sample-pii.json` and `expected-results.json`.

### README Depth
- **D-202:** Medium+ README (~500–1000 lines max). 13 sections: What is AnonReq, Why AnonReq Exists, Architecture Diagram, Core Features, Quick Start (5 min), Example Output, Compliance Support, Supported Providers, Documentation Links, Security Model, Roadmap, Contributing, License.
- **D-203:** Dual tone — security-first hero section ("Fail-secure AI Security Gateway for regulated enterprises"), then technical implementation details, then community/license sections. No startup marketing language, no generic AI hype.
- **D-204:** Architecture diagram: Mermaid source of truth, SVG + PNG generated automatically in CI. CI validates diagram generation. No draw.io sources, no manually edited PNGs.
- **D-205:** License section near the end of README: Apache 2.0 with brief note about enterprise features being available under separate commercial terms. Enterprise features (RBAC, SSO/SAML, multi-tenant, audit dashboards) clearly separated from OSS core.

### Documentation CI / Infrastructure
- **D-206:** Required CI checks on every PR: markdown linting, link validation, Mermaid validation, diagram generation, example execution, quickstart execution, OpenAPI schema sync.
- **D-207:** CI warnings (non-blocking): translation drift detection, CHANGELOG reminders, roadmap consistency checks.
- **D-208:** Nightly CI: full documentation build across all languages, cross-platform execution checks.
- **D-209:** CHANGELOG.md follows Keep a Changelog format. CI enforces format validation AND version bump check (version must be bumped for code changes, not docs-only PRs).
- **D-210:** OpenAPI spec auto-generated from FastAPI app in CI, included in `docs/` as API reference, referenced from README.
- **D-211:** Principle: documentation is executable and testable, not static text.

### the agent's Discretion
- Example file names, internal organization within each language dir, specific markdown tooling choices (linter, link checker), exact Mermaid diagram style.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` § DOCS-01 to DOCS-05 — Integration quickstarts (5 languages), SDK examples, CHANGELOG, license files, README
- `.planning/ROADMAP.md` § Phase 7 — Success criteria, 3 plans (07-01 to 07-03)
- `.planning/ARCHITECTURE_GUARDRAILS.md` — All 20 guardrails (AG-01 to AG-20) apply

### Prior Phase Decisions
- `.planning/phases/01-foundation-fail-secure-auth/01-CONTEXT.md` — D-01 to D-21 (auth, error handling, Docker scaffold)
- `.planning/phases/02-core-pipeline-classification-non-streaming/02-CONTEXT.md` — D-22 to D-53 (pipeline, detection, tokenization)
- `.planning/phases/03-sse-streaming-multi-provider/03-CONTEXT.md` — D-54 to D-109, AG-01 to AG-12 (streaming, providers)
- `.planning/phases/04-multi-locale-detection-compliance-presets/04-CONTEXT.md` — D-110 to D-137, AG-13–AG-14 (locale, compliance presets)
- `.planning/phases/05-configuration-observability/05-CONTEXT.md` — D-138 to D-161, AG-15–AG-18 (metrics, hot-reload)
- `.planning/phases/06-advanced-property-based-tests/06-CONTEXT.md` — D-162 to D-189, AG-19–AG-20 (property tests, security gate)
- `.planning/phases/06-advanced-property-based-tests/07-SECURITY-ACCEPTANCE.md` — Security acceptance gate (9 gates must pass before Phase 7)

### Project Decisions
- `.planning/PROJECT.md` — Python 3.12 + FastAPI, Presidio sidecar, Valkey, Docker Compose, Apache 2.0, fail-secure mandate

### Deployment Reference
- `.planning/phases/01-foundation-fail-secure-auth/01-ARCHITECTURE.md` — Docker Compose services, auth model
- `.planning/phases/05-configuration-observability/05-CONTEXT.md` § Load Testing — k6 setup, P95 targets

</canonical_refs>

<code_context>
## Existing Code Insights

No code exists yet (greenfield project). All code assets will be built by Phases 1–6 before Phase 7 begins.

### Integration Points
- Docker Compose services: `anonreq` + `presidio-analyzer` + `valkey` — must be referenced in quickstarts and deployment docs
- `POST /v1/chat/completions` — main endpoint for SDK examples
- `GET /v1/models` — provider enumeration for examples
- `GET /v1/compliance/presets` — compliance preset endpoint for GDPR example
- `GET /v1/config/rules` — custom rules endpoint
- `GET /health` — health check endpoint
- `GET /metrics` — Prometheus metrics endpoint

</code_context>

<specifics>
## Specific Ideas

- Quickstart scripts modeled after the user's preference: executable, CI-validated, failure-asserting
- README tone modeled after infrastructure security products (HashiCorp Vault, Tailscale) — security promise first, technical detail second
- OpenAPI auto-generation from FastAPI app (standard FastAPI feature, mount static file in CI)

</specifics>

<deferred>
## Deferred Ideas

- Sales docs (executive one-pager, buyer guide, ROI calculator, competitive comparison) — post-MVP adoption phase
- Trust Center (security.md, privacy.md, sub-processors.md, incident-response.md) — post-MVP Phase 7.5 candidate
- CI gate for load test thresholds — Phase 7+ (from Phase 5 deferred)
- Performance regression test under Hypothesis — Phase 7+ (from Phase 6 deferred)
- Reasoning stream anonymization — Phase 7+ (from Phase 3 deferred)

</deferred>

---

*Phase: 7-Developer Experience & Documentation*
*Context gathered: 2026-06-20*
