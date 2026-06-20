# AnonReq Master CI/CD

## Pipeline

GitHub Actions runs linting, type checks, unit tests, property tests, integration tests with service containers, OpenAPI generation, SDK contract tests, documentation validation, k6 smoke/load scenarios, container builds, SBOM generation, vulnerability scanning, image signing, and release artifact publication.

## Supply Chain

Every release publishes Python and container SBOMs in CycloneDX JSON, attaches image attestations with cosign, scans dependencies weekly, and blocks critical CVEs unless an approved risk exception exists. Docker images use Python 3.12 slim multi-stage builds and contain only runtime code plus required model artifacts.

## Environments

Development permits `.env` secrets and Docker Compose. Staging and production require external secrets managers, TLS/mTLS, PostgreSQL, HA Valkey, Helm deployment, readiness/liveness probes, and signed image provenance.
