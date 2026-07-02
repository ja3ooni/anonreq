# AnonReq v5 — Roadmap

**Produced:** 2026-07-02
**Continues from:** v4 Phases 1–21 (Stages 1–3)

---

## Overview

V5 adds two major capabilities on top of the existing gateway and enterprise platform:

1. **Universal Appliance** — AnonReq deploys as a native package or marketplace appliance on
   any infrastructure, acting as a transparent anonymization and audit layer.

2. **Vanata** — A jurisdiction-specific compliance automation module for EU, Middle East, Asia,
   insurance, and legal verticals.

---

## Stage 4: Appliance Foundation (Phases 22–24)

Goal: Make AnonReq deployable as a self-contained appliance on any platform without requiring
application code changes.

---

### Phase 22: Appliance Packaging & Distribution

**Goal**: Package AnonReq as a native installable for every major platform.

**Depends on**: Phase 17 (transparent proxy architecture), Phase 21 (sovereign control)

**Deliverables**:
- Docker image (multi-arch: amd64, arm64) published to GHCR and Docker Hub
- Helm chart with operator pattern for Kubernetes
- Linux `.deb` (Ubuntu/Debian) and `.rpm` (RHEL/Fedora/Amazon Linux) packages
- macOS `.pkg` installer with launchd service registration
- Windows `.msi` installer with Windows Service registration
- Automated release pipeline producing all artifacts from a single tag

**Requirements**: `PKG-01..08` (see REQUIREMENTS.md)

**Success Criteria**:
1. `apt install anonreq` / `yum install anonreq` installs and starts the service on Linux.
2. macOS `.pkg` installs, registers launchd service, starts on boot.
3. Windows `.msi` installs, registers Windows Service, starts on boot.
4. Helm chart deploys to Kubernetes with a single `helm install`.
5. All packages pass signature verification (GPG for Linux, notarization for macOS, Authenticode for Windows).

---

### Phase 23: Transparent Proxy & Network Appliance Mode

**Goal**: AnonReq intercepts AI traffic without requiring application code changes.

**Depends on**: Phase 17 (universal gateway), Phase 22 (packaging)

**Deliverables**:
- TLS interception engine with tenant-managed CA cert injection
- eBPF-based transparent proxy for Linux (kernel 5.8+)
- Network appliance mode: bump-in-the-wire inline deployment
- Auto-discovery of AI API endpoints (OpenAI, Anthropic, Gemini, AWS Bedrock, Azure OpenAI, etc.)
- Certificate management UI in admin portal

**Requirements**: `PROXY-01..06` (see REQUIREMENTS.md)

**Success Criteria**:
1. Existing application routes AI traffic through AnonReq with zero code changes.
2. TLS interception preserves end-to-end encryption between app and AnonReq, and AnonReq and provider.
3. P95 overhead in transparent proxy mode ≤ 5ms (policy evaluation only, no anonymization).
4. P95 overhead in transparent proxy + anonymization mode ≤ 100ms.
5. `block-all-unintercepted-AI` policy blocks direct AI API calls that bypass the proxy.

---

### Phase 24: Marketplace Listings & IaC Modules

**Goal**: AnonReq is available on all major cloud marketplaces and deployable via IaC.

**Depends on**: Phase 22 (packaging), Phase 23 (proxy mode)

**Deliverables**:
- AWS Marketplace AMI + CloudFormation template + CDK construct
- GCP Marketplace VM image + Deployment Manager template + Terraform module
- Azure Marketplace VM offer + ARM template + Bicep module
- NodeShift deployment profile (bare metal + GPU node sidecar)
- Terraform provider for AnonReq configuration management
- Pulumi component library

**Requirements**: `MKTPL-01..07` (see REQUIREMENTS.md)

**Success Criteria**:
1. One-click deploy from AWS Marketplace launches a working AnonReq instance in < 5 minutes.
2. One-click deploy from GCP Marketplace and Azure Marketplace equivalent.
3. NodeShift deployment guide: AnonReq running as compliance sidecar on NodeShift GPU node.
4. `terraform apply` with the AnonReq Terraform module deploys a complete stack.
5. All marketplace listings pass vendor security review.

---

## Stage 5: Infrastructure Integrations (Phases 25–27)

Goal: Deep native integration with each major cloud provider's security and networking fabric.

---

### Phase 25: AWS Native Integration

**Goal**: AnonReq integrates with AWS security, networking, and AI services as a first-class citizen.

**Depends on**: Phase 24 (marketplace listing)

