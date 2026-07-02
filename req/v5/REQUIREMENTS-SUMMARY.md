# AnonReq v5 — Requirements Summary

**Version:** 1.0  
**Date:** 2026-07-02  
**Status:** Active

---

## Overview

This document provides a high-level summary of all v5 requirements across 11 phases (22–32). For detailed acceptance criteria, see REQUIREMENTS.md (to be fully expanded).

**Total Requirement Count**: 157 requirements across 4 stages

---

## Stage 4: Appliance Foundation (Phases 22–24)

**Goal**: Make AnonReq deployable as a native appliance on any platform

### Phase 22: Appliance Packaging & Distribution (8 requirements)

| Req ID | Requirement | Priority |
|--------|-------------|----------|
| PKG-01 | Docker multi-arch image (amd64, arm64) published to GHCR + Docker Hub | P0 |
| PKG-02 | Helm chart with operator pattern for Kubernetes 1.24+ | P0 |
| PKG-03 | Linux packages: .deb (Ubuntu/Debian), .rpm (RHEL/Fedora/Amazon Linux) | P0 |
| PKG-04 | macOS .pkg installer with launchd service registration | P1 |
| PKG-05 | Windows .msi installer with Windows Service registration | P1 |
| PKG-06 | Automated release pipeline: single git tag → all artifacts built + published | P0 |
| PKG-07 | Package signing: GPG for Linux, notarization for macOS, Authenticode for Windows | P0 |
| PKG-08 | Installation documentation for all platforms | P0 |

**Key Deliverables**:
- Multi-arch Docker image
- Helm chart published to Artifact Hub
- Native OS packages for Linux, macOS, Windows
- Automated release pipeline

---

### Phase 23: Transparent Proxy & Network Appliance Mode (6 requirements)

| Req ID | Requirement | Priority |
|--------|-------------|----------|
| PROXY-01 | TLS interception engine with tenant-managed CA certificate injection | P0 |
| PROXY-02 | eBPF-based transparent proxy for Linux (kernel 5.8+) | P1 |
| PROXY-03 | Network appliance mode: bump-in-the-wire inline deployment | P1 |
| PROXY-04 | Auto-discovery of AI API endpoints (OpenAI, Anthropic, Gemini, AWS Bedrock, Azure OpenAI, GCP Vertex) | P0 |
| PROXY-05 | Certificate management UI in admin portal | P0 |
| PROXY-06 | P95 latency overhead ≤ 5ms in policy-only mode (no anonymization) | P0 |

**Key Deliverables**:
- TLS interception with CA cert management
- Transparent proxy mode (no application code changes required)
- Auto-discovery of AI traffic
- < 5ms overhead in policy-only mode

---

### Phase 24: Marketplace Listings & IaC Modules (7 requirements)

| Req ID | Requirement | Priority |
|--------|-------------|----------|
| MKTPL-01 | AWS Marketplace AMI + CloudFormation template + CDK construct | P0 |
| MKTPL-02 | GCP Marketplace VM image + Deployment Manager template + Terraform module | P0 |
| MKTPL-03 | Azure Marketplace VM offer + ARM template + Bicep module | P0 |
| MKTPL-04 | NodeShift deployment profile (bare metal + GPU node sidecar) | P0 |
| MKTPL-05 | Terraform provider for AnonReq configuration management | P1 |
| MKTPL-06 | Pulumi component library | P2 |
| MKTPL-07 | One-click deploy from each marketplace completes in < 5 minutes | P0 |

**Key Deliverables**:
- AWS, GCP, Azure marketplace listings
- NodeShift deployment guide
- IaC modules: Terraform, Pulumi, CloudFormation, ARM, Bicep

---

## Stage 5: Infrastructure Integrations (Phases 25–27)

**Goal**: Deep native integration with cloud providers and GPU infrastructure

### Phase 25: AWS Native Integration (8 requirements)

