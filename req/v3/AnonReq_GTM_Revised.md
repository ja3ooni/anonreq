# AnonReq Go To Market Strategy

**Product:** AI Security Gateway for Regulated Enterprises
**Version:** 2.0
**Date:** June 2026
**Classification:** Confidential — Internal Use

---

## Table of Contents

1. Executive Summary
2. Market Analysis
3. Target Customer Segments
4. Personas & Buyer Journey
5. Product Tiers & Packaging
6. Channel Strategy
7. Marketing & Positioning
8. Sales Process
9. Pilot & Onboarding
10. Competitive Positioning
11. Revenue Model
12. GTM Timeline
13. Success Metrics

---

## 1. Executive Summary

### Product Overview

AnonReq is a self-hosted, proprietary anonymization gateway that sits between enterprise applications and external LLM APIs. It intercepts outbound requests, detects and replaces PII/PHI/MNPI with context-preserving tokens (`[TYPE_N]`), forwards sanitized data to OpenAI/Anthropic/Gemini/Ollama, and restores original values in responses — all within the customer's secure perimeter. Raw sensitive data never crosses the network boundary.

Core engineering decisions: fail-secure architecture (any error blocks forwarding), ephemeral Valkey cache (no persistence), property-based correctness verification (Hypothesis), multi-locale detection (8 locales), and OpenAI-compatible wire protocol with provider adapters.

Trust is established through verifiable security posture — SOC 2 Type II certification, independent penetration testing, third-party audit reports, and source code escrow for enterprise customers — rather than open-source publication.

### Target Market

Regulated enterprises across financial services, healthcare, insurance, government, law firms, and accounting, operating under EU (GDPR, DORA, NIS2, EU AI Act), North America (HIPAA, SEC, FINRA), APAC (PDPA, Privacy Act Australia), MENA (PDPL, UAE data protection), and LATAM (LGPD). Secondary market: mid-market organizations with compliance requirements and large enterprise AI platform teams embedding AnonReq as infrastructure.

### Commercial Model

Three-tier proprietary model:

- **Starter** ($1,500/tenant/month) — single-tenant deployment, core anonymization pipeline, standard support
- **Enterprise** ($4,000-$15,000/tenant/month) — SSO/RBAC, policy engine, compliance reports, SLA, multi-tenant
- **Appliance** ($75,000-$250,000/year) — transparent proxy, AI firewall, voice/meeting protection, air-gapped

Professional services ($250-$500/hour) for implementation, custom recognizers, and compliance mapping. Source code escrow available to all Enterprise and Appliance customers as a standard contractual option.

### Go-To-Market Motion

Direct enterprise sales as primary channel. Outbound prospecting to named accounts in financial services, healthcare, and government. Inbound driven by compliance-oriented content marketing, conference presence, and analyst relations. Channel partnerships with MSPs and regional system integrators serving regulated industries. Cloud marketplace listings on AWS and Azure.

Trust is built through procurement-grade evidence packages: SOC 2 Type II, independent pen test reports, signed release artifacts, SBOM per release, architectural review sessions, and reference customer introductions.

### Key Metrics (Year 1 Targets)

- 20 paid pilots (12 enterprise, 8 starter)
- 10 pilot-to-paid conversions
- $720,000 ARR
- 4 channel partners signed
- SOC 2 Type II audit completed
- 3 referenceable enterprise customers

---

## 2. Market Analysis

### 2.1 Market Size

**Total Addressable Market (TAM):** AI Security Gateways — $4.2B by 2028 (CAGR 38.5%)
- Source: Gartner "Market Guide for AI Trust, Risk, and Security Management" (2025)
- Driven by enterprise genAI adoption hitting 85% of large organizations by 2027

**Serviceable Addressable Market (SAM):** $1.8B
- Self-hosted AI security infrastructure for regulated industries
- Excludes SaaS-only deployments where data residency is a procurement blocker

**Serviceable Obtainable Market (SOM):** $54M (Year 1-2), $216M (Year 3-4)
- Based on 0.6% initial capture of the regulated enterprise segment
- Growth driven by enforcement of EU AI Act, DORA, NIS2, and SEC cybersecurity rules
- Accelerated by increasing CISO awareness of shadow AI as a board-level risk

### 2.2 Key Market Trends

**1. Regulatory enforcement is creating genuine urgency.** The EU AI Act became enforceable in August 2026 for high-risk AI systems. DORA took effect in January 2025 for EU financial entities. NIS2 expanded incident reporting obligations across 18 critical sectors. Regulators are issuing guidance specifically naming LLM data flows as in-scope for data minimization, third-party risk, and operational resilience requirements. This is converting AI security from a "nice to have" into a procurement checkbox.

**2. Shadow AI is a board-level risk.** Gartner estimates 60% of enterprise AI usage is unsanctioned. Legal, HR, and finance teams are using consumer-grade ChatGPT and Copilot for work tasks involving client data, trade secrets, and regulated personal information. Following several high-profile incidents (Samsung source code leakage, healthcare AI data exposures), boards are mandating documented controls before AI can be used operationally.

**3. Multi-provider AI strategy is standard.** Enterprises have stopped betting on a single AI provider. Most organizations in 2026 operate with two to four LLM providers across different use cases (OpenAI for customer-facing, Anthropic for legal, open models for internal tools). Per-provider security configuration is unmanageable. A provider-agnostic gateway layer has become the natural architectural answer.

**4. Data residency requirements are tightening.** EU, UAE, Saudi Arabia, and India have enacted or proposed data localization requirements that restrict personal data from leaving jurisdictional boundaries. SaaS-based AI security proxies that process data on third-party infrastructure conflict with these requirements. Self-hosted infrastructure is the only viable path for organizations operating in these jurisdictions.

**5. The CIO/CISO relationship has shifted.** Post-pandemic AI adoption created tension between CIOs pushing AI velocity and CISOs managing risk. That tension is resolving in 2026: CISOs now have board mandate to govern AI tooling, and CIOs are accepting that AI adoption must come with documented controls. This alignment is the precondition for enterprise AI security purchasing decisions.

### 2.3 Competitive Landscape

| Competitor | Category | Strengths | Weaknesses | AnonReq Advantage |
|------------|----------|-----------|------------|-------------------|
| NodeShift | Sovereign AI Cloud | Turnkey managed, data sovereignty | SaaS model — data still leaves perimeter to their infra | Truly self-hosted, customer owns infrastructure |
| AI Security Gateway (AISG) | SaaS proxy | Easy setup, broad support | Customer data processed on their infrastructure; adds a third party | Zero third-party data processing |
| AWS Bedrock Guardrails | Cloud native | Tight AWS integration, managed | AWS-only, no multi-cloud, no tokenization/restoration | Provider-agnostic, bidirectional tokenization |
| Azure AI Content Safety | Cloud native | Azure integration | Azure-only, no anonymization, content-filtering only | Multi-provider, full anonymize-and-restore pipeline |
| In-house builds | Custom | Full control | 6-12 month build cycle, no streaming, no compliance presets | Production-ready in 30 minutes, 21-phase roadmap |
| Presidio (library) | Library | Flexible, open | Not a gateway; no streaming, no restoration, no audit trail | Full pipeline: detect, tokenize, stream, restore, audit |

### 2.4 AnonReq Differentiation

**1. Bidirectional tokenization.** Most competitors block or strip data. AnonReq replaces PII with context-preserving `[TYPE_N]` tokens, forwards the sanitized prompt, and restores original values in the response. The LLM can still reason about structure ("the customer at [EMAIL_1] sent a complaint") while raw data never leaves the perimeter.

**2. Fail-secure by design, independently verifiable.** Any error in any pipeline stage — detection failure, cache outage, timeout — blocks forwarding and returns HTTP 5xx. This is not configurable. The guarantee is documented in the architecture, verified by property-based tests (Hypothesis), and demonstrated to customers during the pilot. Independent penetration testers can validate fail-secure behavior directly.

**3. Streaming first.** SSE restoration with the Tail_Buffer FSM handles tokens split across chunk boundaries. Not a retrofit; streaming is a first-class pipeline path. Critical for interactive applications where buffering responses before delivery is user-experience-breaking.

**4. Multi-locale, multi-jurisdiction, production-ready.** 8 locales including Arabic (ar-AE for MENA), Portuguese/Brazilian (pt-BR), German (de-DE), French (fr-FR), and others. 6 compliance presets (GDPR, LGPD, PDPA, POPIA, PIPEDA, Privacy Act AU). Checksum validation for national IDs (Steuer-ID, BSN, CPF, NIR, Codice Fiscale). No other self-hosted gateway offers this coverage out of the box.

**5. Single wire protocol, any provider.** OpenAI-compatible API means existing SDK integrations require one configuration change (`base_url`). Zero application code changes. Provider adapters handle translation to Anthropic, Gemini, Ollama, and Azure OpenAI internally.

---

## 3. Target Customer Segments

### 3.1 Primary: Regulated Enterprises (1,000+ employees)

**Financial Services — highest priority**
- Banks, asset managers, hedge funds, insurers, fintech platforms
- Pain: MNPI exposure via trading desk AI use, DORA third-party ICT risk, Model Risk Management (SR 11-7), SEC/FINRA record-keeping, GDPR for EU entities
- Use cases: Trading research with LLMs, contract summarization, compliance document analysis, customer service chatbots
- Entry point: CISO or Chief Compliance Officer following an AI governance audit