**Deliverables**:
- AWS Gateway Load Balancer (GWLB) integration for inline traffic inspection
- AWS PrivateLink endpoint for AnonReq SaaS option
- Amazon Bedrock connector (route anonymized prompts to Bedrock models)
- AWS Security Hub integration (publish AnonReq findings as Security Hub findings)
- AWS CloudTrail integration (AnonReq audit events → CloudTrail data events)
- AWS KMS integration for token mapping encryption at rest
- IAM role-based authentication (replace static API key with IAM roles for EC2/ECS/Lambda)
- Amazon Inspector integration for vulnerability scanning of AnonReq deployments

**Requirements**: `AWS-01..08` (see REQUIREMENTS.md)

**Success Criteria**:
1. AnonReq deployed behind AWS GWLB intercepts all VPC egress AI traffic.
2. Bedrock connector routes anonymized prompts to Claude/Titan/Llama on Bedrock.
3. AnonReq findings appear in AWS Security Hub with correct severity mapping.
4. AnonReq audit events appear in CloudTrail as data events.
5. EC2 instance running AnonReq authenticates via IAM role — no static credentials.

---

### Phase 26: GCP & Azure Native Integration

**Goal**: Equivalent native integration depth for GCP and Azure.

**Depends on**: Phase 24 (marketplace listings)

**GCP Deliverables**:
- Cloud Armor integration for WAF-style AI traffic policy
- Vertex AI connector (route anonymized prompts to Vertex AI models)
- Cloud Logging sink for AnonReq audit events
- Cloud KMS integration for token mapping encryption
- Workload Identity Federation for keyless authentication

**Azure Deliverables**:
- Azure Application Gateway integration for inline inspection
- Azure OpenAI Service connector (route anonymized prompts to Azure OpenAI)
- Azure Monitor / Sentinel integration (AnonReq events → Sentinel workspace)
- Azure Key Vault integration for secrets and token mapping encryption
- Managed Identity authentication (replace static API key)

**Requirements**: `GCP-01..05`, `AZ-01..05` (see REQUIREMENTS.md)

**Success Criteria**:
1. GCP: AnonReq deployed with Cloud Armor intercepts Vertex AI traffic.
2. GCP: Vertex AI connector routes anonymized prompts to Gemini/PaLM on Vertex.
3. Azure: AnonReq events appear in Microsoft Sentinel as custom log table.
4. Azure: Azure OpenAI connector routes anonymized prompts to Azure OpenAI deployments.
5. Both: Keyless/managed identity authentication works end-to-end.

---

### Phase 27: NodeShift & GPU Infrastructure Integration

**Goal**: AnonReq runs as the compliance and anonymization layer on NodeShift-provisioned GPU infrastructure.

**Depends on**: Phase 24 (NodeShift deployment profile)

**Deliverables**:
- NodeShift deployment guide: AnonReq as sidecar on GPU nodes
- NodeShift model connector: route anonymized prompts to NodeShift-hosted model endpoints
- GPU cost passthrough: per-tenant GPU spend attribution and tracking
- NodeShift API integration: provision AnonReq alongside NodeShift GPU node via API
- vLLM and Ollama connectors for NodeShift-hosted local models

**Requirements**: `NS-01..05` (see REQUIREMENTS.md)

**Success Criteria**:
1. AnonReq sidecar deployed on NodeShift GPU node intercepts all model traffic.
2. Anonymized prompts route to NodeShift-hosted vLLM endpoint.
3. Per-tenant GPU cost tracked and attributed in AnonReq spend dashboard.
4. NodeShift API call provisions AnonReq alongside GPU node in single workflow.
5. vLLM and Ollama connectors pass full anonymization round-trip test.

---

## Stage 6: Vanata Core (Phases 28–30)

Goal: Build the Vanata compliance automation module covering all three major regional regimes.

---

### Phase 28: EU Compliance Module

**Goal**: Complete EU compliance coverage beyond GDPR — ePrivacy, NIS2, EU AI Act enforcement.

**Depends on**: Phase 16 (compliance audit), Phase 14 (AI governance)

**Deliverables**:
- ePrivacy Directive control mapping and automated evidence collection
- NIS2 Directive: incident reporting workflows, supply chain risk controls
- EU AI Act: risk classification engine (unacceptable / high / limited / minimal risk),
  conformity assessment automation, human oversight enforcement for high-risk AI