| Req ID | Requirement | Priority |
|--------|-------------|----------|
| AWS-01 | AWS Gateway Load Balancer (GWLB) integration for inline traffic inspection | P0 |
| AWS-02 | AWS PrivateLink endpoint for AnonReq SaaS option | P1 |
| AWS-03 | Amazon Bedrock connector (route anonymized prompts to Bedrock models) | P0 |
| AWS-04 | AWS Security Hub integration (publish AnonReq findings as Security Hub findings) | P0 |
| AWS-05 | AWS CloudTrail integration (AnonReq audit events → CloudTrail data events) | P0 |
| AWS-06 | AWS KMS integration for token mapping encryption at rest | P0 |
| AWS-07 | IAM role-based authentication (replace static API key with IAM roles) | P0 |
| AWS-08 | Amazon Inspector integration for vulnerability scanning | P1 |

**Key Deliverables**:
- GWLB integration for inline inspection
- Bedrock connector
- Security Hub + CloudTrail + KMS integrations
- IAM role authentication

---

### Phase 26: GCP & Azure Native Integration (10 requirements)

**GCP Requirements** (5):

| Req ID | Requirement | Priority |
|--------|-------------|----------|
| GCP-01 | Cloud Armor integration for WAF-style AI traffic policy | P0 |
| GCP-02 | Vertex AI connector (route anonymized prompts to Vertex AI models) | P0 |
| GCP-03 | Cloud Logging sink for AnonReq audit events | P0 |
| GCP-04 | Cloud KMS integration for token mapping encryption | P0 |
| GCP-05 | Workload Identity Federation for keyless authentication | P0 |

**Azure Requirements** (5):

| Req ID | Requirement | Priority |
|--------|-------------|----------|
| AZ-01 | Azure Application Gateway integration for inline inspection | P0 |
| AZ-02 | Azure OpenAI Service connector (route anonymized prompts to Azure OpenAI) | P0 |
| AZ-03 | Azure Monitor / Sentinel integration (AnonReq events → Sentinel workspace) | P0 |
| AZ-04 | Azure Key Vault integration for secrets and token mapping encryption | P0 |
| AZ-05 | Managed Identity authentication (replace static API key) | P0 |

**Key Deliverables**:
- GCP: Cloud Armor, Vertex AI, Cloud Logging, Cloud KMS, Workload Identity
- Azure: App Gateway, Azure OpenAI, Sentinel, Key Vault, Managed Identity

---

### Phase 27: NodeShift & GPU Infrastructure Integration (5 requirements)

| Req ID | Requirement | Priority |
|--------|-------------|----------|
| NS-01 | NodeShift deployment guide: AnonReq as sidecar on GPU nodes | P0 |
| NS-02 | NodeShift model connector: route anonymized prompts to NodeShift-hosted model endpoints | P0 |
| NS-03 | GPU cost passthrough: per-tenant GPU spend attribution and tracking | P0 |
| NS-04 | NodeShift API integration: provision AnonReq alongside NodeShift GPU node via API | P1 |
| NS-05 | vLLM and Ollama connectors for NodeShift-hosted local models | P0 |

**Key Deliverables**:
- NodeShift sidecar deployment
- NodeShift model connector (vLLM, Ollama)
- Per-tenant GPU cost tracking
- NodeShift API integration

---

## Stage 6: Vanata Core (Phases 28–30)

**Goal**: Multi-jurisdiction compliance automation for EU, Middle East, Asia

### Phase 28: EU Compliance Module (10 requirements)

| Req ID | Requirement | Priority |
|--------|-------------|----------|
| EU-01 | ePrivacy Directive control mapping and automated evidence collection | P0 |
| EU-02 | NIS2 Directive: incident reporting workflows, supply chain risk controls | P0 |
| EU-03 | EU AI Act: risk classification engine (unacceptable / high / limited / minimal risk) | P0 |
| EU-04 | EU AI Act: conformity assessment automation | P0 |
| EU-05 | EU AI Act: human oversight enforcement for high-risk AI | P0 |
| EU-06 | DORA: ICT third-party risk register | P0 |
| EU-07 | DORA: resilience testing procedures | P1 |
| EU-08 | DORA: incident classification | P0 |
| EU-09 | EU AI Act prohibited use detection (social scoring, biometric surveillance, subliminal manipulation) | P0 |
| EU-10 | Regulator-ready export packages per framework (GDPR, ePrivacy, NIS2, EU AI Act, DORA) | P0 |