**Healthcare and Pharma**
- Hospital systems, health insurers, pharmaceutical companies, medtech
- Pain: HIPAA, patient data in LLM prompts, clinical note processing, AI-assisted diagnosis liability
- Use cases: Clinical decision support, medical record summarization, prior authorization automation
- Entry point: CISO or Chief Privacy Officer following HIPAA risk assessment

**Insurance**
- Underwriting platforms, claims processing, customer service operations
- Pain: PII in claims documents, cross-border data transfer restrictions, actuarial model governance
- Use cases: Claims analysis, policy document summarization, fraud detection with LLM reasoning
- Entry point: CIO or Head of Digital following an AI adoption initiative

**Government and Public Sector**
- EU member state agencies, federal departments, defense-adjacent contractors
- Pain: Data sovereignty mandates, classified information handling, public procurement requirements for self-hosted
- Use cases: Document classification, citizen communication, policy analysis
- Entry point: IT Procurement or Chief Digital Officer

**Legal and Accounting**
- Magic Circle and Big Four firms, corporate legal departments, national accounting practices
- Pain: Attorney-client privilege, confidential M&A data, professional ethics obligations, eDiscovery risk
- Use cases: Contract analysis, due diligence, financial audit document review
- Entry point: General Counsel, CIO, or Risk Partner

**Geographic priorities:**
1. EU/EEA (GDPR, EU AI Act, DORA — regulatory pressure is highest and most enforced)
2. Germany, Netherlands, France (largest regulated enterprise base in EU)
3. United Kingdom (UK GDPR, FCA — large financial services market)
4. United Arab Emirates (PDPL, DIFC, ADGM — rapid AI adoption, data localization requirements)
5. Saudi Arabia (PDPL, Vision 2030 AI initiative, SDAIA oversight)
6. United States (HIPAA, SEC, FINRA, state privacy laws)
7. Brazil (LGPD — growing compliance market, Portuguese locale ready)
8. Singapore and Australia (PDPA, Privacy Act — APAC Year 2 expansion)
9. South Africa (POPIA — Year 2)
10. Canada (PIPEDA — Year 2)

### 3.2 Secondary: Mid-Market with Compliance Requirements (100-1,000 employees)

- Regional banks and credit unions
- Boutique law firms and accounting practices
- HR tech and payroll platforms processing employee PII
- Enterprise SaaS companies whose customers are in regulated industries
- Healthcare technology vendors subject to HIPAA Business Associate Agreements

**Approach:** Starter tier pricing, self-service deployment, shorter sales cycle (30-45 days), lighter professional services. Many mid-market organizations can deploy on Starter and never need Enterprise features, making them high-margin, low-touch accounts.

### 3.3 Tertiary: Platform Integrators and OEM Partners

Enterprise software vendors building LLM features into their products who need to satisfy regulated customers' data governance requirements. AnonReq is embedded as the AI security layer and white-labeled or referenced in their compliance documentation.

Examples: ERP vendors adding AI document processing, vertical SaaS companies (legal tech, healthtech, fintech) adding AI assistants, system integrators building AI platforms for government.

**Commercial model:** OEM licensing agreement, flat annual fee based on estimated call volume, vendor takes margin on resale. Target: 3 OEM agreements by Year 2.

---

## 4. Personas & Buyer Journey

### 4.1 Core Personas

#### Technical Buyer: CISO / VP Security

| Attribute | Detail |
|-----------|--------|
| Title | Chief Information Security Officer, VP Information Security, Security Architect |
| Primary concern | Data exfiltration via AI channels, regulatory liability, inability to prove controls to auditors |
| Technical depth | Deep — evaluates architecture diagrams, reviews threat models, asks about fail-secure edge cases |
| Key questions | Where does my data go at each stage? What happens if Presidio fails? Can I see the audit trail? How do you prove no PII is logged? Is source code available under escrow? |
| Information sources | Gartner, CISO peer networks, RSA/Black Hat, security-focused technical blogs, vendor SBOM |
| Buying criteria | SOC 2 Type II, pen test report, architecture review, fail-secure proof, SBOM, source code escrow |
| Objections | "We can build this with Presidio"; "I need to audit the code myself"; "This adds another third party to our supply chain" |
| Objection responses | "We offer source code escrow as standard"; "Property-based test reports and pen test results replace line-by-line audit for most procurement needs"; "AnonReq runs entirely on your infrastructure — we are not in your data path" |

#### Economic Buyer: CIO / CTO

| Attribute | Detail |
|-----------|--------|
| Title | Chief Information Officer, Chief Technology Officer, VP Engineering |
| Primary concern | AI adoption velocity, developer productivity, vendor lock-in, total cost of build vs. buy |
| Technical depth | High-level technical, budget authority |
| Key questions | How fast to deploy? What is the latency impact? Does it work with our existing stack? What is TCO vs. building in-house? |
| Information sources | Analyst reports, peer CIO networks, ROI calculators, case studies with named customers |
| Buying criteria | Time-to-value, developer experience, provider flexibility, pricing predictability, reference customers |
| Objections | "Our team can build this"; "Another proxy adds latency and failure points"; "We already use Bedrock Guardrails" |
| Objection responses | "6-12 months of engineering time vs. 30-minute deployment"; "P95 overhead is sub-100ms on prompts under 1,000 words"; "Bedrock ties you to AWS — AnonReq works across any provider and any cloud" |

#### Compliance Influencer: DPO / Compliance Director

| Attribute | Detail |
|-----------|--------|
| Title | Data Protection Officer, Head of Compliance, Regulatory Affairs Director |
| Primary concern | GDPR Article 28 processor obligations, audit evidence, data minimization, cross-border transfer controls |
| Technical depth | Moderate — understands data flows, prefers auditable, documented controls |
| Key questions | Does this satisfy GDPR Art. 28? Can we get a compliance evidence package? Is detection aligned with our DPIA? What data does AnonReq process about our users? |
| Information sources | IAPP, national DPA guidance, peer DPO networks, legal counsel opinion |
| Buying criteria | Compliance preset mapping, metadata-only audit trail, no-PII-in-logs proof, record retention, legal hold, evidence package export |
| Objections | "Our DLP already handles this"; "We need everything on-prem to pass audit" |
| Objection responses | "Traditional DLP is not designed for LLM API traffic or streaming responses"; "AnonReq is entirely on-prem — nothing is sent to us" |

#### User: Platform Engineer / ML Engineer

| Attribute | Detail |
|-----------|--------|
| Title | Platform Engineer, ML Engineer, Senior Backend Engineer, DevOps Engineer |
| Primary concern | Latency, reliability, integration effort, documentation quality, observability |
| Key questions | How do I change my OpenAI client? Does streaming work? What metrics are exposed? How do I configure custom recognizers for our internal identifiers? |
| Information sources | Technical documentation, GitHub (even for proprietary products, public docs matter), engineering blogs |
| Buying criteria | Clean API with SDK examples, fast quickstart, Docker Compose, Prometheus metrics, hot-reload config, low overhead |
| Objections | "This adds latency"; "I can just use Presidio directly"; "How do I debug when detection goes wrong?" |
| Objection responses | "Sub-100ms P95 overhead"; "Presidio alone gives you detection — not streaming, restoration, compliance presets, or audit"; "Structured audit logs and Prometheus metrics give you full pipeline observability" |

### 4.2 Buyer Journey

**Stage 1: Awareness**
- Trigger: Shadow AI audit finds unsanctioned LLM usage; regulatory requirement for AI governance; AI incident at peer organization; analyst report names AI data leakage as a top risk
- AnonReq touchpoints: Conference presence (RSA, CISO summits), analyst briefings, compliance-focused content (DORA/GDPR guides), direct outbound to CISO/Compliance Director at named accounts

**Stage 2: Initial Evaluation**
- Platform engineer or security architect receives internal mandate to evaluate AI security gateway options
- They compare AnonReq vs. building with Presidio vs. cloud-native options vs. SaaS proxies
- AnonReq touchpoints: Product website with architecture diagram, latency benchmarks, compliance preset documentation, SDK quickstart, technical deep-dive content (blog posts, recorded webinars)

**Stage 3: Technical Validation (Pilot)**
- Engineering team deploys Docker Compose and runs the pilot checklist
- Security architect reviews architecture, threat model, and fail-secure behavior
- DPO reviews compliance preset mapping and audit log format
- AnonReq touchpoints: Dedicated Solutions Engineer during pilot, pilot checklist, architecture walkthrough session, SOC 2 report and pen test summary shared under NDA

**Stage 4: Procurement**
- CISO presents recommendation with evidence package
- Procurement team reviews DPA, commercial agreement, escrow terms
- Legal reviews proprietary software license
- AnonReq touchpoints: Security questionnaire response package, DPA template, source code escrow agreement, reference customer introduction

**Stage 5: Deployment and Expansion**
- Platform engineering team deploys to production
- CSM tracks usage, monitors for expansion signals (additional tenants, business units, appliance tier interest)
- AnonReq touchpoints: Implementation engineer (40 hours), quarterly business reviews, compliance evidence package refresh

### 4.3 Decision-Making Unit (DMU)

| Role | Stage | Influence | Authority |
|------|-------|-----------|-----------|
| CISO | Evaluate, Procure | High (defines technical requirements) | Sign-off on security approval |
| CIO/CTO | Awareness, Procure | High (budget) | Budget approval |
| DPO/Compliance | Evaluate, Procure | Medium (defines compliance requirements) | Recommend to CISO |
| Platform Engineer | Evaluate, Deploy | Medium (technical feasibility) | Recommend to CIO/CISO |
| Legal | Procure | Low (contract terms, DPA) | Legal sign-off |
| Procurement | Procure | Low (vendor management) | PO issuance |