- DORA: ICT third-party risk register, resilience testing procedures, incident classification
- EU AI Act prohibited use detection (social scoring, biometric surveillance, subliminal manipulation)
- Regulator-ready export packages per framework

**Requirements**: `EU-01..10` (see REQUIREMENTS.md)

**Success Criteria**:
1. EU AI Act risk classifier correctly classifies AI use cases across all 4 risk tiers.
2. Prohibited use detection blocks requests matching EU AI Act Article 5 prohibitions.
3. NIS2 incident report generated and queued for regulator notification within SLA.
4. DORA ICT third-party register exportable in regulator-required format.
5. ePrivacy consent tracking integrated with anonymization pipeline.

---

### Phase 29: Middle East Compliance Module

**Goal**: Full compliance coverage for Middle East data privacy regimes.

**Depends on**: Phase 28 (EU module architecture as template)

**Jurisdictions**:
- Saudi Arabia: Personal Data Protection Law (PDPL) — SDAIA enforcement
- UAE: Federal Decree-Law No. 45 of 2021 on Personal Data Protection
- UAE DIFC: DIFC Data Protection Law 2020 (DIFC DP Law)
- UAE ADGM: ADGM Data Protection Regulations 2021
- Qatar: Personal Data Privacy Protection Law (Law No. 13 of 2016)
- Bahrain: Personal Data Protection Law (Law No. 30 of 2018)
- Kuwait: draft data protection framework (monitoring)
- Egypt: Personal Data Protection Law No. 151 of 2020

**Deliverables**:
- Per-jurisdiction control mappings and PII entity definitions
- Arabic-language PII detection (national IDs, phone formats, addresses)
- Cross-border transfer restriction enforcement per jurisdiction
- Data localization enforcement (Saudi PDPL requires local storage for certain categories)
- Regulator notification workflows per jurisdiction
- Audit-ready export packages per regime

**Requirements**: `ME-01..10` (see REQUIREMENTS.md)

**Success Criteria**:
1. Arabic NID (Saudi Iqama, UAE Emirates ID, Qatar QID) detected with ≥ 95% precision.
2. Saudi PDPL cross-border transfer restriction enforced: blocks transfer of sensitive categories
   to non-approved jurisdictions.
3. UAE PDPL consent record created and exportable per data subject request.
4. DIFC DP Law breach notification workflow triggers within 72-hour SLA.
5. All 8 jurisdictions have passing control mapping tests.

---

### Phase 30: Asia Compliance Module

**Goal**: Full compliance coverage for Asia-Pacific data privacy regimes.

**Depends on**: Phase 28 (EU module architecture as template)

**Jurisdictions**:
- China: Personal Information Protection Law (PIPL) — CAC enforcement
- Japan: Act on Protection of Personal Information (APPI) — PPC enforcement
- India: Digital Personal Data Protection Act (DPDP Act 2023) — DPBI enforcement
- Singapore: Personal Data Protection Act (PDPA) — PDPC enforcement
- Thailand: Personal Data Protection Act (PDPA) — PDPC enforcement
- South Korea: Personal Information Protection Act (PIPA) — PIPC enforcement
- Australia: Privacy Act 1988 (amended) — OAIC enforcement
- Indonesia: Personal Data Protection Law (UU PDP 2022)

**Deliverables**:
- Per-jurisdiction control mappings and PII entity definitions
- CJK (Chinese, Japanese, Korean) PII detection: national IDs, phone formats, addresses
- PIPL: data localization enforcement, cross-border transfer security assessment automation
- APPI: third-party provision records, anonymization standard compliance
- DPDP: consent management, data fiduciary obligations, grievance redressal workflow
- Regulator notification workflows per jurisdiction
- Audit-ready export packages per regime

**Requirements**: `ASIA-01..10` (see REQUIREMENTS.md)

**Success Criteria**:
1. Chinese ID (居民身份证), Japanese My Number, Korean RRN detected with ≥ 95% precision.
2. PIPL cross-border transfer security assessment generated and exportable.
3. DPDP consent record created per data principal with full audit trail.
4. APPI third-party provision record created for every cross-border data transfer.
5. All 8 jurisdictions have passing control mapping tests.

---

## Stage 7: Vertical Tracks (Phases 31–32)

Goal: Dedicated compliance tracks for insurance and legal verticals — the two sectors with
zero tolerance for non-compliance.

---

### Phase 31: Insurance Compliance Track

**Goal**: AnonReq/Vanata as the compliance layer for insurance carriers, reinsurers, and brokers.