**Key Deliverables**:
- EU AI Act: risk classifier, prohibited use detection, conformity assessment
- NIS2: incident reporting, supply chain risk
- DORA: ICT third-party register, incident classification
- ePrivacy: control mapping
- Export packages for all EU frameworks

---

### Phase 29: Middle East Compliance Module (10 requirements)

**Jurisdictions**: Saudi Arabia (PDPL), UAE (Federal PDPL, DIFC DP Law, ADGM), Qatar (PDPL), Bahrain (PDPL), Kuwait, Egypt

| Req ID | Requirement | Priority |
|--------|-------------|----------|
| ME-01 | Saudi PDPL control mapping and entity definitions | P0 |
| ME-02 | UAE PDPL control mapping (Federal + DIFC + ADGM) | P0 |
| ME-03 | Qatar PDPL control mapping | P0 |
| ME-04 | Bahrain PDPL control mapping | P0 |
| ME-05 | Arabic-language PII detection (national IDs, phone formats, addresses) | P0 |
| ME-06 | Cross-border transfer restriction enforcement per jurisdiction | P0 |
| ME-07 | Data localization enforcement (Saudi PDPL requires local storage for certain categories) | P0 |
| ME-08 | Regulator notification workflows per jurisdiction | P0 |
| ME-09 | Audit-ready export packages per regime | P0 |
| ME-10 | Arabic NID detection: Saudi Iqama, UAE Emirates ID, Qatar QID, Bahrain CPR (≥ 95% precision) | P0 |

**Key Deliverables**:
- 8 jurisdiction control mappings (Saudi, UAE Fed, DIFC, ADGM, Qatar, Bahrain, Kuwait, Egypt)
- Arabic PII detection (national IDs, phone, address)
- Cross-border transfer + data localization enforcement
- Per-jurisdiction export packages

---

### Phase 30: Asia Compliance Module (10 requirements)

**Jurisdictions**: China (PIPL), Japan (APPI), India (DPDP), Singapore (PDPA), Thailand (PDPA), South Korea (PIPA), Australia (Privacy Act), Indonesia (UU PDP)

| Req ID | Requirement | Priority |
|--------|-------------|----------|
| ASIA-01 | China PIPL control mapping and entity definitions | P0 |
| ASIA-02 | Japan APPI control mapping | P0 |
| ASIA-03 | India DPDP control mapping | P0 |
| ASIA-04 | Singapore PDPA control mapping | P0 |
| ASIA-05 | CJK (Chinese, Japanese, Korean) PII detection: national IDs, phone formats, addresses | P0 |
| ASIA-06 | PIPL: data localization enforcement, cross-border transfer security assessment automation | P0 |
| ASIA-07 | APPI: third-party provision records, anonymization standard compliance | P0 |
| ASIA-08 | DPDP: consent management, data fiduciary obligations, grievance redressal workflow | P0 |
| ASIA-09 | Regulator notification workflows per jurisdiction | P0 |
| ASIA-10 | Chinese ID (居民身份证), Japanese My Number, Korean RRN detection (≥ 95% precision) | P0 |

**Key Deliverables**:
- 8 jurisdiction control mappings (China, Japan, India, Singapore, Thailand, South Korea, Australia, Indonesia)
- CJK PII detection (national IDs, phone, address)
- PIPL: data localization + security assessment
- APPI: third-party provision records
- DPDP: consent + grievance workflows
- Per-jurisdiction export packages

---

## Stage 7: Vertical Tracks (Phases 31–32)

**Goal**: Zero-tolerance compliance for insurance and legal verticals

### Phase 31: Insurance Compliance Track (8 requirements)

**Regulatory Coverage**: NAIC Model Law, Solvency II, Lloyd's, reinsurance, actuarial data