---

## 5. Product Tiers & Packaging

### 5.1 Starter Tier

**Target:** Mid-market organizations, single-tenant deployments, teams with capable engineering but lean compliance function

**Feature set:**
- Full anonymization gateway (Phases 1-7 of product roadmap)
- POST /v1/chat/completions with full SSE streaming support
- Hybrid detection engine (regex + NER, 8 locales including Arabic and Portuguese/Brazilian)
- Bidirectional tokenization and restoration
- Ephemeral Valkey cache (persistence disabled)
- Multi-provider support: OpenAI, Anthropic, Gemini, Ollama, Azure OpenAI
- Metadata-only audit logging to stdout
- Custom detection rules and exclusion lists with hot-reload
- Docker Compose deployment (30-minute target)
- Prometheus metrics and health endpoints
- Property-based test suite (deliverable: test results per release)
- Signed release artifacts (checksums, SBOM per release)
- Documentation: EN, DE, FR, ES, PT-BR, AR
- SDK examples: curl, Python, TypeScript, Go
- Email support, 48-hour response SLO
- Single tenant only

**Pricing:**
- $1,500/month ($18,000/year)
- Annual prepay: $15,000/year (17% discount)
- No per-seat, per-request, or per-provider fees

### 5.2 Enterprise Tier

**Target:** Regulated enterprises with 1,000+ employees, multi-tenant deployments, dedicated compliance and security teams

**Feature set (all Starter features plus):**
- SSO: OIDC, SAML 2.0, Azure AD, Okta integration
- RBAC: roles — viewer, operator, administrator, compliance, security
- mTLS between internal gateway components
- HashiCorp Vault, AWS Secrets Manager, Azure Key Vault integration
- Multi-tenant isolation (tenant-namespaced cache, audit, config)
- Per-tenant rate limiting: RPM, TPM, concurrent requests
- Per-tenant spend controls: daily and monthly budgets with HTTP 402 enforcement
- Multimodal anonymization: tool call arguments, JSON payloads, multipart content
- Data classification: 5-level sensitivity (Public through Highly Restricted), auto-classification from detected entity types
- AI Security Firewall: prompt injection detection, jailbreak pattern matching, output policy enforcement
- Config change audit trail: append-only, immutable, 7-year retention
- AI Governance Framework: ISO 42001 alignment, named governance owners, review cycles, risk assessments
- Compliance reporting: GDPR, DORA, NIS2, HIPAA, SEC, FINRA, SR 11-7 framework mapping
- Conformity assessment package export (EU AI Act)
- Fairness monitoring: bias assessment per locale, CI/CD gate (recall disparity ≤ 0.05)
- Financial services compliance: MNPI detection, Model Risk Management, financial crime controls, DORA resilience procedures
- Data lineage: immutable records with HMAC-SHA256 integrity
- Record retention with configurable policies and legal hold
- Business unit segregation (Chinese Wall enforcement via X-AnonReq-BU header)
- Executive governance reporting
- SBOM per release with OCI attestation and Cosign image signing
- Kubernetes Helm chart with horizontal pod autoscaling
- 99.9% uptime SLA
- Priority support: dedicated Slack channel + email, 4-hour response (8x5) or 1-hour response (24x7 add-on)
- Dedicated implementation engineer: 40 hours included
- Quarterly business review
- Source code escrow: standard contractual option (Norton Rose Fulbright escrow agreement template)
- Up to 25 tenants per deployment

**Pricing:**

| Model | Price | Best for |
|-------|-------|----------|
| Per-tenant/month (1-9 tenants) | $4,000/tenant/month | Banks, insurers with multiple BUs |
| Per-tenant/month (10-49 tenants) | $3,200/tenant/month | Large enterprises with subsidiaries |
| Per-tenant/month (50+ tenants) | $2,500/tenant/month | Platform providers, group-level deployments |
| Flat annual (up to 5 tenants) | $150,000/year | Single-org with multiple departments |
| Flat annual (up to 25 tenants) | $450,000/year | Large financial institution or group |

Multi-year commitment (2-year): 15% discount. Multi-year (3-year): 22% discount.
Non-profit/academic pricing: 40% discount on flat annual.

**Onboarding included:** 40-hour implementation engineer, compliance mapping workshop (4 hours), custom recognizer development (up to 3 domain-specific pattern bundles).

### 5.3 Appliance Tier

**Target:** Regulated enterprises requiring network-level AI governance, transparent proxy, voice/meeting protection, or air-gapped deployment

**Feature set (all Enterprise features plus):**
- Universal AI traffic gateway: transparent proxy mode with TLS interception using tenant-managed CA certificate
- Reverse proxy mode and virtual appliance deployment
- AI-aware DLP: 8 data loss categories with per-category enforcement actions (allow/anonymize/redact/quarantine/block)
- Voice and meeting AI protection: SIP/WebRTC interception, local STT pipeline, audio redaction (≤150ms P99 latency)
- Agent and tool call governance: MCP protocol inspection, per-tool permission policies, human approval queue
- Extended AI Security Firewall: data exfiltration detection, model manipulation detection, agent abuse detection, MITRE ATT&CK/ATLAS mapping
- AI network discovery: identifies AI API traffic to 8+ providers, shadow AI detection via network flow/DNS analysis
- AI CASB: classification of AI SaaS apps as sanctioned/tolerated/unsanctioned, per-app enforcement policies
- Secure RAG pipeline protection: retrieval injection point inspection, vector database connectors (Pinecone, Weaviate, Chroma, pgvector)
- SIEM integration: Splunk HEC, IBM QRadar syslog CEF, Microsoft Sentinel DCR API, Elastic Bulk API, Datadog Logs API
- Block-all-unintercepted-AI policy enforcement
- Physical or virtual appliance form factors
- Air-gapped deployment: no external telemetry, no license phone-home, local sovereign AI control plane routing via vLLM/Ollama
- Dedicated support engineer (named contact)
- 1-hour SLA (24x7)
- Quarterly on-site architecture review
- On-premise deployment engineering support (travel included for up to 2 on-site visits/year)
- Hardware Security Module (HSM) integration option

**Pricing:**

| SKU | Price/year | Includes |
|-----|------------|----------|
| Virtual Appliance | $75,000-$125,000 | All Enterprise + Appliance features, VM image, standard hardware sizing guide |
| Physical Appliance | $100,000-$200,000 | Pre-configured 2U hardware, all features, on-site installation, 3-year hardware warranty |
| Air-Gapped Appliance | $175,000-$300,000 | Physical appliance, no telemetry, local model routing, dedicated HSM integration, classified environment deployment guide |

Hardware specification (physical appliance): 2U rackmount, dual Xeon/EPYC, 128GB RAM, 2TB NVMe RAID, GPU (A10 or equivalent) for local STT and small-model inference, dual 25GbE network interfaces, bypass LAN pair, TPM 2.0.

### 5.4 Professional Services

| Service | Price | Description |
|---------|-------|-------------|
| Standard implementation | $25,000-$40,000 flat | Deployment, integration, policy configuration, compliance mapping, team training |
| Complex implementation | $40,000-$75,000 flat | As above plus multi-tenant setup, custom SSO integration, HA Kubernetes deployment |
| Custom recognizer development | $5,000-$15,000 per bundle | Domain-specific PII/MNPI patterns (e.g., internal account codes, deal names, fund identifiers) |
| Compliance mapping workshop | $12,000-$20,000 | Map AnonReq controls to DORA/NIS2/GDPR/SEC/HIPAA, produce evidence package |
| Security architecture review | $15,000-$30,000 | Threat model walkthrough, fail-secure validation, pen test facilitation |
| Training: operator | $3,500 per session | Platform engineering team — deployment, config, monitoring, incident response |
| Training: compliance | $3,500 per session | DPO/Compliance team — audit log interpretation, evidence package, preset configuration |
| Retainer | $6,000-$15,000/month | Ongoing support, quarterly reviews, compliance framework updates, custom recognizer maintenance |

### 5.5 Source Code Escrow

Source code escrow is offered as a standard contractual option to all Enterprise and Appliance customers at no additional charge. The escrow arrangement uses a recognized third-party escrow agent (e.g., Iron Mountain, NCC Group) and releases source code to the customer under defined conditions (vendor insolvency, product discontinuation, failure to maintain). This replaces the open-source audit mechanism with a commercially standard and legally enforceable alternative that regulated enterprise procurement teams are already familiar with.

Customers may conduct a supervised code review session (on-site or virtual, under NDA) as part of security due diligence at the Enterprise tier and above.

### 5.6 Pricing Principles

1. **No per-request, per-token, or per-provider fees.** Pricing is flat by tier and tenant count. Customers can process as many requests as their infrastructure supports without variable cost surprises.
2. **No feature degradation over time.** All features available at purchase remain available for the life of the subscription.
3. **Transparent pricing.** Pricing is published on the website for Starter tier. Enterprise and Appliance pricing is shared on first contact, not gated behind "contact us."
4. **Predictable multi-year commitments.** Annual and multi-year prepay options with published discount rates.
5. **Escrow is standard, not a premium add-on.** Source code escrow is included in Enterprise and Appliance contracts by default.

---

## 6. Channel Strategy

### 6.1 Direct Sales

**Sales team structure (Year 1):**
- 2 Enterprise Account Executives (named accounts, 1,000+ employee regulated enterprises)
- 1 SDR/BDR (outbound prospecting, inbound qualification)
- 1 Solutions Engineer (technical pre-sales, pilot support, architecture reviews)
- 1 Customer Success Manager (post-sales, adoption tracking, expansion identification)

