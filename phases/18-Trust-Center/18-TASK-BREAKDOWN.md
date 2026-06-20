# Phase 18 Task Breakdown: Trust Center

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Epics

1. Domain model and configuration contract.
2. Gateway integration and fail-secure orchestration.
3. Administrative API and OpenAPI contract.
4. Audit, metrics, and evidence integration.
5. Test suite, documentation, and release gates.

## Stories

- As an administrator, I can configure Trust Center for one tenant without affecting another tenant.
- As a security officer, I can inspect decisions and evidence without seeing raw prompt values or token strings.
- As an SRE, I can observe health, latency, failures, and SLO impact through Prometheus and structured events.
- As a developer, I receive deterministic HTTP status codes and structured error bodies for denied or failed requests.

## Tasks

- Define Pydantic models for configuration, decisions, errors, audit payloads, and API responses.
- Implement services: TrustCenterSite, PublicEvidencePublisher, SBOMPublisher, DetectionQualityPublisher, SLOStatusPublisher, SecurityQuestionnairePackager, LegalDocumentRegistry.
- Add repository interfaces and migrations for durable metadata when required.
- Wire phase execution into request context before ForwardingGuard.
- Add RBAC permissions and route metadata for every endpoint.
- Add structured audit events: trust_artifact_published, security_package_generated, public_slo_status_updated, sbom_published.
- Add Prometheus metrics: anonreq_trust_artifacts_published_total, anonreq_public_slo_status, anonreq_security_package_downloads_total.
- Update OpenAPI examples, MkDocs pages, runbooks, and traceability matrix.
- Add CI coverage for unit, integration, property, load, and security tests listed in the test plan.

## Estimates

- Domain model and config validation: 3 engineering days.
- Runtime services and orchestration: 8 engineering days.
- Admin APIs and OpenAPI: 4 engineering days.
- Audit, metrics, evidence, and documentation: 4 engineering days.
- Test automation and hardening: 6 engineering days.
- Security review fixes: 3 engineering days.

## Dependencies

Implementation depends on Stage 1 request context, audit logger, metrics registry, provider mocks, Valkey test fixture, PostgreSQL migration framework, and RBAC middleware. Work must land behind configuration flags until acceptance gates pass.
