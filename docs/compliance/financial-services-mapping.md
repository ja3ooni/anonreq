# Financial Services Compliance Mapping

**Last updated:** 2026-07-04  
**Phase:** 15 — Financial Services Compliance  
**Purpose:** Map AnonReq features to 9 financial regulatory frameworks for compliance reporting and audit evidence  

## Frameworks Covered

| # | Framework | Jurisdiction | Effective |
|---|-----------|-------------|-----------|
| 1 | DORA — Digital Operational Resilience Act | EU | Jan 2025 |
| 2 | NIS2 — Network and Information Security Directive | EU | Oct 2024 |
| 3 | GDPR — General Data Protection Regulation | EU/EEA | May 2018 |
| 4 | ISO/IEC 27001 | International | Latest version |
| 5 | ISO/IEC 42001 | International | Latest version |
| 6 | EBA — European Banking Authority Guidelines | EU | Ongoing |
| 7 | FCA — Financial Conduct Authority Handbook | UK | Ongoing |
| 8 | SEC — Securities and Exchange Commission Rules | US | Ongoing |
| 9 | FINRA — Financial Industry Regulatory Authority | US | Ongoing |

---

## DORA (Digital Operational Resilience Act)

- **Regulation:** EU 2022/2554, effective January 2025
- **Scope:** ICT risk management, incident reporting, digital operational resilience testing, third-party risk
- **Covered by:** Incident escalation (15-03), provider inventory (15-02), SLO monitoring (Phase 11)

### Mapped Requirements

| DORA Article | AnonReq Feature | Evidence Source |
|-------------|-----------------|----------------|
| Art 11 | ICT incident management | IncidentManager, auto-escalation via `escalate_if_needed()` |
| Art 13 | ICT risk management framework | Governance lifecycle, risk assessment endpoints |
| Art 28 | Third-party risk (ICT TPP) | ProviderInventory, concentration risk flagging |
| Art 30 | Register of information | Provider inventory listing, model inventory |
| Art 5(iii) | ICT systems and tools | Detection pipeline, fail-secure architecture |

### Compliance Evidence

- Incident records with criticality-based escalation (CRITICAL → auto-notify)
- Provider inventory with DORA ICT critical designation
- Concentration risk flagging with annual review cycle
- SLO breach auto-escalation

---

## NIS2 (Network and Information Security Directive)

- **Regulation:** EU 2022/2555, effective October 2024
- **Scope:** Cybersecurity risk-management measures, incident reporting, supply chain security
- **Covered by:** Incident escalation (15-03), security controls (Phases 10, 13)

### Mapped Requirements

| NIS2 Article | AnonReq Feature | Evidence Source |
|-------------|-----------------|----------------|
| Art 20 | Cybersecurity risk-management measures | Governance lifecycle, risk assessments |
| Art 21 | Incident notification | IncidentManager, escalation audit events |
| Art 22 | Supply chain security | Provider inventory, concentration risk |
| Art 23 | Register of information | Model inventory, provider records |
| Art 24 | Security controls | Firewall engine, DLP detection, prompt injection protection |

### Compliance Evidence

- Incident records with severity and criticality classification
- Risk assessment records with dimensions and treatment plans
- Provider inventory with supply chain visibility
- Governance records with review cycles
- Security event logs from firewall and DLP modules

---

## GDPR (General Data Protection Regulation)

- **Regulation:** EU 2016/679, effective May 2018
- **Scope:** Personal data protection, data subject rights, data protection by design and default
- **Covered by:** Core AnonReq pipeline (Phases 1-7), governance (Phase 14), compliance presets (Phase 4)

### Mapped Requirements

| GDPR Article | AnonReq Feature | Evidence Source |
|-------------|-----------------|----------------|
| Art 5(1)(c) | Data minimisation | Anonymization pipeline, entity detection and tokenization |
| Art 5(1)(e) | Storage limitation | Ephemeral cache with TTL (60-3600s), DEL post-response |
| Art 5(2) | Accountability | Structured audit logging, governance records |
| Art 13 | Transparency | Compliance presets, governance transparency data |
| Art 15 | Right of access | Governance records, incident history |
| Art 32 | Security of processing | Fail-secure architecture, admin auth, RBAC |
| Art 33 | Personal data breach notification | IncidentManager, notification service |
| Art 35 | Data protection impact assessment | Governance risk assessment workflow |

### Compliance Evidence

- Audit log entries (metadata-only, no raw PII)
- Cache manager configuration (persistence disabled, TTL-based eviction)
- Governance records with officer assignments
- Risk assessment records
- Incident records for data breach scenarios
- Compliance preset configurations per jurisdiction

---

## ISO/IEC 27001 (Information Security Management)

- **Standard:** ISO/IEC 27001:2022
- **Scope:** Information security management system (ISMS)
- **Covered by:** Governance lifecycle (Phase 14), security controls (Phases 10, 13)

### Mapped Requirements