**Territory split:**
- AE 1: EMEA — Germany, Netherlands, France, UK, UAE (primary coverage)
- AE 2: Americas — US East Coast financial services, US healthcare, Canada

**Named account targeting (Year 1 — illustrative, not exhaustive):**
- 15 financial services institutions (EU-based banks, asset managers, insurers)
- 8 healthcare organizations (US hospital systems, EU pharma)
- 8 insurance carriers (EU and US)
- 5 government agencies or defense contractors (EU)
- 4 MENA enterprises (UAE/KSA financial institutions, government digital agencies)

**Sales motion:**
- Outbound: SDR identifies and qualifies; AE runs discovery; SE supports technical evaluation; AE closes
- Inbound: SDR qualifies, routes to AE within 24 hours
- Channel-sourced: AE co-sells with partner, shares pipeline in CRM
- No self-serve enterprise (Starter is available self-serve; Enterprise and Appliance require sales engagement)

### 6.2 Channel Partners

**Managed Service Providers (MSPs):**
MSPs serving regulated industries (financial services IT, healthcare IT, government IT) resell and operate AnonReq as a managed service for their clients. MSP takes responsibility for deployment, monitoring, and first-line support.

- Revenue share: 20% referral fee for leads sourced; 30% resell margin for MSPs who own the customer relationship and support
- Enablement: Partner portal, deployment playbooks, co-branded pilot checklist, dedicated partner SE support during first 3 deployments
- Target: 3 MSP partners signed in Year 1 (1 EU financial services IT, 1 US healthcare IT, 1 MENA government IT)

**System Integrators (SIs):**
Large SIs (Accenture, Deloitte, PwC, Capgemini, NTT Data) implement AnonReq as part of broader AI governance and digital transformation engagements. SI adds professional services margin on top of AnonReq licensing.

- Revenue share: 15% referral fee for leads sourced and closed by SI; SI self-prices professional services
- Enablement: SI-specific technical training, co-developed compliance mapping templates, named technical contact at AnonReq
- Target: 2 SI partnerships signed in Year 2 (focus: DORA compliance practice at Big 4, EU AI Act advisory practice)

**Regional Distributors:**
- UAE/KSA: Partner with a UAE-based cybersecurity distributor with relationships in ADGM/DIFC financial community and government digital agencies. MENA distributor handles local compliance documentation (PDPL, UAE IA requirements) and Arabic-language sales collateral.
- Brazil: Partner with local cloud/SI firms for LGPD compliance market. Portuguese locale support is a natural entry point.
- Japan/Singapore: Year 2 expansion via local IT trading companies or cybersecurity distributors.

**Compliance Consultancies:**
Boutique GDPR, DORA, NIS2, HIPAA, and SEC compliance firms recommend AnonReq to clients as part of remediation and AI governance advisory engagements.

- Revenue share: 10% referral fee
- No resell — consultancy refers to AnonReq sales team, receives referral fee at close
- Target: 10 compliance consultancy referral relationships signed in Year 1

### 6.3 Cloud Marketplaces

**AWS Marketplace:**
- Enterprise tier listed as private offer (procurement via AWS, reduces procurement friction for AWS-committed customers)
- BYOL model for customers who negotiate directly then transact via Marketplace
- Appliance tier available as AMI for AWS-based deployments

**Azure Marketplace:**
- Enterprise tier as transactable SaaS offer
- Integration documentation for Azure AD SSO evaluation
- Azure OpenAI provider adapter highlighted as a key use case

**Both marketplaces by Month 8.** Marketplace listings reduce procurement friction for customers with committed cloud spend and no appetite for new vendor onboarding outside their marketplace relationships.

---

## 7. Marketing & Positioning

### 7.1 Core Positioning Statement

AnonReq is the AI security gateway for regulated enterprises that cannot afford to trust an AI provider with raw sensitive data. It sits inside your network, detects PII and regulated data before it leaves, replaces it with context-preserving tokens, and restores original values when the response comes back. Your LLM sees anonymized prompts. Your employees see real answers. Nothing raw crosses the boundary.

### 7.2 Messaging Framework

**Primary message (CISO audience):**
"Raw sensitive data never crosses your network boundary. Any failure in the pipeline blocks the request. This is not configurable. It is verifiable."

**Secondary message (CIO/CTO audience):**
"Change one line — your base_url. Zero application code changes, any LLM provider, 30-minute deployment."

**Tertiary message (DPO/Compliance audience):**
"GDPR Article 28, DORA, NIS2, EU AI Act, HIPAA — six compliance presets, a verifiable audit trail, and an evidence package you can hand to your auditor."

**Trust replacement message (for all audiences, replacing open-source auditability):**
"You don't have to take our word for it. SOC 2 Type II. Independent pen test report. SBOM per release. Signed artifacts. Source code escrow as a standard contract term. If you need a supervised code review, we will schedule it."

### 7.3 Key Narratives

**Narrative 1: "The only AI security guarantee you can verify"**
Proprietary software security claims are often unverifiable. AnonReq replaces public auditability with a verification package: SOC 2 Type II certification from a recognized auditor, annual third-party penetration test with published scope and findings summary, SBOM per release (CycloneDX format), Cosign-signed container images with OCI attestation, and source code escrow as a standard contractual term. Regulated enterprise procurement teams are more familiar with this evidence package than with GitHub repositories.

Visual asset: "How we prove it" diagram showing each verification mechanism and the question it answers.

**Narrative 2: "AI security built for DORA and the EU AI Act"**
For EU financial services, DORA requires documented ICT third-party risk management for every AI provider used. The EU AI Act requires risk management, human oversight, and transparency for high-risk AI system deployers. AnonReq ships a DORA conformity assessment package and an EU AI Act alignment mapping as standard enterprise deliverables. No other self-hosted AI gateway does this.

Content format: Regulatory mapping table, downloadable compliance brief, conference session at SIFMA/Risk.net/FT Live events.

**Narrative 3: "Zero code changes, any provider, any cloud"**
Most AI security solutions lock you in: to one cloud, one AI provider, or one deployment model. AnonReq presents an OpenAI-compatible interface — all major AI SDKs already support it. Change `base_url` and you are behind the gateway. No per-provider security configuration. No cloud lock-in. Runs on any infrastructure that can run Docker.

Content format: Side-by-side code snippet (before/after), latency benchmark chart, provider compatibility matrix.

**Narrative 4: "MENA sovereign AI: built for the region"**
For UAE and Saudi Arabia: AnonReq supports Arabic (ar-AE) locale detection, runs entirely within national infrastructure, and produces audit documentation that satisfies PDPL and UAE Information Assurance requirements. For organizations subject to SAMA (Saudi Central Bank) cybersecurity framework and UAE CBUAE guidance, AnonReq provides the data minimization control layer that AI provider contracts alone cannot satisfy.

Content format: Arabic-language product brief, PDPL compliance mapping, case study from MENA pilot customer. Presented at GITEX and regional fintech/govtech events.

### 7.4 Trust Building Program

This replaces the open-source community trust mechanism with an enterprise-grade evidence program.

**SOC 2 Type II certification:**
- Initiate audit engagement in Month 1 with a recognized auditor (Deloitte, KPMG, A-LIGN, or equivalent)
- Type I certification available by Month 6 (gap analysis + controls documentation)
- Type II certification (12-month observation period) by Month 18
- Report shared under NDA with all Enterprise and Appliance prospects during evaluation

**Annual penetration test:**
- Engage a recognized penetration testing firm (NCC Group, Bishop Fox, or equivalent) annually
- Scope: full API surface, Docker Compose deployment, fail-secure scenarios, tenant isolation
- Share executive findings summary (not full report) with enterprise prospects under NDA
- Share full report with Enterprise and Appliance customers under NDA

**SBOM and release attestation:**
- CycloneDX SBOM generated per release as a CI/CD output
- SBOM published alongside release artifacts
- Container images signed with Cosign, attested via OCI attestation
- SHA-256 checksums for all release artifacts
- Dependabot weekly scans with CVE response SLA (Critical: 24h, High: 72h, Medium: 7 days)

**Source code escrow:**
- Standard escrow arrangement offered to all Enterprise and Appliance customers
- Third-party escrow agent holds current release source
- Release conditions: vendor insolvency, 12-month product discontinuation, failure to maintain
- Escrow agreement template based on NCC Group/Iron Mountain standard terms
- No additional fee

**Supervised code review:**
- Enterprise and Appliance customers may request a supervised code review session
- Conducted by AnonReq SE or CTO at customer site or via secure virtual session
- Scope defined by customer: specific security-critical modules, data flow verification, audit log implementation
- Under mutual NDA, no code leaves the review session environment
- Available twice per year per customer

### 7.5 Content Strategy

**Compliance and regulatory content (primary trust driver):**
- "DORA Article 28 and LLM APIs: A Practical Compliance Guide for EU Financial Institutions" (whitepaper, gated)
- "EU AI Act Article 13 and AI Gateway Obligations: What Regulated Enterprises Must Document" (whitepaper, gated)
- "GDPR Data Minimization for LLM Prompts: Technical Controls That Satisfy DPA Auditors" (whitepaper, gated)
- "How AnonReq Satisfies HIPAA Technical Safeguard Requirements for LLM Data Flows" (compliance brief, gated)
- Quarterly regulatory update newsletter: new guidance from EDPB, FCA, SAMA, SEC, FINRA affecting AI data governance

