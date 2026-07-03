# Phase 18 Discussion Log: Trust Center

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Decision

The architecture review approved implementing Trust Center as tenant-scoped gateway services integrated before ForwardingGuard, with metadata-only audit, bounded Prometheus metrics, RBAC-protected administration, OpenAPI-first contracts, and explicit security acceptance gates.

## Alternatives

- Build the feature as a separate sidecar service.
- Persist richer request context for easier debugging.
- Allow best-effort behavior when optional dependencies are unavailable.
- Implement provider-specific shortcuts for faster delivery.

## Why Rejected

- A sidecar adds network hops and a second enforcement boundary before the core gateway has stable internal interfaces.
- Rich persisted context risks storing raw prompts, responses, tokens, or entity values and conflicts with the no-PII logging model.
- Best-effort behavior weakens the product's fail-secure guarantee and is not acceptable for regulated deployments.
- Provider-specific shortcuts create schema drift and can bypass restoration, policy, and audit invariants.

## Risks

- Configuration complexity can create operator error.
- New API surfaces increase RBAC and audit coverage needs.
- Durable evidence systems can drift from runtime truth.
- Performance budgets can be exceeded if phase logic runs on every request without caching or short-circuiting.

## Mitigations

- Use typed configuration, startup validation, versioned policy bundles, and safe defaults.
- Add route-level permission metadata and matrix tests for every endpoint.
- Generate evidence from runtime records and sign manifests with SHA-256 hashes.
- Cache compiled policies, bound queue sizes, publish latency histograms, and load-test the hot path before release.
