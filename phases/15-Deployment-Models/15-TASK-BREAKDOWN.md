# Phase 15 Task Breakdown: Deployment Models

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Epics

1. Domain model and configuration contract.
2. Gateway integration and fail-secure orchestration.
3. Administrative API and OpenAPI contract.
4. Audit, metrics, and evidence integration.
5. Test suite, documentation, and release gates.

## Stories

- As an administrator, I can configure Deployment Models for one tenant without affecting another tenant.
- As a security officer, I can inspect decisions and evidence without seeing raw prompt values or token strings.
- As an SRE, I can observe health, latency, failures, and SLO impact through Prometheus and structured events.
- As a developer, I receive deterministic HTTP status codes and structured error bodies for denied or failed requests.

## Tasks

- Define Pydantic models for configuration, decisions, errors, audit payloads, and API responses.
- Implement services: DockerPackaging, HelmChart, ValkeyHAProfiles, TransparentProxyRuntime, ApplianceBootstrapper, AirGapArtifactBundle, UpgradeController.
- Add repository interfaces and migrations for durable metadata when required.
- Wire phase execution into request context before ForwardingGuard.
- Add RBAC permissions and route metadata for every endpoint.
- Add structured audit events: deployment_preflight_failed, deployment_profile_changed, tls_interception_enabled, upgrade_started, upgrade_completed.
- Add Prometheus metrics: anonreq_readiness_state, anonreq_startup_preflight_seconds, anonreq_proxy_passthrough_total, anonreq_upgrade_events_total.
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