**Technical credibility content (primary evaluation driver):**
- "AnonReq Architecture: Fail-Secure by Design" (technical deep-dive blog, ungated)
- "How We Property-Test Streaming Restoration with Hypothesis" (engineering blog, ungated)
- "Latency Benchmarks: AnonReq Overhead Across Providers and Prompt Sizes" (benchmark report, ungated)
- "Bidirectional Tokenization: Why Strip-and-Block Is Not Enough for LLM Security" (technical explainer, ungated)
- Architecture diagram (interactive, web-based, clickable components) — ungated, linked from homepage

**Sales enablement content (procurement support):**
- Security questionnaire response template (pre-filled for common enterprise security questionnaires)
- SBOM documentation guide (how to interpret the CycloneDX output)
- DPA template (data processing agreement, pre-drafted for GDPR Article 28 compliance)
- ROI calculator: build vs. buy (engineering time, compliance overhead, incident cost)
- Reference customer introduction request flow (post-pilot, before close)

**MENA-specific content:**
- Arabic-language product brief (ar-AE)
- PDPL compliance mapping document (UAE Federal Decree-Law No. 45/2021)
- SAMA cybersecurity framework alignment brief (Saudi financial institutions)
- UAE AI governance alignment (TDRA AI principles, eSafe program)

### 7.6 Events and Conferences

**Year 1 — speaking and booth presence:**

| Event | Location | Audience | Theme |
|-------|----------|----------|-------|
| RSA Conference | San Francisco | CISOs, security architects | AI security architecture, fail-secure design |
| Black Hat Europe | London | Security researchers, CISOs | Threat model, penetration test findings |
| SIBOS | London (2026) | Financial services technology leaders | DORA compliance, AI governance for banks |
| IAPP Global Privacy Summit | Washington DC | DPOs, compliance officers | GDPR Article 28 for LLM APIs |
| GITEX Global | Dubai | MENA technology leaders | Sovereign AI infrastructure, PDPL compliance |
| Risk.net AI in Finance | London | Risk and compliance, financial services | AI risk management, MNPI protection |
| KubeCon + CloudNativeCon | Atlanta | Platform engineers, DevOps | Deployment architecture, Helm chart, Kubernetes |

**Year 2 additions:**
- Money20/20 (Amsterdam and Las Vegas) — fintech, payments
- BioIT World — life sciences, pharma, HIPAA
- FT Live Artificial Intelligence Summit — enterprise AI governance

**Speaking strategy:** AnonReq founders/CTO present technical sessions, not vendor pitches. Topics: "How to fail-secure an LLM pipeline", "Property-based testing for security invariants", "What DORA actually requires of your AI stack." Technical credibility in sessions drives inbound interest from practitioners who then become internal champions.

### 7.7 Analyst Relations

**Target analysts (Year 2 priority):**
- Gartner: AI TRiSM (AI Trust, Risk, and Security Management), Data Security, API Security
- Forrester: AI Governance, Data Security and Privacy
- IDC: AI Infrastructure Security, European AI Regulations
- S&P Global / 451 Research: AI Infrastructure

**Strategy:**
- Brief Gartner AI TRiSM team before each major release
- Share architecture, compliance mapping, and customer evidence (anonymized)
- Target inclusion in Gartner "Market Guide for AI TRiSM Tools" (2027 edition)
- Offer to brief IDC on MENA sovereign AI infrastructure market dynamics

---

## 8. Sales Process

### 8.1 Lead Sources and Qualification

**Lead sources:**
- Outbound (SDR prospecting to named accounts): 40% of pipeline
- Inbound (content, events, referrals): 35% of pipeline
- Channel (partner-sourced): 25% of pipeline

**Qualified lead criteria (must meet 3 of 5):**
1. Regulated industry (financial services, healthcare, legal, insurance, government)
2. Active LLM usage or planned adoption within 6 months
3. CISO or DPO engaged in the evaluation
4. Preference for self-hosted/on-premises deployment
5. Budget authority for security tools ($30,000+/year)

**Disqualified:**
- SaaS-only infrastructure policy (AnonReq requires self-hosted deployment)
- No regulatory compliance requirements
- Sub-50 employee organizations (Starter tier self-service only; no dedicated sales engagement below this threshold)
- Organizations using only non-LLM AI

### 8.2 Sales Stages

| Stage | Definition | Exit Criteria |
|-------|------------|---------------|
| Prospect | Identified, not yet contacted | Meets 3/5 qualification criteria |
| Discovery | First call completed | Pain confirmed, stakeholders mapped, timeline identified |
| Technical Evaluation | Pilot deployment in progress | SE engaged, pilot checklist started |
| Commercial | Pilot complete, negotiating terms | Pilot success criteria met, DPA agreed |
| Closed Won | Contract executed | PO received or contract signed |
| Closed Lost | Passed on AnonReq | Loss reason documented |

### 8.3 Proof-of-Value Pilot Process

**Pilot structure:**
- Duration: 30 days (extendable to 60 for complex enterprise)
- Starter tier: 30-day time-limited trial license
- Enterprise tier: Enterprise license for pilot period, dedicated SE support

**Pilot schedule:**

| Day | Activity | Owner |
|-----|----------|-------|
| 1 | Docker Compose deployment, health check | Customer engineering |
| 1-2 | Verification run: PII injection, round-trip restoration, log scan, fail-secure test | Customer engineering + AnonReq SE |
| 3-5 | Integration: point existing SDK application at AnonReq (change base_url) | Customer engineering |
| 5-10 | Testing: run internal test suite through gateway, measure latency overhead | Customer engineering |
| 10-14 | Compliance review: audit log format, compliance preset activation, evidence package preview | Customer DPO/Compliance + AnonReq SE |
| 14-21 | Security review: architecture walkthrough, threat model, SOC 2 summary, pen test summary | Customer CISO + AnonReq SE |
| 21-28 | Custom configuration: recognizer rules, exclusion lists, locale configuration | Customer engineering |
| 28-30 | Pilot readout: success criteria review, commercial conversation, reference call | AnonReq AE + CSM |

**Pilot checklist (shared with customer Day 1):**
- [ ] Docker Compose deployment complete (target: under 30 minutes)
- [ ] Health endpoint returns 200 for all three services
- [ ] Sample PII prompt anonymized and fully restored — round-trip passes
- [ ] Verification script confirms no PII substrings in audit log output
- [ ] SSE streaming tested with primary provider (OpenAI or Anthropic)
- [ ] Custom recognizer loaded and detecting domain-specific identifier
- [ ] Compliance preset activated and confirmed in audit log field
- [ ] Latency overhead measured: P95 under 200ms for prompts under 1,000 words
- [ ] Fail-secure confirmed: stop Presidio container → request returns 500, not forwarded
- [ ] Prometheus metrics scraped and visible in customer observability stack

**Pilot success criteria:**
- Developer team confirms: no application code changes except base_url
- CISO confirms: fail-secure architecture meets documented requirements
- DPO confirms: compliance preset coverage satisfies active regulatory obligations
- Measured latency overhead within acceptable range for planned use cases

### 8.4 Enterprise Procurement Timeline

```
Weeks 1-2:   Discovery
             - Pain, timeline, stakeholders confirmed
             - Architecture overview session with SE
             - SOC 2 summary and pen test executive brief shared (NDA)

Weeks 2-6:   Technical Evaluation (Pilot)
             - Deployment and verification
             - Integration with existing AI application
             - Compliance and security review

Weeks 6-9:   Security Procurement Review
             - SBOM and dependency audit
             - Security questionnaire response package submitted
             - Source code escrow terms agreed
             - DPA reviewed and signed by legal

Weeks 9-11:  Commercial
             - Pricing and discount negotiation
             - Multi-year commitment discussion
             - Reference customer call (if requested)
             - Order form execution

Weeks 11-14: Production Deployment Planning
             - Production architecture reviewed
             - Integration with observability stack confirmed
             - Custom recognizers finalized
             - Team training scheduled

Week 14+:    Production Launch
             - Staged rollout to first use case
             - CSM onboarding call
             - Compliance evidence package delivered
```

### 8.5 Procurement Package

Delivered to every Enterprise and Appliance customer at the security review stage:

1. SOC 2 Type II report (full, under NDA)
2. Penetration test executive findings summary (under NDA)
3. CycloneDX SBOM for purchased release version
4. Signed release artifacts with SHA-256 checksums
5. SECURITY.md (disclosure process, CVE response SLAs)
6. Architecture diagram (all components and data flows)
7. Data flow diagram (PII path: detection → tokenization → forwarding → restoration)
8. Threat model (STRIDE-based, covering detection bypass, cache persistence, log leakage, tenant confusion)
9. Vulnerability management process document
10. Incident response plan (data exposure scenario)
11. SOC 2 / ISO 27001 control mapping
12. DORA/NIS2/GDPR/applicable framework compliance mapping
13. DPA template (GDPR Article 28 compliant, pre-drafted)
14. Source code escrow agreement template
15. SLO runbook
16. Cosign-signed container image attestations

---

## 9. Pilot & Onboarding

### 9.1 Deployment Options

**Starter tier (self-service):**
- Docker Compose: `docker compose up` — three services (anonreq, presidio-analyzer, valkey)
- `.env.example` configuration
- Target: healthy and processing first request within 30 minutes
- Guided by documentation alone; SE support not included in Starter

**Enterprise tier (guided):**
- Docker Compose for evaluation and small production deployments
- Kubernetes Helm chart for production-scale deployments with horizontal pod autoscaling
- Dedicated SE during pilot and initial production deployment (40 hours included)
- Configuration via ConfigMaps and Secrets; Prometheus operator integration