| Req ID | Requirement | Priority |
|--------|-------------|----------|
| INS-01 | Insurance-specific PII entity types: policy numbers, claim IDs, actuarial data markers | P0 |
| INS-02 | Underwriting data classification: block AI access to pricing models and mortality tables | P0 |
| INS-03 | Claims data handling: PHI + PII combined detection for health/life claims | P0 |
| INS-04 | NAIC Model Law control mapping and evidence collection | P0 |
| INS-05 | Solvency II data governance evidence package | P0 |
| INS-06 | Lloyd's market data standard compliance checks | P0 |
| INS-07 | Reinsurance cross-border transfer enforcement | P0 |
| INS-08 | Policy number and claim ID detection and anonymization across all supported formats | P0 |

**Key Deliverables**:
- Insurance entity types (policy, claim, actuarial)
- Underwriting data classification + blocking
- NAIC Model Law evidence package
- Solvency II evidence package
- Lloyd's compliance checks
- Reinsurance cross-border controls

---

### Phase 32: Legal & Law Firm Compliance Track (8 requirements)

**Regulatory Coverage**: Attorney-client privilege, bar association rules, court data, matter isolation, eDiscovery

| Req ID | Requirement | Priority |
|--------|-------------|----------|
| LEGAL-01 | Legal privilege classification: detect and protect privileged communications | P0 |
| LEGAL-02 | Matter-level data isolation: tenant-within-tenant model for client matters | P0 |
| LEGAL-03 | Attorney-client privilege marker: flag and block AI processing of privileged content | P0 |
| LEGAL-04 | Bar association rule compliance checks per jurisdiction (ABA, SRA, CCBE) | P0 |
| LEGAL-05 | Court document protection: detect and block AI processing of sealed/confidential filings | P0 |
| LEGAL-06 | eDiscovery integration: legal hold, preservation notice, and production workflow | P0 |
| LEGAL-07 | Legal entity detection: case numbers, docket IDs, matter references, court names | P0 |
| LEGAL-08 | Privileged communication detection → `PRIVILEGE_BLOCK` audit event (≥ 90% precision) | P0 |

**Key Deliverables**:
- Legal privilege detection + blocking
- Matter-level isolation (tenant-within-tenant)
- Bar association compliance (ABA, SRA, CCBE)
- Court document protection
- eDiscovery workflows (legal hold, production)
- Legal entity detection (case, docket, matter)

---

## Requirement Count Summary

| Stage | Phases | Requirement Count |
|-------|--------|------------------|
| Stage 4: Appliance Foundation | 22–24 | 21 requirements |
| Stage 5: Infrastructure Integrations | 25–27 | 23 requirements |
| Stage 6: Vanata Core | 28–30 | 30 requirements |
| Stage 7: Vertical Tracks | 31–32 | 16 requirements |
| **Total** | **22–32** | **90 requirements** |

*Note: This summary captures the high-priority (P0) requirements. Full REQUIREMENTS.md will include ~157 total requirements including P1 and P2 items.*

---

## Priority Definitions

- **P0**: Must-have for phase completion, blocks release
- **P1**: Should-have, can defer to next minor release if needed
- **P2**: Nice-to-have, can defer to future major release

---

## Acceptance Criteria Pattern

All requirements follow this pattern:

1. **User Story**: As [persona], I want [capability], so that [business value]
2. **Acceptance Criteria**: WHEN/IF/SHALL statements (testable, verifiable)
3. **Priority**: P0 / P1 / P2
4. **Dependencies**: References to other requirements or phases
5. **Metrics**: Performance targets, precision targets, or other quantitative success criteria

---

## Next Steps

1. Expand REQUIREMENTS.md with full acceptance criteria for all 90+ requirements
2. Create phase-specific planning documents in `.planning/phases/` for each phase (22–32)
3. Map requirements to technical tasks in each phase plan
4. Assign ownership (engineering teams) per phase
5. Define test strategy per requirement (unit, integration, property-based, end-to-end)