| ISO 27001 Clause | AnonReq Feature | Evidence Source |
|-----------------|-----------------|----------------|
| 6.1 | Risk assessment and treatment | Risk assessment records, governance risk workflow |
| 7.5 | Documented information | Governance records, change history |
| 8.1 | Operational planning and control | Pipeline configuration, policy engine |
| 8.2 | Information security risk assessment | Risk dimension scoring (privacy, security, bias, etc.) |
| 9.1 | Monitoring, measurement, analysis | Prometheus metrics, SLO monitoring |
| 9.2 | Internal audit | Audit logger, governance review cycles |
| Annex A 5.1 | Policies for information security | Governance policies, compliance presets |
| Annex A 5.15 | Access control | Admin API key auth, RBAC roles |
| Annex A 5.33 | Protection of records | SEC 17a-4 WORM archive, audit logging |
| Annex A 8.8 | Management of technical vulnerabilities | Security acceptance gates, review cycles |
| Annex A 8.12 | Data leakage prevention | DLP engine, exfiltration detection |
| Annex A 8.16 | Monitoring activities | Prometheus metrics, audit events |

### Compliance Evidence

- Governance records with active review cycles
- Risk assessment dimensions and treatment plans
- Security event metrics and monitoring data
- Access control enforcement (admin auth, RBAC)
- Audit trail with event history
- DLP detection events and firewall logs
- Incident management records

---

## ISO/IEC 42001 (Artificial Intelligence Management System)

- **Standard:** ISO/IEC 42001:2023
- **Scope:** AI management system (AIMS)
- **Covered by:** Model governance (Phase 14), fairness evaluation (Phase 16)

### Mapped Requirements

| ISO 42001 Clause | AnonReq Feature | Evidence Source |
|-----------------|-----------------|----------------|
| 6.1 | AI risk assessment | Model risk classification (SR 11-7), risk dimensions |
| 6.2 | AI system objectives | Model inventory, lifecycle stages |
| 7.4 | AI system documentation | Model documentation, versioning |
| 8.1 | Operational planning and control | Model approval gating, ForwardingGuard |
| 8.3 | AI system change management | Governance change history, review cycles |
| 9.1 | AI system monitoring | Fairness evaluation, SLO monitoring |
| 9.2 | AI system validation | Model validation status, review cycles |
| 10.1 | AI system incident management | IncidentManager for AI-related incidents |
| Annex A | AI-specific controls | Bias/fairness monitoring, transparency records |

### Compliance Evidence

- Model inventory with risk classification (LOW, MODERATE, HIGH)
- Model lifecycle stages (DESIGN → REVIEW → APPROVED → PRODUCTION → RETIRED)
- Approval gating via ForwardingGuard
- Fairness evaluation datasets and results
- Review cycle tracking with next_review_date
- Model documentation URLs and version history

---

## EBA (European Banking Authority) Guidelines

- **Regulation:** EBA/GL/2019/04, EBA guidelines on outsourcing arrangements
- **Scope:** Outsourcing to cloud/service providers, ICT and third-party risk management
- **Covered by:** Provider inventory (15-02), model inventory (15-02)

### Mapped Requirements

| EBA Guideline | AnonReq Feature | Evidence Source |
|--------------|-----------------|----------------|
| GL 28 | Risk assessment before outsourcing | Model risk classification, provider lifecycle |
| GL 30 | Outsourcing register | Provider inventory records |
| GL 32 | Review of outsourcing arrangements | Provider review cycles, concentration risk |
| GL 36 | Business continuity | DORA escalation, incident management |
| GL 38 | Access and audit rights | Governance records, audit logging |
| GL 42 | Sub-outsourcing | Provider inventory hierarchy |

### Compliance Evidence

- Provider inventory with lifecycle stages
- Model inventory with risk classification
- Provider concentration risk flagging
- Incident records for business continuity events
- Governance records with access rights documentation
- Provider review cycle tracking

---

## FCA (Financial Conduct Authority) Handbook

- **Regulation:** FCA Handbook — SYSC, SUP, MAR, DISP modules
- **Scope:** Systems and controls, outsourcing, market conduct, disputes
- **Covered by:** AML/Financial crime (15-03), incident management (15-03)

### Mapped Requirements

| FCA Module | AnonReq Feature | Evidence Source |
|-----------|-----------------|----------------|
| SYSC 3 | Systems and controls | Governance records, policy enforcement |
| SYSC 8 | Outsourcing | Provider inventory, suspension capability |
| SYSC 13 | Operational risk | Incident records, risk assessments |
| SYSC 14 | Compliance function | Governance officer assignment |
| SYSC 15 | Risk management | Risk assessment workflow |
| MAR 1 | Market conduct | MNPI detection, audit logging |
| DISP 1 | Complaints handling | Incident records, resolution tracking |

### Compliance Evidence