**Appliance tier (engineered):**
- Virtual appliance: OVF/OVA image for VMware, QCOW2 for KVM, AMI for AWS
- Physical appliance: AnonReq ships pre-configured hardware; on-site installation included (up to 2 visits/year)
- Transparent proxy: network routing guidance (iptables/eBPF/DNS), CA certificate installation
- SIEM integration configuration walkthrough

### 9.2 Guided Quickstart (All Tiers)

```bash
# Step 1 — Clone and configure
git clone https://license.anonreq.ai/enterprise/<customer_id>/anonreq.git
cp .env.example .env
# Edit .env: set ANONREQ_API_KEY, provider keys, compliance preset

# Step 2 — Start services
docker compose up -d
# Wait for health: anonreq → presidio → valkey

# Step 3 — Verify deployment
curl http://localhost:8080/health
# Expected: {"status":"healthy","services":{"valkey":"connected","presidio":"connected"}}

# Step 4 — Test round-trip with synthetic PII
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer $ANONREQ_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-AnonReq-Locale: en-US" \
  -d '{
    "model": "openai/gpt-4o",
    "messages": [
      {"role": "user", "content": "My email is test@example.com and IBAN is DE89370400440532013000"}
    ]
  }'
# Response: original values restored

# Step 5 — Verify no PII in logs
docker compose logs anonreq | grep -E "test@example.com|DE89370400440532013000" \
  && echo "FAIL: PII found in logs" || echo "PASS: No PII in logs"

# Step 6 — Test fail-secure
docker compose stop presidio-analyzer
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer $ANONREQ_API_KEY" \
  -d '{"model":"openai/gpt-4o","messages":[{"role":"user","content":"test"}]}'
# Expected: HTTP 500 — request not forwarded
docker compose start presidio-analyzer
```

### 9.3 Customer Onboarding Milestones (Enterprise)

| Milestone | Target Day | Owner | Criteria |
|-----------|------------|-------|----------|
| Deployment complete | Day 2 | Customer + SE | Health endpoint 200 |
| Round-trip verified | Day 3 | Customer + SE | Verification script passes |
| Application integrated | Day 7 | Customer engineering | Existing AI app routed through gateway |
| Compliance preset active | Day 10 | Customer + SE | Audit log shows preset field |
| Security review complete | Day 21 | Customer CISO + SE | SOC 2/pen test reviewed, architecture approved |
| Production launch | Day 45 | Customer engineering + CSM | First production traffic processed |
| Evidence package delivered | Day 50 | AnonReq SE | Compliance evidence package handed to DPO |

---

## 10. Competitive Positioning

### 10.1 AnonReq vs. NodeShift

| Dimension | AnonReq | NodeShift |
|-----------|---------|-----------|
| Deployment | Self-hosted (customer's infrastructure) | SaaS (NodeShift's sovereign cloud) |
| Data boundary | Raw data processed inside customer perimeter | Data processed on NodeShift infrastructure |
| Infrastructure ownership | Customer owns and operates | NodeShift operates |
| Provider choice | OpenAI, Anthropic, Gemini, Ollama, Azure, others | NodeShift-managed sovereign models |
| Air-gapped support | Yes (Appliance tier) | No |
| License | Proprietary, source escrow | Proprietary, SaaS |
| Pricing | Flat per-tenant (no consumption fees) | Consumption + compute |

**Positioning:** "NodeShift is a managed sovereign AI cloud. AnonReq is a self-hosted AI security gateway. If you need managed model hosting, NodeShift is relevant. If you already have cloud or on-prem infrastructure and need to secure AI traffic within your own perimeter, AnonReq is the answer. They solve adjacent but different problems."

**When we win:** Customer has existing infrastructure and needs a gateway layer only. Customer requires air-gapped or classified deployment. Customer wants multi-provider flexibility with their own model contracts.

**When we lose:** Customer has no cloud infrastructure and wants everything managed. Customer wants sovereign compute, not just a data security layer.

### 10.2 AnonReq vs. SaaS AI Security Gateways (AISG and similar)

| Dimension | AnonReq | SaaS Proxy |
|-----------|---------|------------|
| Data residency | Raw data stays inside customer perimeter | Raw data transits SaaS provider infrastructure |
| Third-party risk | Zero (AnonReq not in data path) | Adds vendor as a data processor (GDPR Art. 28) |
| Deployment | Self-hosted | SaaS |
| Tokenization | Context-preserving `[TYPE_N]` bidirectional | Strip or block only |
| SSE streaming | Full support with Tail_Buffer | Limited |
| Air-gapped support | Yes | No |
| Compliance evidence | SOC 2, pen test, SBOM, escrow | SOC 2, no escrow |

**Positioning:** "A SaaS proxy means your sensitive data passes through another vendor's infrastructure before reaching the LLM — adding a third party to your GDPR Article 28 chain and DORA ICT third-party risk register. AnonReq runs inside your perimeter. Your data never touches our infrastructure. We are not a processor of your data — we are software you deploy."

**When we win:** Customer has explicit regulatory prohibition on third-party data processing. Customer needs air-gapped deployment. Customer needs tokenization (not just blocking) to preserve LLM utility.

**When we lose:** Customer prioritizes ease of setup over data residency. Customer is too small to self-host. Customer evaluation is driven purely by "time-to-deploy" with no compliance overlay.

### 10.3 AnonReq vs. Cloud-Native (AWS Bedrock Guardrails, Azure AI Content Safety)

| Dimension | AnonReq | Cloud-Native |
|-----------|---------|--------------|
| Provider lock-in | None (any LLM provider) | Locked to one cloud and that cloud's AI services |
| Multi-cloud | Yes | No |
| Self-hosted / on-prem | Yes | No |
| Tokenization | Context-preserving, bidirectional | Strip or content filter only |
| Compliance presets | 6 jurisdictions | Cloud-region-specific |
| MENA compliance | Yes (ar-AE locale, PDPL mapping) | Not available |

**Positioning:** "Cloud-native guardrails are designed to make you buy more of that cloud. If you use Azure OpenAI, Azure AI Content Safety is convenient. The moment you add Anthropic, Gemini, or an on-prem model, it stops working. AnonReq works regardless of which AI provider you use or where your infrastructure lives."

**When we win:** Customer uses or plans to use multiple AI providers. Customer has multi-cloud or hybrid infrastructure. Customer operates in jurisdictions not well-served by cloud-native compliance tooling.

**When we lose:** Customer is fully committed to one cloud and one AI service and has no plans to change.

### 10.4 AnonReq vs. In-House Builds

| Dimension | AnonReq | In-House |
|-----------|---------|----------|
| Time to production | 30 minutes to deploy, 30 days to pilot | 6-12 months for equivalent capability |
| Streaming support | Built-in SSE with Tail_Buffer FSM | Rarely built correctly |
| Compliance presets | 6 built-in, validated | Manual per-regulation implementation |
| Property-based tests | Yes (Hypothesis, round-trip, fail-secure, locale) | Rare |
| 8-locale support | Built-in, checksum-validated | Per-locale custom work |
| Ongoing maintenance | Covered by subscription | Internal engineering time |
| SOC 2 / pen test | Included in subscription value | Customer must fund separately |

**Build vs. Buy analysis (ROI calculator inputs):**
- Estimated engineering cost to build equivalent: 3 senior engineers × 6 months = ~$450,000 (EU), ~$600,000 (US)
- Estimated ongoing maintenance: 0.5 FTE × $150,000 = $75,000/year
- AnonReq Enterprise (3 tenants): $144,000/year
- Breakeven vs. build: Year 1 already cost-positive; maintenance savings compound from Year 2

**When we win:** Customer has limited ML/security engineering bandwidth. Customer has a compliance deadline they cannot miss. Customer evaluates honestly against true cost of building and maintaining.

**When we lose:** Customer has already invested in a build that is "good enough." Customer has a team that views in-house as a strategic capability.

### 10.5 Sales Battle Cards Summary

| Competitor | Primary counter | Proof point |
|------------|----------------|-------------|
| NodeShift | Complementary — they are a sovereign cloud, we are a security gateway | "You can run AnonReq on your own infra inside your NodeShift environment" |
| SaaS proxy | Their infrastructure is in your data flow; ours is not | "We are not a data processor under GDPR Article 28. They are." |
| Bedrock / Azure Content Safety | Cloud lock-in; no multi-provider; no tokenization | "Works with any provider, any cloud, including your existing on-prem models" |
| In-house | 6-12 months vs. 30 minutes; no streaming; no locale; no compliance presets | ROI calculator: build cost vs. subscription cost, compliance gap, maintenance burden |

---

## 11. Revenue Model

### 11.1 Revenue Streams

| Stream | Description | Gross Margin | % of Revenue (Y1) |
|--------|-------------|-------------|-------------------|
| Starter subscriptions | Flat annual, self-service | 88% | 10% |
| Enterprise subscriptions | Per-tenant or flat annual, sales-led | 83% | 55% |
| Appliance subscriptions | Enterprise + hardware | 52-60% (hardware) | 22% |
| Professional services | Implementation, consulting, training | 72% | 13% |

### 11.2 Revenue Targets

**Year 1 (Build and Early Traction):**

| Metric | Conservative | Target | Stretch |
|--------|-------------|--------|---------|
| Starter subscriptions | 10 | 20 | 35 |
| Starter ARR | $180,000 | $360,000 | $630,000 |
| Enterprise tenants (paid) | 8 | 15 | 25 |
| Enterprise ARR | $288,000 | $540,000 | $900,000 |
| Appliance deals | 0 | 1 | 3 |
| Appliance ARR | $0 | $100,000 | $375,000 |
| Professional services | $40,000 | $80,000 | $150,000 |
| **Total ARR** | **$508,000** | **$1,080,000** | **$2,055,000** |

