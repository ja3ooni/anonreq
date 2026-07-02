# AnonReq v5 — Requirements Document

**Version:** 1.0  
**Date:** 2026-07-02  
**Status:** Active

---

## Introduction

This document defines all requirements for AnonReq v5 (Phases 22–32), organized into four stages:

- **Stage 4 (Phases 22–24)**: Appliance Foundation — packaging, transparent proxy, marketplace listings
- **Stage 5 (Phases 25–27)**: Infrastructure Integrations — AWS, GCP, Azure, NodeShift native integrations
- **Stage 6 (Phases 28–30)**: Vanata Core — EU, Middle East, Asia compliance modules
- **Stage 7 (Phases 31–32)**: Vertical Tracks — Insurance and Legal compliance

All requirements use WHEN/IF/SHALL grammar for traceability and testability.

---

## Glossary

Terms from core requirements document (`requirements.md`) and enterprise requirements (`requirements_v2.md`) apply. Additional v5-specific terms:

- **Appliance Mode**: A deployment configuration where AnonReq operates as a standalone network appliance or transparent proxy, intercepting AI traffic without requiring application code changes or explicit routing configuration.
- **Transparent Proxy**: A network proxy that intercepts traffic via TLS interception or eBPF without requiring client applications to explicitly configure a proxy endpoint.
- **Native Package**: An operating system-specific installer that registers AnonReq as a system service (launchd on macOS, systemd on Linux, Windows Service on Windows).
- **Marketplace Listing**: A cloud provider marketplace offering (AWS Marketplace, GCP Marketplace, Azure Marketplace) that enables one-click deployment and billing through cloud provider accounts.
- **Infrastructure Embed**: An OEM or partnership arrangement where AnonReq is integrated into a third-party infrastructure platform (NodeShift, AWS, GCP, Azure) as a built-in compliance layer.
- **Vanata**: The compliance automation module of AnonReq that provides jurisdiction-specific control mappings, automated evidence collection, and audit-ready export packages for EU, Middle East, and Asia-Pacific data privacy regimes.
- **Jurisdiction Module**: A Vanata component that implements data privacy controls, entity detection, and compliance workflows for a specific regulatory regime (e.g., Saudi PDPL, UAE PDPL, China PIPL).
- **Control Mapping**: A documented relationship between AnonReq features/audit events and specific regulatory control requirements (e.g., "PII detection" → GDPR Article 32 "appropriate technical measures").
- **Evidence Package**: A machine-readable and human-readable export of compliance evidence (audit logs, control mappings, configuration snapshots) formatted for regulator submission.


---

## Stage 4: Appliance Foundation (Phases 22–24)

### Phase 22: Appliance Packaging & Distribution

#### Requirement PKG-01: Docker Multi-Arch Image

**User Story**: As a platform engineer, I want to deploy AnonReq via Docker on any architecture (amd64, arm64), so that I can run it on AWS Graviton, Apple Silicon, or x86 infrastructure without rebuilding.

**Acceptance Criteria**:

1. THE build pipeline SHALL produce a multi-architecture Docker image supporting linux/amd64 and linux/arm64 platforms.

2. THE Docker image SHALL be published to GitHub Container Registry (ghcr.io) and Docker Hub under versioned tags (e.g., `v3.0.0`, `v3.0`, `v3`, `latest`).

3. WHEN a user runs `docker pull anonreq/gateway:latest`, THE Docker runtime SHALL automatically select the architecture-appropriate image for the host platform.

4. THE Docker image SHALL include all runtime dependencies (Python 3.12, Presidio models, Valkey/Redis client libraries) and SHALL NOT require internet access at runtime to download additional dependencies.

5. THE Docker image SHALL pass automated security scanning (Trivy or equivalent) with zero critical or high-severity CVEs before release.

6. THE Docker image size SHALL be ≤ 2GB (uncompressed) for the amd64 variant.


#### Requirement PKG-02: Helm Chart & Kubernetes Operator

**User Story**: As a platform engineer, I want to deploy AnonReq on Kubernetes with a single `helm install` command, so that it integrates with my existing k8s infrastructure (ingress, service mesh, secrets, monitoring).

**Acceptance Criteria**:

1. THE AnonReq Helm chart SHALL support Kubernetes 1.24+ and SHALL be published to a public Helm repository (Artifact Hub).

2. THE Helm chart SHALL include configurable values for: replica count, resource limits, ingress configuration, TLS certificates, cache backend (Valkey/Redis), provider credentials (stored as Kubernetes Secrets), and observability integrations (Prometheus, Jaeger).

3. WHEN deployed via Helm, THE chart SHALL create all required Kubernetes resources: Deployment, Service, ConfigMap, Secret, Ingress (optional), ServiceMonitor (for Prometheus scraping).

4. THE Helm chart SHALL support rolling updates with zero downtime: new pods SHALL become ready before old pods are terminated.

5. THE Helm chart SHALL include liveness and readiness probes that check `/health` endpoint and fail if the Gateway or Detection_Engine is unhealthy.

6. THE Helm chart SHALL optionally deploy a bundled Valkey/Redis instance for development/testing, with persistence disabled by default.

#### Requirement PKG-03: Linux Native Packages (.deb, .rpm)

**User Story**: As a Linux system administrator, I want to install AnonReq via `apt install anonreq` or `yum install anonreq`, so that it integrates with my OS package management and runs as a systemd service.

**Acceptance Criteria**:

1. THE build pipeline SHALL produce `.deb` packages for Ubuntu 22.04+, Debian 11+, and `.rpm` packages for RHEL 9+, Fedora 38+, Amazon Linux 2023.

2. WHEN installed via `apt install anonreq` or `yum install anonreq`, THE package SHALL: (a) install binaries to `/usr/bin/anonreq`, (b) install configuration to `/etc/anonreq/config.yaml`, (c) create a system user `anonreq` with no shell, (d) register a systemd service `anonreq.service`, (e) start the service automatically.

3. THE systemd service SHALL restart automatically on failure (Restart=on-failure), with exponential backoff.

4. THE package SHALL include post-install hooks that: (a) generate self-signed TLS certificates if none exist, (b) initialize cache connection configuration, (c) print post-install instructions to stdout.

5. THE package SHALL support clean uninstallation: `apt remove anonreq` or `yum remove anonreq` SHALL stop the service, remove binaries, but preserve configuration in `/etc/anonreq/` (user can manually delete).

6. THE package SHALL be signed with GPG (for .deb) or RPM signing key, and the public key SHALL be published in package repository metadata.