- Governance records with compliance officer assignments
- Provider inventory with suspension/unsuspension audit trail
- Incident records with resolution tracking
- Risk assessments with treatment plans
- AML webhook events and configuration
- MNPI detection events (audit metadata only)

---

## SEC (Securities and Exchange Commission) Rules

- **Regulation:** SEC 17a-4 (record retention), SEC 10b5-1 (insider trading), SEC Regulation SCI
- **Scope:** Record retention, insider trading prevention, systems compliance
- **Covered by:** MNPI protection (15-01), WORM archiving (15-01), incident management (15-03)

### Mapped Requirements

| SEC Rule | AnonReq Feature | Evidence Source |
|---------|-----------------|----------------|
| 17a-4 | Record retention | MinIO WORM bucket, audit events (immutable) |
| 10b5-1 | Insider trading safeguards | MNPI detection (ticker, deal, restricted name) |
| Reg SCI | Systems compliance | Incident escalation, SLO monitoring |
| 17a-3 | Record creation | Audit logger, detection events |
| 21(a) | Production of records | Compliance report generation |

### Compliance Evidence

- MNPI detection events with SHA-256 hashed values (not raw)
- Audit event chain with hash-linked immutability
- Incident records for systems-compliance events
- WORM archive configuration and evidence
- Compliance reports per framework

---

## FINRA (Financial Industry Regulatory Authority)

- **Regulation:** FINRA Rules 3110 (supervision), 3120 (AML), 3310 (AML program), 8210 (records)
- **Scope:** Supervision, anti-money laundering, recordkeeping
- **Covered by:** AML webhook (15-03), surveillance data (15-03), incident management (15-03)

### Mapped Requirements

| FINRA Rule | AnonReq Feature | Evidence Source |
|-----------|-----------------|----------------|
| 3110 | Supervision system | Governance oversight, review cycles |
| 3120 | AML compliance program | AML webhook, financial crime detection |
| 3210 | Accounts at other firms | Provider inventory, vendor management |
| 3310 | Anti-money laundering | AML webhook configuration, threshold enforcement |
| 8210 | Record production | Compliance report, audit event export |
| 4530 | Reporting requirements | Incident records, regulatory notifications |

### Compliance Evidence

- AML webhook configuration per tenant
- AML alert payloads (metadata only) with HMAC signatures
- Financial crime detection with context-word boosting
- Provider inventory for vendor oversight
- Incident records with resolution details
- Governance supervision framework

---

## Cross-Cutting Features

| Feature | Frameworks |
|---------|-----------|
| Fail-secure architecture | DORA, NIS2, ISO 27001, SEC |
| Metadata-only audit logging | GDPR, ISO 27001, SEC, FINRA |
| Ephemeral cache (no persistence) | GDPR (Art 5(1)(e)) |
| RBAC and admin authentication | ISO 27001, SOX |
| Incident auto-escalation | DORA, NIS2, SEC |
| Provider inventory and suspension | DORA, EBA, FCA |
| Model inventory and risk classification | ISO 42001, EBA, SR 11-7 |
| Compliance presets per jurisdiction | GDPR, LGPD, PDPA, POPIA |
| Prometheus metrics and SLO monitoring | DORA, ISO 27001 |
| Governance lifecycle and review cycles | ISO 27001/42001, NIS2 |
| Risk assessment framework | ISO 27001/42001, EBA |
| Fairness and bias evaluation | ISO 42001 |

---

## Evidence Collection Process

AnonReq collects compliance evidence through:

1. **Structured audit logging** — All significant events produce audit events with metadata (no raw values)
2. **Governance records** — Per-tenant governance officers, review cycles, risk assessments
3. **Incident records** — DORA ICT incidents with criticality-based escalation
4. **Provider inventory** — Third-party providers with DORA ICT designation, concentration risk
5. **Model inventory** — SR 11-7 model risk classification, lifecycle stages, approval gating
6. **Prometheus metrics** — SLO metrics, fail-secure events, request counts
7. **Dynamic compliance reports** — Framework-specific reports generated from current data via `GET /v1/admin/compliance/report`

## Gap Analysis

| Framework | Current Coverage | Gaps |
|-----------|-----------------|------|
| DORA | Incident escalation, provider inventory, SLO | Formal ICT risk management documentation |
| NIS2 | Incident management, security controls | Supply chain audit trail |
| GDPR | Core anonymization, ephemeral cache, audit | Data subject request workflow |
| ISO 27001 | Governance, security controls, incident | Formal ISMS documentation, BCP |
| ISO 42001 | Model inventory, fairness | AI ethics board documentation |
| EBA | Provider inventory, model risk | Formal outsourcing register |
| FCA | AML webhook, MNPI | Market abuse detection workflow |
| SEC | MNPI, WORM archive | Formal 17a-4 retention schedule |
| FINRA | AML webhook, supervision | Detailed supervisory procedures |

---

*Document maintained as part of Phase 15 (Financial Services Compliance).  
Last updated: 2026-07-04*