**Year 2 (Growth):**

| Metric | Conservative | Target | Stretch |
|--------|-------------|--------|---------|
| Starter subscriptions | 30 | 60 | 100 |
| Enterprise tenants | 25 | 50 | 80 |
| Appliance deals | 2 | 5 | 10 |
| Professional services ARR | $100,000 | $200,000 | $400,000 |
| **Total ARR** | **$1,200,000** | **$2,400,000** | **$4,200,000** |

**Year 3 (Scale):**

| Metric | Conservative | Target | Stretch |
|--------|-------------|--------|---------|
| Starter subscriptions | 80 | 150 | 250 |
| Enterprise tenants | 60 | 120 | 200 |
| Appliance deals | 8 | 18 | 35 |
| **Total ARR** | **$3,200,000** | **$6,500,000** | **$12,000,000** |

### 11.3 Unit Economics

**Starter tier:**
- ACV: $18,000/year
- CAC: $2,500 (primarily marketing attribution; no direct sales cost)
- CAC payback: 1.7 months
- Gross margin: 88%
- Churn target: < 5%/year

**Enterprise tier:**
- Average ACV: $54,000/year (3 tenants at $18,000 per tenant-year equivalent)
- Sales cycle: 90 days
- CAC: $28,000 (AE + SE time, marketing attribution, events)
- CAC payback: 6 months
- NRR target: 125% (tenant expansion, upgrade to Appliance)
- Gross margin: 83%

**Appliance tier:**
- Average ACV: $125,000/year (virtual) / $175,000/year (physical)
- Sales cycle: 120 days
- CAC: $45,000 (longer cycle, SE travel, proof-of-concept infrastructure)
- CAC payback: 4 months
- Gross margin: 55% (hardware) / 76% (virtual)

### 11.4 Pricing Adjustments

- Annual prepay: 10% discount vs. monthly billing
- Multi-year (2-year): 15% discount
- Multi-year (3-year): 22% discount
- Volume pricing: 10+ tenants: 20% off per-tenant rate; 50+ tenants: 37.5% off per-tenant rate
- Non-profit / academic: 40% discount on flat annual (Starter and Enterprise)
- Startup program (under $10M funding, under 100 employees): Starter tier at $500/month for Year 1

---

## 12. GTM Timeline

### 12.1 Pre-Launch (Months -3 to 0)

**Product readiness:**
- Stage 1 (Phases 1-7) complete and passing all property tests
- Production Readiness Review complete
- Signed release artifacts and SBOM pipeline operational
- License management infrastructure ready (customer-specific repository access per Starter/Enterprise tier)
- Legal: proprietary software license terms finalized, DPA template drafted, escrow agreement template ready

**Sales readiness:**
- CRM configured (HubSpot or Salesforce), lead scoring model set up
- Pricing page live (Starter tier transparent, Enterprise/Appliance: "request pricing")
- Enterprise trial request flow tested end-to-end
- Sales deck, one-pager, and ROI calculator finalized
- Procurement package assembled for first enterprise prospect
- 20 named accounts identified per AE territory; first 50 outbound contacts researched

**Marketing readiness:**
- Product website live with architecture diagram, latency benchmarks, compliance preset overview
- 3 ungated technical blog posts published (architecture, fail-secure design, streaming restoration)
- 2 gated compliance whitepapers ready (DORA/LLM, GDPR/LLM)
- Social media channels established (LinkedIn primary, X secondary)
- Event calendar for Year 1 confirmed, speaking submissions submitted

**Certification:**
- SOC 2 Type I audit engagement signed
- Pen test engagement scoped and scheduled (Month 1-2)

### 12.2 Launch (Month 0)

**Announcement:**
- Press release: "AnonReq Launches Proprietary AI Security Gateway for Regulated Enterprises — Raw PII Never Leaves Your Perimeter"
- Distribution: PRNewswire/BusinessWire, direct outreach to security and compliance press (The Register, CSO Online, SecurityWeek, Dark Reading, IAPP Privacy Tracker)
- LinkedIn announcement from founding team with architecture diagram
- Direct email to 50 CISO/Compliance Director contacts in financial services

**Product:**
- v1.0.0 released to first 5 design partner / pilot customers
- License portal live — customers receive repository access credentials
- All release artifacts published (SBOM, checksums, signed images)

**Pipeline:**
- 5 enterprise pilot commitments targeted for Month 0-2
- First partner conversation with target MSP

### 12.3 Months 1-3

**Pilot execution:**
- 10 enterprise pilots running
- Weekly SE check-in with each active pilot
- Collecting structured pilot feedback (NPS, friction points, feature requests)
- Target: 4 conversions to paid in Month 3

**Trust building:**
- Pen test completed, executive findings summary ready for distribution
- SOC 2 Type I gap assessment complete, controls documentation in progress
- First supervised code review session conducted with pilot customer

**Content:**
- Case study #1: pilot customer deployed to production (anonymized until customer approves named reference)
- Latency benchmark report published
- GDPR/LLM compliance guide published (gated lead magnet)
- First regulatory update newsletter distributed to email list

**Events:**
- RSA Conference — booth and speaking session submitted

**Channel:**
- First MSP partner agreement signed

### 12.4 Months 4-9

**Revenue:**
- 8+ paid Enterprise customers
- 15+ Starter subscriptions
- First Appliance deal pipeline identified

**Certifications:**
- SOC 2 Type I certification received — immediately added to procurement package
- Pen test completed and findings documented

**Content and awareness:**
- 3 case studies published (2 with named customers, 1 anonymized)
- DORA compliance guide published
- First conference talk delivered (RSA or equivalent)
- Analyst briefing: Gartner AI TRiSM team

**Channel:**
- 3 MSP partners signed and enabled
- AWS Marketplace listing live
- First SI partnership conversation initiated

**Product:**
- Stage 2 features in progress (Phases 8-16): SSO/RBAC, policy engine, rate limiting, AI firewall
- Enterprise Helm chart published

### 12.5 Months 10-12

**Revenue:**
- $720,000+ ARR achieved (target)
- 15+ Enterprise tenants
- 20+ Starter subscriptions
- 1 Appliance deal closed

**Certifications:**
- SOC 2 Type II observation period running (12 months, completes Month 18)

**Market position:**
- 3+ named reference customers available for introduction
- Gartner briefing complete
- Named in 2+ analyst reports (even if brief mentions)

**Product:**
- Stage 2 features shipped (Enterprise tier fully operational)
- MENA Arabic locale and PDPL mapping complete and validated

### 12.6 Year 2

**Expansion:**
- MENA go-to-market activated (GITEX, UAE distributor operational, Arabic sales collateral)
- APAC expansion begun (Singapore, Australia — partner-led)
- Physical Appliance first shipments

**Certifications:**
- SOC 2 Type II certification received — major trust unlock for enterprise procurement
- ISO 27001 certification initiated

**Revenue target:** $2.4M ARR

**Product:**
- Stage 3 (Appliance) features shipped: transparent proxy, AI firewall, voice protection, agent governance, SIEM integration
- OEM agreement with first enterprise software platform vendor

---

## 13. Success Metrics

### 13.1 Revenue Metrics

| Metric | Y1 Target | Y2 Target | Y3 Target |
|--------|-----------|-----------|-----------|
| Total ARR | $1,080,000 | $2,400,000 | $6,500,000 |
| Starter ACV | $18,000 | $18,000 | $18,000 |
| Enterprise ACV | $54,000 | $64,000 | $75,000 |
| Appliance ACV | $125,000 | $140,000 | $160,000 |
| Monthly churn (Starter) | < 4% | < 3% | < 2% |
| Monthly churn (Enterprise) | < 2% | < 1.5% | < 1% |
| Net Revenue Retention | 120% | 128% | 135% |
| Gross margin blended | 76% | 79% | 82% |

### 13.2 Sales Metrics

| Metric | Y1 Target | Y2 Target |
|--------|-----------|-----------|
| Total pilots started | 20 | 50 |
| Pilot conversion rate | 50% | 58% |
| Average pilot-to-close (days) | 60 | 50 |
| Enterprise sales cycle (days) | 90 | 75 |
| Pipeline coverage ratio | 3x ARR target | 3x ARR target |
| Win rate (competitive deals) | 35% | 45% |
| CAC (Enterprise) | $28,000 | $22,000 |
| CAC payback (Enterprise) | 6 months | 5 months |

### 13.3 Customer Success Metrics

| Metric | Target | Alert if |
|--------|--------|----------|
| NPS (Enterprise customers) | > 45 | < 25 |
| Time-to-value (deploy to first verified request) | < 2 hours | > 8 hours |
| Support ticket volume (Enterprise) | < 15/month/tenant | > 40/month/tenant |
| Critical incident response | < 1 hour | > 4 hours |
| On-time renewal rate | > 95% | < 88% |
| Referenceable customers | > 50% of paid base | < 30% |
| Quarterly business review completion | 100% | < 80% |

### 13.4 Trust and Certification Metrics