**Depends on**: Phase 28 (EU), Phase 29 (Middle East), Phase 30 (Asia) — as applicable per market

**Regulatory Coverage**:
- US: NAIC Insurance Data Security Model Law, state-level privacy laws (CCPA, NY SHIELD, etc.)
- EU: Solvency II data governance requirements, EIOPA guidelines on AI in insurance
- Lloyd's of London: data handling and market data standards
- Reinsurance: cross-border data transfer controls for treaty and facultative reinsurance
- Actuarial data: protection of mortality tables, pricing models, and underwriting data

**Deliverables**:
- Insurance-specific PII entity types: policy numbers, claim IDs, actuarial data markers
- Underwriting data classification: block AI access to pricing models and mortality tables
- Claims data handling: PHI + PII combined detection for health/life claims
- NAIC Model Law control mapping and evidence collection
- Solvency II data governance evidence package
- Lloyd's market data standard compliance checks
- Reinsurance cross-border transfer enforcement

**Requirements**: `INS-01..08` (see REQUIREMENTS.md)

**Success Criteria**:
1. Policy number and claim ID detected and anonymized across all supported formats.
2. Actuarial data classification blocks AI access to pricing model data.
3. NAIC Model Law evidence package generated and exportable.
4. Solvency II data governance report generated per entity.
5. Lloyd's market data standard compliance check passes.

---

### Phase 32: Legal & Law Firm Compliance Track

**Goal**: AnonReq/Vanata as the compliance layer for law firms, in-house legal teams, and legal tech platforms.

**Depends on**: Phase 28 (EU), Phase 29 (Middle East), Phase 30 (Asia) — as applicable per jurisdiction

**Regulatory Coverage**:
- Legal professional privilege: attorney-client privilege, legal professional privilege (UK/EU)
- Bar association rules: ABA Model Rules, SRA (UK), CCBE (EU), local bar rules
- Court data: protection of sealed documents, confidential filings, witness data
- Matter isolation: strict data separation between client matters
- eDiscovery: legal hold, preservation, and production workflows

**Deliverables**:
- Legal privilege classification: detect and protect privileged communications
- Matter-level data isolation: tenant-within-tenant model for client matters
- Attorney-client privilege marker: flag and block AI processing of privileged content
- Bar association rule compliance checks per jurisdiction
- Court document protection: detect and block AI processing of sealed/confidential filings
- eDiscovery integration: legal hold, preservation notice, and production workflow
- Legal entity detection: case numbers, docket IDs, matter references, court names

**Requirements**: `LEGAL-01..08` (see REQUIREMENTS.md)

**Success Criteria**:
1. Privileged communication detected and blocked from AI processing with `PRIVILEGE_BLOCK` audit event.
2. Matter-level isolation: data from Matter A never appears in Matter B context.
3. Bar association rule compliance check passes for ABA, SRA, and CCBE.
4. Legal hold workflow suspends deletion of all records for held matter.
5. eDiscovery production package generated with full chain of custody.

---

## V5 Phase Summary

| Stage | Phase | Name | Status |
|---|---|---|---|
| 4 | 22 | Appliance Packaging & Distribution | Not started |
| 4 | 23 | Transparent Proxy & Network Appliance Mode | Not started |
| 4 | 24 | Marketplace Listings & IaC Modules | Not started |
| 5 | 25 | AWS Native Integration | Not started |
| 5 | 26 | GCP & Azure Native Integration | Not started |
| 5 | 27 | NodeShift & GPU Infrastructure Integration | Not started |
| 6 | 28 | Vanata — EU Compliance Module | Not started |
| 6 | 29 | Vanata — Middle East Compliance Module | Not started |
| 6 | 30 | Vanata — Asia Compliance Module | Not started |
| 7 | 31 | Vanata — Insurance Compliance Track | Not started |
| 7 | 32 | Vanata — Legal & Law Firm Compliance Track | Not started |

---

## Dependencies

```
Phase 22 (Packaging)
  └── Phase 23 (Transparent Proxy)
        └── Phase 24 (Marketplace + IaC)
              ├── Phase 25 (AWS)
              ├── Phase 26 (GCP + Azure)
              └── Phase 27 (NodeShift)

Phase 16 + Phase 14
  └── Phase 28 (EU Vanata)
        ├── Phase 29 (Middle East Vanata)
        ├── Phase 30 (Asia Vanata)
        └── Phase 31 (Insurance) ← also needs 29, 30
              Phase 32 (Legal) ← also needs 28, 29, 30
```
