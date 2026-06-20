# AnonReq Master Documentation

## Documentation System

MkDocs Material publishes architecture, operations, security, deployment, compliance, SDK, and quickstart documentation. OpenAPI is generated from FastAPI and treated as the SDK source of truth. Documentation includes English source and selected translated quickstarts.

## Required Document Sets

- Architecture: system overview, trust boundaries, data flows, sequence diagrams, provider adapters, streaming design, and appliance topology.
- Operations: deployment, health checks, scaling, SLO runbooks, fail-secure alert handling, backup/restore, secret rotation, and resilience testing.
- Security: threat model, incident response, vulnerability disclosure, RBAC matrix, secrets handling, supply chain, and no-PII logging guarantees.
- Compliance: GDPR, DORA, NIS2, ISO 27001, ISO 42001, SOC 2, SEC/FINRA/SR 11-7 mappings, conformity packages, and evidence exports.
- Developer: quickstarts, SDK examples, OpenAI base URL migration, streaming examples, and troubleshooting.

## Drift Controls

CI validates links, markdown style, OpenAPI sync, diagram rendering, translated quickstart freshness, and traceability updates for every feature PR.