| Metric | Target | Date |
|--------|--------|------|
| SOC 2 Type I certification | Complete | Month 6 |
| Annual pen test completed | Complete | Month 3 |
| SOC 2 Type II certification | Complete | Month 18 |
| ISO 27001 certification initiated | In progress | Month 18 |
| SBOM per release (100% of releases) | 100% | Month 0 onward |
| Cosign-signed container images (100% of releases) | 100% | Month 0 onward |
| Source code escrow agreement signed (Enterprise/Appliance customers) | > 80% | Ongoing |
| Supervised code review requests fulfilled within 30 days | 100% | Ongoing |
| CVE Critical response (patch available within 24h) | 100% | Ongoing |
| CVE High response (patch available within 72h) | 100% | Ongoing |

### 13.5 Marketing Metrics

| Metric | Y1 Target |
|--------|-----------|
| Website visitors/month | 20,000 |
| Whitepaper downloads/month (gated) | 400 |
| Demo/trial requests/month | 50 |
| Marketing-qualified leads/month | 25 |
| Sales-accepted leads/month | 12 |
| Email list subscribers | 2,000 |
| Conference speaking slots | 5 |
| Analyst briefings completed | 4 |
| Case studies published | 3 |
| Press mentions (security/compliance press) | 15 |

### 13.6 Channel Metrics

| Metric | Y1 Target | Y2 Target |
|--------|-----------|-----------|
| MSP partners signed | 3 | 7 |
| SI partnerships signed | 0 | 2 |
| Compliance consultancy referral relationships | 10 | 25 |
| Channel-sourced ARR (% of total) | 15% | 25% |
| AWS Marketplace transactions | 3 | 10 |
| Azure Marketplace transactions | 2 | 8 |
| OEM agreements signed | 0 | 1 |

### 13.7 Product Quality Metrics

| Metric | Target | Source |
|--------|--------|--------|
| Property-based test pass rate | 100% | CI pipeline |
| Latency overhead P95 (prompts ≤1,000 words) | ≤ 100ms | /metrics |
| Streaming restoration accuracy | > 99.99% of tokens restored | Property test suite |
| Fail-secure event rate | ≤ 0.1% of requests | anonreq_fail_secure_events_total |
| Audit log write success rate | ≥ 99.99% | anonreq_audit_log_failures_total |
| Docker Compose startup time | ≤ 60 seconds | CI timing gate |
| False positive rate (out-of-box config) | < 5% on standard PII types | Benchmark test suite |
| False negative rate (active preset mandatory types) | < 1% | Benchmark test suite |

---

## Appendix A: Competitive Matrix

| Feature | AnonReq | NodeShift | SaaS Proxy | Bedrock Guardrails | Azure Content Safety | In-House (Presidio) |
|---------|---------|-----------|------------|-------------------|---------------------|---------------------|
| Self-hosted | Yes | No (their cloud) | No (their infra) | No | No | Yes |
| Raw data stays in customer perimeter | Yes | No | No | No | No | Yes |
| Bidirectional tokenization | Yes | No | Limited | No | No | Manual |
| SSE streaming support | Yes | Limited | Limited | No | No | No |
| Multi-provider | 5+ | Their models | 2-3 | AWS only | Azure only | Manual |
| 8+ locales | Yes | Unknown | 3-4 | US only | Region-specific | Manual |
| Fail-secure (property-tested) | Yes | Unknown | Partial | Partial | Partial | No |
| Compliance presets | 6 presets | Unknown | 2 | None | None | Manual |
| Arabic locale (MENA) | Yes | Unknown | No | No | No | Manual |
| Air-gapped deployment | Yes | No | No | No | No | Yes |
| SOC 2 Type II | In progress (Y1) | Yes | Yes | Yes (AWS) | Yes (Azure) | Customer responsibility |
| Source code escrow | Yes (standard) | No | No | N/A | N/A | N/A |
| SBOM per release | Yes | Unknown | No | AWS-managed | Azure-managed | Customer responsibility |
| Transparent proxy | Appliance tier | No | No | No | No | No |
| Voice/meeting protection | Appliance tier | No | No | No | No | No |
| Agent governance | Appliance tier | No | No | No | No | No |
| License | Proprietary + escrow | Proprietary SaaS | Proprietary SaaS | AWS proprietary | Azure proprietary | MIT (Presidio only) |

---

## Appendix B: Pricing Summary Card (Sales Tool)

```
ANONREQ PRICING (2026)

STARTER — $1,500/month ($15,000/year prepaid)
  Core anonymization pipeline
  8 locales including Arabic and Portuguese/Brazilian
  4 providers: OpenAI, Anthropic, Gemini, Ollama, Azure
  SSE streaming with bidirectional tokenization
  SBOM + signed release artifacts
  Email support, 48-hour SLO
  Single tenant

ENTERPRISE — from $4,000/tenant/month
  Everything in Starter, plus:
  SSO (OIDC, SAML), RBAC, mTLS
  Multi-tenant (up to 25 tenants)
  Policy engine: rate limits, spend controls, classification
  AI Security Firewall (injection, jailbreak, output policy)
  Compliance reports: GDPR, DORA, NIS2, HIPAA, SEC
  AI Governance Framework (ISO 42001, EU AI Act)
  Data lineage, record retention, legal hold
  Financial services: MNPI, MRM, DORA resilience
  Executive governance reporting
  SOC 2 report + pen test summary (under NDA)
  Source code escrow (standard contract term)
  99.9% SLA | Priority support | Kubernetes Helm chart
  Implementation engineer: 40 hours included

  Volume: 10+ tenants: 20% off | 50+ tenants: 37.5% off
  Multi-year: 2yr: −15% | 3yr: −22%

APPLIANCE — from $75,000/year (virtual) / $100,000/year (physical)
  Everything in Enterprise, plus:
  Transparent proxy + TLS interception
  Voice and meeting AI protection (≤150ms P99)
  Agent governance (MCP protocol, tool permissions)
  AI network discovery + shadow AI detection
  CASB integration + secure RAG pipeline protection
  SIEM: Splunk, Sentinel, QRadar, Elastic, Datadog
  Air-gapped mode (no telemetry, local model routing)
  1-hour SLA (24x7) | Dedicated support engineer
  Quarterly on-site architecture review

PROFESSIONAL SERVICES
  Standard implementation:  $25,000-$40,000
  Custom recognizers:        $5,000-$15,000 per bundle
  Compliance mapping:        $12,000-$20,000
  Security architecture:     $15,000-$30,000
  Training (per session):    $3,500
  Monthly retainer:          $6,000-$15,000
```

---

## Appendix C: Sales Discovery Questions

**CISO discovery:**
1. "What AI services are your teams using today — both sanctioned and unsanctioned?"
2. "How do you currently control what sensitive data goes to external LLMs?"
3. "Have you had any AI-related data exposure incidents, or are you anticipating regulatory scrutiny on AI governance?"
4. "What evidence would you need to present to your board or auditors to demonstrate that LLM usage is controlled?"
5. "How does your team feel about self-hosted vs. SaaS for security-critical infrastructure?"

**CIO/CTO discovery:**
1. "What is your AI adoption roadmap for the next 12 months — which teams and use cases are in scope?"
2. "How many LLM providers are you using or evaluating? Is multi-provider flexibility a strategic priority?"
3. "Has your security or compliance team set requirements that are slowing down AI deployment?"
4. "Have you evaluated building a gateway layer internally? What was the conclusion?"
5. "What does a 30-minute deployment and zero application code changes mean for your team's timeline?"

**DPO/Compliance discovery:**
1. "Have you completed a DPIA for your AI usage? What were the residual risks identified?"
2. "How are you currently satisfying GDPR Article 28 processor obligations for LLM providers?"
3. "What would you need to demonstrate to your DPA that personal data is not being sent to external AI providers?"
4. "Which regulatory frameworks are most urgent — GDPR, DORA, EU AI Act, or others?"
5. "What audit evidence do you need to produce, and on what cadence?"

---

## Appendix D: Launch Checklist

**Pre-launch (T-30 days):**
- [ ] v1.0.0 release artifacts signed and SBOM attached
- [ ] License portal live — customer repository access provisioned
- [ ] Proprietary software license terms finalized
- [ ] DPA template reviewed by legal counsel
- [ ] Source code escrow agreement template reviewed
- [ ] SECURITY.md with disclosure contact and CVE response SLAs
- [ ] Pen test engagement scoped (Month 1-2 delivery)
- [ ] SOC 2 audit engagement signed
- [ ] Product website live with architecture diagram
- [ ] 3 ungated technical blog posts published
- [ ] 2 gated compliance whitepapers ready and gated behind lead form
- [ ] Pricing page live (Starter transparent; Enterprise: "request pricing")
- [ ] Sales deck, one-pager, and ROI calculator finalized
- [ ] CRM configured and initial 50 named accounts loaded
- [ ] 5 design partner / pilot customers confirmed

**Launch day:**
- [ ] Press release distributed
- [ ] LinkedIn announcement (founding team)
- [ ] Direct email to 50 CISO/Compliance Director contacts
- [ ] Security and compliance press outreach (The Register, CSO Online, IAPP Privacy Tracker)
- [ ] Sales outreach sequence activated in CRM
- [ ] Monitor inbound inquiry channel (contact form, email)

**Post-launch (T+14 days):**
- [ ] First 5 pilot customers actively deploying
- [ ] Pen test engagement kicked off
- [ ] SOC 2 Type I gap assessment underway
- [ ] First compliance whitepaper download leads qualified
- [ ] Blog post: "Two Weeks In — What Regulated Enterprises Are Asking About AI Security"
- [ ] First partner conversation initiated

---

*Document version 2.0 | June 2026 | AnonReq — Confidential Internal Use*
*All pricing in USD. Subject to change. Contact sales@anonreq.ai for current pricing and enterprise agreements.*
