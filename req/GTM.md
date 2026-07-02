# AnonReq Go To Market Strategy

**Product:** AI Security Gateway for Regulated Enterprises
**Version:** 1.0
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

AnonReq is a self-hosted, Apache 2.0 licensed, anonymization gateway that sits between enterprise applications and external LLM APIs. It intercepts outbound requests, detects and replaces PII/PHI/MNPI with context-preserving tokens (`[TYPE_N]`), forwards sanitized data to OpenAI/Anthropic/Gemini/Ollama, and restores original values in responses — all within the customer's secure perimeter. No raw sensitive data ever crosses the network boundary.

Core engineering decisions: fail-secure architecture (any error blocks forwarding), ephemeral Valkey cache (no persistence), property-based correctness verification (Hypothesis), multi-locale detection (8 locales), and OpenAI-compatible wire protocol with provider adapters.

### Target Market

Regulated enterprises across financial services, healthcare, insurance, government, law firms, and accounting, operating in EU (GDPR), North America (HIPAA/SEC), APAC (PDPA/PDPP), MENA (PDPL), and LATAM (LGPD). Secondary market: mid-market organizations with compliance requirements and the open-source developer community.

### Revenue Model

Three-tier commercial model:
- **Open Source Core** (free, Apache 2.0) — adoption driver
- **Enterprise Subscription** ($2,500-$15,000/tenant/month) — SSO/RBAC, policy engine, compliance reports, SLA
- **Appliance** ($50,000-$200,000/year + hardware) — transparent proxy, AI firewall, voice/meeting, air-gapped

Professional services ($250-$500/hour) for implementation, custom recognizers, and compliance mapping.

### Go-To-Market Motion

Open-source community as top-of-funnel, direct enterprise sales for named accounts, channel partnerships with MSPs and system integrators, cloud marketplace presence (AWS, Azure). 30-day self-service pilot with guided Docker Compose deployment.

### Key Metrics (Year 1 Targets)

- 2,500 GitHub stars
- 500 active Docker pulls/week
- 20 paid pilots (10 enterprise, 10 mid-market)
- 8 pilot-to-paid conversions
- $480,000 ARR
- 4 channel partners signed

---

## 2. Market Analysis

### 2.1 Market Size

**Total Addressable Market (TAM):** AI Security Gateways — $4.2B by 2028 (CAGR 38.5%)
- Source: Gartner "Market Guide for AI Trust, Risk, and Security Management" (2025)
- Driven by enterprise genAI adoption hitting 85% of large organizations by 2027

**Serviceable Addressable Market (SAM):** $1.8B
- Self-hosted/open-source AI security infrastructure (excluding SaaS-only solutions)
- Regulated industry verticals requiring data residency

**Serviceable Obtainable Market (SOM):** $45M (Year 1-2), $180M (Year 3-4)
- Based on 0.5% initial capture of regulated enterprise segment
- Growth driven by compliance mandates in EU AI Act, DORA, NIS2

### 2.2 Key Trends

1. **GenAI adoption in regulated industries**: Financial services, healthcare, and legal are accelerating LLM use for document analysis, code generation, customer interaction, and internal knowledge retrieval. Each creates PII exposure vectors.

2. **Regulatory pressure**: EU AI Act (effective 2026), DORA (2025), NIS2 (2024), SEC cybersecurity rules, and GDPR enforcement create liability for enterprises that fail to control AI data flows. Regulators increasingly view AI data leakage as a governance failure.

3. **Shadow AI**: Employees use ChatGPT, Claude, Gemini, and Copilot for work tasks without IT approval. Enterprises have no visibility into what data is being sent to AI providers. Gartner estimates 60% of AI usage in enterprises is unsanctioned.

4. **Provider diversity**: Organizations want multi-provider flexibility but need consistent policy enforcement. A single gateway layer solves this more efficiently than per-provider security configurations.

5. **Open-source adoption in security**: Enterprises prefer auditable, self-hosted security infrastructure over black-box SaaS solutions, particularly for data-loss prevention and compliance.

### 2.3 Competitive Landscape

| Competitor | Category | Strengths | Weaknesses | AnonReq Advantage |
|------------|----------|-----------|------------|-------------------|
| NodeShift | Sovereign AI Cloud | Turnkey, managed, sovereign data centers | Vendor lock-in, SaaS model, higher cost | Self-hosted, open-source, no dependency |
| AI Security Gateway (AISG) | SaaS proxy | Easy setup, broad provider support | No on-prem option, data passes through their infra | Self-hosted, zero-trust architecture |
| In-house builds | Custom | Full control | 6-12 month dev cycle, ongoing maintenance | Ready in 30 min, property-tested, community |
| AWS Bedrock Guardrails | Cloud native | Tight AWS integration | AWS-only, no multi-cloud, vendor lock-in | Provider-agnostic, self-hosted, any infra |
| Azure AI Content Safety | Cloud native | Azure integration, content safety focus | Azure-only, no anonymization/tokenization | Full pipeline: detect, tokenize, restore, audit |
| Open-source filters (presidio-only) | Library | Flexible, customizable | No gateway, no streaming, no restoration, no audit | Production gateway, SSE support, compliance |

### 2.4 AnonReq Differentiation

1. **Bi-directional tokenization**: Anonymizes outbound, restores inbound. Competitors either strip data (lossy) or block requests entirely. AnonReq preserves LLM utility while protecting sensitive data.

2. **Fail-secure architecture**: Any error — detection failure, cache outage, timeout — blocks forwarding. Competitors may degrade gracefully (leaking data) rather than failing closed.

3. **Open-source core (Apache 2.0)**: Auditable, forkable, no vendor lock-in. Enterprises can verify the security model, contribute improvements, and build on the platform.

4. **Property-based verification**: Hypothesis test suite provides generative proof of round-trip correctness, token uniqueness, fail-secure invariants, and cross-request randomization. Enterprises can verify guarantees independently.

5. **Streaming first**: SSE restoration with Tail_Buffer for split tokens — not retrofitted onto a synchronous pipeline.

6. **Multi-locale, multi-jurisdiction**: 8 locales, 6 compliance presets, locale-specific checksum validation. Competitors are predominantly English/US-only.

---

## 3. Target Customer Segments

### 3.1 Primary: Regulated Enterprises

**Sectors:**
- **Financial Services**: Banks, asset managers, hedge funds, insurers, fintech
  - Pain: MNPI exposure, SEC/FINRA record-keeping, DORA compliance, Model Risk Management (SR 11-7)
  - Use case: Trading desk analysts using LLM for research; compliance teams reviewing AI outputs; customer service chatbots handling PII
- **Healthcare**: Hospitals, health insurers, pharma, medtech
  - Pain: HIPAA, patient data in AI prompts, clinical note processing
  - Use case: Clinical decision support, medical record summarization, patient communication
- **Insurance**: Underwriting, claims processing, customer service
  - Pain: PII in claims documents, regulatory filing requirements
- **Government**: Federal, state, local agencies
  - Pain: Data sovereignty, classified information, procurement requirements for self-hosted
- **Legal**: Law firms, corporate legal departments
  - Pain: Attorney-client privilege, confidential case documents, discovery exposure
- **Accounting**: Audit firms, tax preparation
  - Pain: Client financial data, tax return PII, professional ethics obligations

**Geography priorities:**
1. EU/EEA (GDPR — largest regulatory driver, early adopters)
2. North America (HIPAA, SEC, FINRA — large market, early revenue)
3. UK (UK GDPR, FCA)
4. Brazil (LGPD — growing compliance market)
5. MENA (PDPL, UAE data protection)
6. APAC (PDPA Singapore, PDPP Japan, Privacy Act Australia)
7. South Africa (POPIA)
8. Canada (PIPEDA)

**Enterprise size:** 1,000-50,000 employees, $500M+ revenue, dedicated compliance/security teams

### 3.2 Secondary: Mid-Market with Compliance

**Sectors:**
- Accounting firms (50-500 employees)
- Boutique law firms
- Regional banks and credit unions
- HR tech platforms
- Enterprise SaaS companies serving regulated industries

**Enterprise size:** 50-1,000 employees, $10M-$500M revenue, lean compliance/IT teams

**Differentiated approach:** Self-service, Docker Compose deployment, guided pilot, lower price point (per-tenant or flat annual). Community edition likely sufficient for many mid-market needs.

### 3.3 Tertiary: Open-Source Community

**Segments:**
- Individual developers experimenting with AI security
- AI startups needing quick anonymization
- Platform engineers evaluating self-hosted options
- Security researchers auditing the codebase

**Value:** Community drives awareness, contributions, integrations, and enterprise referrals. Treat as top-of-funnel.

---

## 4. Personas & Buyer Journey

### 4.1 Personas

#### Technical Buyer: CISO / Security Architect

| Attribute | Detail |
|-----------|--------|
| Title | Chief Information Security Officer, VP Security, Security Architect |
| Primary concern | Data leakage, compliance liability, unauthorized AI usage |
| Technical depth | Deep — understands TLS, proxies, tokenization, fail-secure patterns |
| Questions they ask | Where does my data go? Can you prove no PII crosses the boundary? What if Presidio fails? Is the audit log verifiable? |
| Information sources | Gartner, CISO peer networks, security conferences (RSA, Black Hat), technical blog posts, architecture diagrams |
| Buying criteria | Fail-secure proof, SBOM, SOC2 mapping, architecture review, threat model |
| Objections | "We can build this with Presidio + a reverse proxy", "I don't trust open-source security", "How is this different from NodeShift?" |

#### Economic Buyer: CIO / CTO

| Attribute | Detail |
|-----------|--------|
| Title | Chief Information Officer, Chief Technology Officer, VP Engineering |
| Primary concern | AI adoption velocity, developer productivity, vendor lock-in, total cost |
| Technical depth | High-level technical, budget authority |
| Questions they ask | How fast can we deploy? Will this slow down our AI apps? Does it work with our existing stack? What is the total cost vs building in-house? |
| Information sources | Analyst reports, peer CIO networks, case studies, ROI calculators |
| Buying criteria | Time-to-value, developer experience, provider flexibility, pricing predictability |
| Objections | "Our team can build this in a sprint", "Another proxy adds latency", "We already use Bedrock Guardrails" |

#### Influencer: Compliance Officer / DPO

| Attribute | Detail |
|-----------|--------|
| Title | Data Protection Officer, Compliance Director, Regulatory Affairs |
| Primary concern | Regulatory compliance (GDPR Art. 28 processor obligations, HIPAA, DORA) |
| Technical depth | Moderate — understands data flows, prefers auditable controls |
| Questions they ask | Does this satisfy GDPR Art. 28? Can we get a compliance evidence package? Is the detection aligned with our Data Protection Impact Assessment? |
| Information sources | IAPP, regulatory guidance, peer DPO networks, whitepapers |
| Buying criteria | Compliance preset mapping, audit trail, no-PII-in-logs proof, retention/legal hold |
| Objections | "Our current DLP covers this", "We need on-prem to pass audit" |

#### User: Developer / Platform Engineer

| Attribute | Detail |
|-----------|--------|
| Title | Platform Engineer, ML Engineer, DevOps Engineer |
| Primary concern | Latency, reliability, developer experience, documentation quality |
| Technical depth | Deep — will run the pilot, integrate APIs, debug issues |
| Questions they ask | How do I change my OpenAI client? Does streaming work? What's the latency overhead? Is it production-ready? |
| Information sources | GitHub, technical blog posts, Stack Overflow, Discord/community |
| Buying criteria | Clean API, SDK examples, fast quickstart, Docker Compose, low overhead |
| Objections | "It adds latency", "I can just use Presidio directly", "Our app uses multiple providers" |

### 4.2 Buyer Journey

**Stage 1: Awareness** (CISO/CIO)
- Trigger: Shadow AI audit reveals unsanctioned LLM usage, or regulatory requirement for AI governance
- Sources: Hacker News, security conferences, analyst reports, peer referral
- AnonReq touchpoint: Open-source release on GitHub, HN post, conference booth, whitepaper

**Stage 2: Evaluation** (Security Architect + Platform Engineer)
- Developer discovers on GitHub, deploys Docker Compose in 30 minutes
- Runs quickstart with sample PII data, verifies no PII in logs
- Evaluates latency overhead, streaming behavior, provider support
- Security architect reviews architecture, threat model, fail-secure guarantees

**Stage 3: Procurement** (CISO + Procurement + Legal)
- RFI/RFP driven by compliance requirement
- Security questionnaire: SBOM, SOC2, architecture, data flow, incident response
- Pilot transitions to paid proof-of-value with real data (30-60 days)
- Legal reviews Apache 2.0 license, commercial agreement

**Stage 4: Deployment** (Platform Engineering Team)
- Container deployment into staging environment
- Integration with existing observability stack
- Custom recognizer configuration for enterprise-specific identifiers
- Compliance preset activation and verification

**Stage 5: Expansion** (CSM + CISO)
- Additional tenants, business units, geographies
- Upgrade from open-source to enterprise tier for SSO, RBAC, policy engine
- Eventual appliance tier for transparent proxy and AI firewall

### 4.3 Decision-Making Unit (DMU)

| Role | Stage | Influence | Authority |
|------|-------|-----------|-----------|
| CISO | Evaluate, Procure | High (technical requirements) | Sign off |
| CIO/CTO | Awareness, Procure | High (budget) | Budget approval |
| DPO/Compliance | Evaluate, Procure | Medium (requirements) | Recommend |
| Platform Engineer | Evaluate, Deploy | Medium (technical assessment) | Recommend |
| Legal | Procure | Low (contract terms) | Legal sign off |

---

## 5. Product Tiers & Packaging

### 5.1 Open Source Core (Apache 2.0)

**Feature set:**
- Full gateway implementation (Phases 1-7)
- POST /v1/chat/completions with streaming support
- Hybrid detection engine (regex + NER, 8 locales)
- Tokenization and restoration (bidirectional)
- Ephemeral Valkey cache
- Multi-provider support (OpenAI, Anthropic, Gemini, Ollama)
- Metadata-only audit logging
- Custom detection rules and exclusion lists
- Docker Compose deployment
- Prometheus metrics (/metrics, /health)
- Property-based test suite
- Multilingual documentation (EN, DE, FR, ES, PT-BR)
- Community support via GitHub Issues + Discord

**License:** Apache 2.0 — commercial use, modification, redistribution, sublicensing allowed. Patent grant included.

**Target user:** Developers, startups, mid-market organizations with capable engineering teams, proof-of-value pilots

**Support:** Community (GitHub, Discord), best-effort responses

### 5.2 Enterprise Tier (Subscription)

**Feature set (all open-source features plus):**
- SSO/OIDC/SAML authentication and RBAC (Phase 8)
- Policy engine (rate limiting, spend controls, data classification) (Phase 8, 12)
- Compliance reporting engine and regulatory framework mapping (Phase 11, 15)
- AI governance framework (ISO 42001 alignment) (Phase 14)
- Human oversight and kill-switch controls (Phase 14)
- Prompt security and AI firewall (Phase 10)
- AI governance and oversight dashboard (admin portal, Phase 14 iteration)
- SBOM, attestation, supply chain security (Phase 11)
- Fairness monitoring and bias assessment (Phase 16)
- Financial services compliance (MNPI, MRM, DORA, financial crime) (Phase 15)
- Config change audit trail, 7-year retention (Phase 11)
- Post-deployment monitoring and incident management (Phase 16)
- Data lineage and traceability (Phase 16)
- Record retention and legal hold (Phase 16)
- Business unit segregation and Chinese Walls (Phase 16)
- Executive governance reporting (Phase 16)
- Conformity assessment package export (Phase 14)
- Guaranteed SLA (99.9% uptime, 4-hour response)
- Priority support (Slack + email, 8x5 or 24x7)
- SSO enforcement and audit-ready deployment
- Helm chart for Kubernetes deployment

**Pricing models:**

| Model | Price | Best for |
|-------|-------|----------|
| Per-tenant/month | $2,500-$15,000 depending on tenant count (volume discounts at 10+, 50+) | Banks, insurers with multiple BUs |
| Flat annual (single tenant) | $30,000-$60,000/year | Single-org enterprises |
| Flat annual (up to 5 tenants) | $100,000-$200,000/year | Large enterprises with subsidiaries |
| Consumption-based (per million tokens processed) | $5-$15 per million tokens | Mid-market, variable usage |

**Edge cases:**
- Non-profit / academic pricing: 50% discount on flat annual
- Startup program (under $10M funding): $1,000/month enterprise tier
- Multi-year commitment (2+ years): 15% discount

**Onboarding included:** Dedicated implementation engineer (40 hours), compliance mapping workshop, custom recognizer development

### 5.3 Appliance Tier (Subscription + Hardware)

**Feature set (all enterprise features plus):**
- Universal AI traffic gateway (transparent proxy, TLS interception) (Phase 17)
- AI-aware DLP with 8 categories and contextual rules (Phase 13)
- Voice and meeting AI protection (SIP/RTP interception, STT pipeline) (Phase 17)
- Agent and tool call governance (MCP protocol, tool permissions) (Phase 18)
- AI firewall (injection, jailbreak, outbound policy) (Phase 13)
- AI network discovery and shadow AI detection (Phase 19)
- AI CASB integration (Phase 19)
- Secure RAG pipeline protection (Phase 19)
- AI SOC/SIEM integration (5 SIEM platforms) (Phase 20)
- Desktop agents for endpoint visibility (Phase 21)
- Sovereign AI control plane with local model routing (Phase 21)
- Air-gapped deployment support (Phase 21)
- Dedicated support engineer, 1-hour SLA
- Quarterly architecture review and health check
- On-premise deployment engineering support

**Pricing:**

| SKU | Price/year | Includes |
|-----|------------|----------|
| Virtual Appliance (VM) | $50,000-$100,000 | Enterprise tier + transparent proxy + AI firewall + all appliance features |
| Physical Appliance | $75,000-$200,000 | Pre-configured hardware + all features + air-gapped support + on-site installation |
| Air-Gapped Appliance | $150,000-$300,000 | Physical appliance + no telemetry + local model routing + dedicated HSM |

**Hardware specs (physical appliance):**
- 2U rackmount, dual Xeon/EPYC, 128GB RAM, 2TB NVMe
- GPU (A10 or equivalent) for local STT and small-model inference
- Dual 25GbE network interfaces, Bypass LAN pair for fail-open option
- TPM 2.0, optional HSM integration

### 5.4 Professional Services

| Service | Price | Description |
|---------|-------|-------------|
| Implementation | $25,000-$50,000 flat | Deployment, integration, policy configuration, compliance mapping |
| Custom recognizer development | $5,000-$15,000 per bundle | Domain-specific PII/MNPI patterns for enterprise-specific identifiers |
| Compliance mapping workshop | $10,000-$20,000 | Map controls to DORA/NIS2/GDPR/SEC, generate evidence package |
| Security architecture review | $15,000-$30,000 | Threat model, architecture review, fail-secure verification |
| Training | $3,000-$5,000 per session | Operator training, compliance team training |
| Retainer | $5,000-$15,000/month | Ongoing support, quarterly reviews, compliance updates |

### 5.5 Pricing Principles

1. **Open source never paywalled**: All features in Phases 1-7 are and remain Apache 2.0. The license is permanent and irrevocable.
2. **Enterprise features are additive, not coercive**: No degrading open-source features. Enterprise tier adds compliance, governance, and operational capabilities.
3. **Self-service to enterprise sales**: Any organization can deploy the open-source core without talking to sales. Enterprise sales engage only when SSO, compliance reporting, or SLA are required.
4. **Predictable pricing**: No hidden per-seat, per-provider, or per-region fees. Transparent pricing page.

---

## 6. Channel Strategy

### 6.1 Direct Sales

**Enterprise sales team structure (Year 1):**
- 2 Enterprise AEs (named accounts, $500M+ target companies)
- 1 SDR/BDR (outbound prospecting, pipeline generation)
- 1 Solutions Engineer (technical pre-sales, pilot support)
- 1 Customer Success Manager (post-sales, expansion)

**Named account targeting (Year 1):**
- 20 financial services institutions (EU + US)
- 10 healthcare organizations (US + EU)
- 10 insurance carriers (EU + US)
- 5 government agencies (EU)
- 5 law/accounting firms (UK + US)

**Sales territories:**
- EMEA (London/Amsterdam-based) — primary focus
- North America (US East Coast) — secondary focus
- APAC (Singapore-based) — Year 2+ expansion

### 6.2 Channel Partners

**Cloud Resellers:**
- AWS Marketplace (transact via API, private offers for enterprise)
- Azure Marketplace (transact via Azure Marketplace metered billing)
- GCP Marketplace (Year 2)

**Managed Service Providers (MSPs):**
- Partner with MSPs serving regulated industries (banks, healthcare)
- MSPs resell appliance tier as managed service offering
- Revenue share: 20% referral, 30% resell (MSP handles support)
- Target: 4 MSP partners in Year 1

**System Integrators:**
- Accenture, Deloitte, PwC, EY, KPMG — compliance and AI practices
- SIs implement AnonReq as part of broader AI governance engagements
- Revenue share: 15% referral fee, or SI marks up 20-30% on professional services
- Target: 3 SI partnerships in Year 2

**Compliance Consultancies:**
- Boutique DORA/GDPR/SEC compliance firms
- Recommend AnonReq to clients as part of compliance remediation
- Revenue share: 10% referral fee
- Target: 10 compliance partners in Year 1

**Regional distributors:**
- Brazil: Partner with local cloud/SI firms for LGPD compliance market
- MENA: Partner with UAE-based cybersecurity distributors
- Japan: Partner with local IT trading companies for PDPP compliance

### 6.3 Open-Source Community as Funnel

**Strategy:** Treat the open-source community as top-of-funnel for enterprise sales. Developers who deploy AnonReq at a startup or mid-market become advocates when they join regulated enterprises.

**Community touchpoints:**
- GitHub (code, issues, discussions)
- Discord/Slack (community support, announcements)
- Documentation site (tutorials, architecture guides)
- Developer blog (technical deep-dives)

**Conversion path:**
1. Developer discovers AnonReq on GitHub/HN/tech blog
2. Docker Compose up in 30 minutes, runs quickstart
3. Uses open-source core indefinitely, or encounters need for SSO/enterprise features
4. Requests enterprise trial, engages sales team
5. Converts to paid enterprise subscription

### 6.4 Cloud Marketplaces

**AWS Marketplace:**
- List Enterprise Tier as private offer (mature organizations prefer procurement through AWS)
- BYOL (bring your own license) model for open-source customers
- Appliance tier as AMI in AWS Marketplace

**Azure Marketplace:**
- Enterprise Tier as transactable offer
- Integration with Azure AD for SSO evaluation

---

## 7. Marketing & Positioning

### 7.1 Messaging Framework

**Problem statement:**
"Enterprises adopting AI are exposing PII, PHI, MNPI, and trade secrets to external LLM providers. Current solutions either block AI usage entirely (kill productivity) or trust third-party SaaS proxies with sensitive data (increase risk). Compliance officers cannot verify black-box privacy filters."

**Solution:**
"AnonReq is a self-hosted, open-source gateway that detects sensitive data, replaces it with tokens before it leaves your network, and restores original values in responses. Raw PII never crosses the network boundary. The code is auditable. The guarantees are property-tested."

**Proof:**
"Deploy in 30 minutes. Run the verification script. Confirm no PII in logs. Confirm round-trip restoration. Confirm fail-secure behavior. No trust required — only verification."

### 7.2 Key Narratives

**Narrative 1: "Raw PII never crosses the network boundary"**
- Focus on the fail-secure, no-compromise security posture
- Contrast with competitors that degrade gracefully (continuation of service at cost of data exposure)
- Visual asset: Data flow diagram showing red/green boundary with "NO RAW PII" annotation at the perimeter

**Narrative 2: "AI security for regulated enterprises"**
- Focus on compliance presets, regulatory framework alignment, audit trails
- Regulatory mapping tables (GDPR, DORA, NIS2, HIPAA, SEC, FINRA)
- Enterprise controls (SSO, RBAC, policy engine, retention, legal hold)

**Narrative 3: "Open-source, auditable, fail-secure"**
- Focus on the open-source core as a trust-building asset
- "If you can't audit it, you can't trust it with your sensitive data"
- Contrast with SaaS competitors where security claims cannot be independently verified
- Community contributions as validation

**Narrative 4: "One wire protocol, any provider"**
- Focus on OpenAI-compatible interface as universal adapter
- "Change your base_url, keep your existing code, add security"
- Multi-provider flexibility without per-provider security configuration

### 7.3 Content Strategy

**Awareness-stage content (top of funnel):**
- "Why Every Regulated Enterprise Needs an AI Security Gateway" (whitepaper)
- "The Cost of Shadow AI: How Unsanctioned LLM Usage Exposes PII" (research brief)
- "GDPR Art. 28 and LLM APIs: What Your Processor Obligations Really Mean" (compliance guide)
- "DORA Compliance for AI: A Practical Guide" (regulatory mapping series)

**Evaluation-stage content (middle of funnel):**
- "AnonReq Architecture Deep-Dive: Fail-Secure by Design" (architecture blog post)
- "Benchmark: AnonReq vs NodeShift vs In-House Presidio Build" (comparison)
- "Streaming Round-Trip Verification: How We Property-Test SSE Restoration" (engineering blog)
- "Multi-Locale PII Detection: 8 Jurisdictions, One Pipeline" (technical deep-dive)
- Interactive architecture diagram (web-based, clickable components)
- Deployment time calculator ("How fast can you deploy AnonReq?")

**Decision-stage content (bottom of funnel):**
- "AnonReq Enterprise vs Open Source: Feature Comparison" (comparison matrix)
- "Security Questionnaire Response Package: SBOM, Architecture, Threat Model" (gated)
- "Integrating AnonReq with Your Compliance Framework" (implementation guide)
- Case studies (when available after pilots)

**Always-on content:**
- Technical blog (bi-weekly): architecture, engineering decisions, community contributions
- Changelog highlights (monthly): new features, improvements, bug fixes
- Community spotlight (monthly): user stories, integrations built by community
- Regulatory update tracker (quarterly): new compliance frameworks, regulatory changes

### 7.4 Events & Conferences

**Year 1 speaking/booth:**

| Event | Focus | Target |
|-------|-------|--------|
| RSA Conference (San Francisco) | AI security, DLP for AI | CISO, security architects |
| KubeCon + CloudNativeCon | Deployment, Helm, operators | Platform engineers |
| Black Hat (Las Vegas + EU) | AI security, threat model | Security researchers, CISO |
| IAPP Global Privacy Summit | GDPR, AI governance | DPOs, compliance officers |
| FinTech & AI events (Money20/20, Finovate) | Financial services, MNPI | Fintech, banking |

**Regional events (Year 2+):**
- Gitex (Dubai) — MENA market
- SaaStr (APAC edition) — APAC market
- Future of Fintech (Sao Paulo) — LATAM market

### 7.5 Analyst Relations

**Priority analysts (Year 2):**
- Gartner: AI TRiSM, API Security, Cloud Security
- Forrester: AI Governance, Data Security
- 451 Research / S&P Global: AI Infrastructure

**Strategy:** Brief analysts before major releases. Share architecture and compliance mapping. Target inclusion in "Cool Vendors" and market guides.

### 7.6 Developer Relations

**Activities:**
- GitHub sponsors program (no financial, but recognition for contributors)
- Community-contributed locale recognizer bundles (first 5 accepted = contributor swag)
- Swag program (stickers, t-shirts for contributors and reference customers)
- Office hours (bi-weekly community call via Discord)

---

## 8. Sales Process

### 8.1 Lead Qualification Criteria

**Qualified lead (must meet 3 of 5):**
1. Regulated industry (financial services, healthcare, legal, gov)
2. Active LLM usage or planned LLM adoption within 6 months
3. Compliance-driven security requirements (DPO/CISO engaged)
4. Self-hosted/premises preference (no SaaS-only)
5. Budget for security tools ($50k+ annual)

**Disqualified:**
- SaaS-only infrastructure policy (AnonReq is self-hosted)
- No regulatory compliance requirements
- Using only non-LLM AI (e.g., predictive models only)
- Sub-50 employee organizations (too small for self-hosted value prop)

### 8.2 Proof-of-Value / Pilot Process

**Pilot structure:**
- Duration: 30 days (extendable to 60 for complex enterprise)
- Standard pilot: Open-source core (free, self-deployed)
- Enterprise pilot: Enterprise tier with dedicated support (time-limited license key)

**Pilot steps:**
1. **Day 1 - Deployment**: Engineering team deploys Docker Compose (guided quickstart)
2. **Day 1-3 - Verification**: Run verification script, confirm no PII in logs, confirm round-trip restoration
3. **Day 3-7 - Integration**: Point existing OpenAI SDK application at AnonReq (change base_url)
4. **Day 7-14 - Testing**: Developer team runs internal test suite through gateway, validates latency
5. **Day 14-21 - Compliance review**: Security/Compliance reviews audit logs, fail-secure behavior, architecture
6. **Day 21-30 - Decision**: Enterprise pilot graduates to production deployment or conversion to paid

**Pilot checklist:**
- [ ] Docker Compose deployment complete (under 30 min)
- [ ] Health endpoint returns 200
- [ ] Sample PII prompt anonymized and restored successfully
- [ ] No PII values found in log output (verification script passes)
- [ ] SSE streaming works with provider (OpenAI or Anthropic)
- [ ] Custom recognizer loaded (if applicable)
- [ ] Compliance preset activated (GDPR or other)
- [ ] Latency overhead measured and acceptable (< 200ms P95)
- [ ] Fail-secure confirmed (kill Presidio container, verify 500 error)

**Pilot success criteria:**
- Developer team confirms usability (no application code changes except base_url)
- CISO confirms fail-secure architecture meets requirements
- DPO confirms compliance preset alignment with regulatory obligations
- Measured overhead within acceptable range for production use
- Security team approves architecture

### 8.3 Enterprise Procurement Timeline

```
Week 1-2:  Discovery & RFI
  - Security architect evaluates architecture, threat model, data flow
  - Compliance officer reviews regulatory mapping
  - Legal reviews license terms

Week 2-4:  Proof of Value
  - Engineering deploys and tests core features
  - Pilot runs with real application traffic (non-production)

Week 4-6:  Security Review
  - SBOM, dependency audit, supply chain review
  - Penetration testing (customer-led or AnonReq-provided)
  - Architecture review with customer security team
  - SOC2 readiness review (or equivalent)

Week 6-8:  Commercial & Legal
  - Pricing negotiation (volume discounts, multi-year)
  - DPA signing (Data Processing Agreement)
  - Order form execution
  - Licensing terms for commercial tier

Week 8-10: Deployment Planning
  - Production deployment architecture approved
  - Integration with customer observability stack
  - Custom recognizer configuration
  - Team training

Week 10-12: Production Launch
  - Deploy to production (staged rollout)
  - Monitor metrics, latency, audit logs
  - Compliance evidence package generated
```

### 8.4 Technical Close Requirements

**Procurement package provided to enterprise customer:**

1. **SBOM** (CycloneDX JSON, per release version)
2. **SECURITY.md** (disclosure process, response SLAs)
3. **Architecture diagram** (Mermaid or draw.io, describing all components and data flows)
4. **Data flow diagram** (describing PII path through detection, tokenization, forwarding, restoration)
5. **Threat model** (STRIDE-based, covering detection bypass, cache persistence, log leakage, tenant confusion)
6. **Vulnerability management process** (how reports are handled, patching cadence)
7. **Incident response plan** (for data exposure scenario)
8. **SOC2 / ISO 27001 readiness mapping** (mapping controls to SOC2 trust criteria / ISO 27001 Annex A)
9. **DORA/NIS2/GDPR compliance mapping** (control-by-control mapping)
10. **SLO runbook** (how SLOs are measured, breach response)
11. **Retention and legal hold design** (how records are retained and protected)
12. **Cosign-signed container image attestations**
13. **Signed release artifacts** (checksums, GPG signatures)

---

## 9. Pilot & Onboarding

### 9.1 Deployment

**Standard deployment (all tiers):**
- `docker compose up` in under 30 minutes
- Three services: `anonreq` (FastAPI), `presidio-analyzer` (NER), `valkey` (cache)
- `.env.example` configuration
- Health endpoint verification

**Enterprise deployment:**
- Kubernetes Helm chart (Phase 8+)
- Configuration via ConfigMaps and Secrets
- Horizontal pod autoscaling
- Prometheus operator integration

**Appliance deployment:**
- VM image or physical rack installation
- Network configuration (transparent proxy mode)
- CA certificate installation
- SIEM integration configuration

### 9.2 Guided Quickstart

The quickstart walks through:
1. Clone repository, configure `.env` with provider keys
2. `docker compose up` — observe all three services healthy
3. Send a test prompt containing synthetic PII through the API
4. Verify the response contains restored original values (not tokens)
5. Run the verification script to confirm no PII in logs
6. Test fail-secure by stopping the Presidio container

**Quickstart example payload:**
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $ANONREQ_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-AnonReq-Locale: en-US" \
  -d '{
    "model": "openai/gpt-4o",
    "messages": [
      {"role": "user", "content": "My email is john.doe@example.com and my phone is +1-555-123-4567"}
    ]
  }'
```

**Verification script (shell):**
```bash
# Check audit log for PII absence
docker compose logs anonreq | grep -E "john.doe|555-123-4567" && echo "FAIL: PII found in logs" || echo "PASS: No PII in logs"
# Check response contains restored values
curl output | grep -E "john.doe@example.com" && echo "PASS: Restoration works" || echo "FAIL: Tokens not restored"
# Check fail-secure
docker compose stop presidio
curl output | grep "500" && echo "PASS: Fail-secure works" || echo "FAIL: Request forwarded without detection"
```

### 9.3 Success Criteria for Pilot Exit

**Minimum:**
- Deployment complete, all services healthy
- Round-trip verification passes (inject PII, confirm restoration)
- No PII in audit logs (verification script passes)
- Streaming works with at least one provider
- Latency overhead measured and deemed acceptable

**Target:**
- Custom recognizers configured for enterprise-specific identifiers
- Compliance preset activated and audit log shows correct field
- Fail-secure tested and confirmed
- Integration with existing monitoring (Prometheus metrics scraped)

**Stretch:**
- Kubernetes deployment operational
- SSO integration configured (enterprise tier)
- Compliance evidence package generated

---

## 10. Competitive Positioning

### 10.1 AnonReq vs NodeShift

| Dimension | AnonReq | NodeShift |
|-----------|---------|-----------|
| Deployment | Self-hosted (your infrastructure) | SaaS (their infrastructure) |
| Data boundary | Raw data never leaves your perimeter | Data processed on their sovereign cloud |
| License | Apache 2.0 (open-source) | Proprietary |
| Cost | Free core, paid enterprise tier (per-tenant) | Paid (consumption + compute) |
| Streaming | Native SSE with Tail_Buffer | Limited |
| Providers | OpenAI, Anthropic, Gemini, Ollama, Azure | Their managed models (sovereign) |
| Audibility | Full source code, property-tested | Black-box |
| Latency | ~100ms overhead (P95) | Variable (depends on region routing) |

**When we win:**
- Customer has existing cloud infrastructure and just needs a gateway layer
- Customer requires full source code auditability
- Customer already uses multiple AI providers and doesn't want to change
- Customer needs air-gapped deployment (NodeShift requires their infra)

**When we lose:**
- Customer wants a fully managed service (no self-hosting)
- Customer needs sovereign compute (no on-prem capability) — NodeShift's moat
- Customer wants bundled managed model serving + security

**Battle card:** "NodeShift is a sovereign AI cloud. AnonReq is a self-hosted security gateway. If you need managed model hosting with built-in sovereignty, use NodeShift. If you already have infrastructure and just need to secure AI traffic, use AnonReq. They are complementary, not competitive."

### 10.2 AnonReq vs AI Security Gateway (AISG)

| Dimension | AnonReq | AISG |
|-----------|---------|------|
| Deployment | Self-hosted | SaaS (proxy) |
| Data processed by provider | No (pass-through after anonymization) | Yes (all data passes through their proxy) |
| Tokenization | Context-preserving `[TYPE_N]` | Strip or block only |
| SSE streaming | Full support | Limited |
| Open source | Yes (Apache 2.0) | No |
| Multi-provider | OpenAI, Anthropic, Gemini, Ollama | OpenAI, Anthropic, some others |
| Pricing | Free + tiered | Per-call pricing |

**When we win:**
- Customer has security/compliance prohibition on third-party data processing
- Customer needs tokenization (not just blocking) for LLM utility
- Customer wants open-source core for auditability

**When we lose:**
- Customer prefers SaaS for zero ops overhead
- Customer evaluates only on "setup simplicity" (AISG is simpler as SaaS)
- Customer has small scale and consumption pricing works better

**Battle card:** "AISG is a SaaS proxy — all your data passes through their infrastructure before reaching the LLM. That adds another third party to your data flow, which is problematic for GDPR Art. 28 and DORA supply chain risk. AnonReq is self-hosted: raw data never leaves your perimeter. You own the infrastructure. You audit the code. You verify the guarantees."

### 10.3 AnonReq vs Cloud-Native (AWS Bedrock Guardrails, Azure AI Content Safety)

| Dimension | AnonReq | Cloud-Native |
|-----------|---------|--------------|
| Cloud-agnostic | Yes (any infra) | No (locked to one cloud) |
| Self-hosted | Yes | No (managed service) |
| Multi-provider | All major providers | Only provider-specific |
| Tokenization | Context-preserving | Strip/block only |
| Compliance presets | 6 jurisdictions | Cloud-regional only |
| Open source | Yes | No |

**When we win:**
- Customer uses multiple clouds or cloud-agnostic strategy
- Customer needs multi-provider flexibility
- Customer has on-premise or hybrid infrastructure

**When we lose:**
- Customer is all-in on single cloud (e.g., fully committed to AWS)
- Customer only uses that cloud's AI services (Bedrock, Azure OpenAI)
- Customer has no multi-cloud or portability requirements

**Battle card:** "Cloud-native guardrails tie you to one provider and one AI service. AnonReq works across any cloud, any AI provider, any deployment topology. If you're committed to a single-cloud, single-provider strategy, cloud-native tools are simpler. If you want provider flexibility, portability, and open-source control, AnonReq is the foundation."

### 10.4 AnonReq vs In-House Builds

| Dimension | AnonReq | In-House |
|-----------|---------|----------|
| Time to deploy | 30 minutes | 6-12 months |
| Maintenance burden | Community + vendor | Internal team |
| Property tests | Yes (Hypothesis) | Rarely built |
| SSE streaming | Built-in | Custom work |
| Compliance presets | 6 built-in | Manual implementation |
| Locale support | 8 locales | Per-request effort |
| Cost | Free core, paid tiers | Engineering salary + infra |

**When we win:**
- Customer evaluated building with Presidio directly and realized scope
- Customer has limited ML/security engineering bandwidth
- Customer needs compliance-ready features (audit, presets, evidence)

**When we lose:**
- Customer has already built a solution
- Customer has unique requirements that generic gateway cannot serve
- Customer views "not invented here" as a requirement

**Battle card:** "We did the engineering so you don't have to. In-house builds using Presidio alone lack production streaming, fail-secure guarantees, property tests, compliance presets, and multi-provider adapters. Our 21-phase roadmap covers everything an enterprise needs. Your team can contribute to our open-source core instead of building from scratch."

### 10.5 Win/Loss Analysis

**Most common win scenarios:**
1. GDPR compliance audit uncovers employees using ChatGPT with customer PII → DPO mandates gateway
2. Enterprise procuring AI platform, security review flags "no control over data sent to LLMs"
3. Financial institution deploying LLM for trading desk — requires MNPI protection
4. Healthcare organization launching clinical AI assistant — needs HIPAA-compliant LLM access
5. Cloud migration to multi-provider strategy — needs consistent security layer

**Most common loss scenarios:**
1. Customer chooses fully managed service (NodeShift, Azure) for lower ops overhead
2. Customer builds in-house using Presidio (underestimates streaming/compliance complexity)
3. Customer already uses AISG and doesn't see value in self-hosted
4. Budget does not clear (competing priorities)
5. "Check the box" compliance — uses simpler DLP that doesn't really protect AI traffic

### 10.6 Sales Battle Cards (Summary)

| Competitor | One-liner | Proof Point |
|------------|-----------|-------------|
| NodeShift | "Complementary — they're a sovereign AI cloud, we're a self-hosted gateway." | "You can run AnonReq on NodeShift's infra for best of both worlds." |
| AISG | "SaaS proxy means your data goes through another third party." | "Our open-source core lets you verify no raw data leaves your perimeter." |
| Cloud-native | "Locks you into one cloud, one provider." | "AnonReq works with any of 4 providers across any cloud or on-prem." |
| In-house | "6 months of engineering to replicate what we already built and tested." | "30 minute deployment, property-tested correctness, 8 locales out of the box." |

---

## 11. Revenue Model

### 11.1 Revenue Streams

| Stream | Description | Margin | % of Revenue (Y1) |
|--------|-------------|--------|--------------------|
| Enterprise subscriptions | Per-tenant/month or flat annual | 80%+ | 65% |
| Appliance subscriptions | Enterprise + hardware/SI | 50-60% (hardware) | 20% |
| Professional services | Implementation, consulting, training | 70% | 15% |
| Open-source | Free — no direct revenue (adoption driver) | N/A | 0% |

### 11.2 Revenue Targets

**Year 1 (Build + Early Traction):**

| Metric | Conservative | Target | Stretch |
|--------|-------------|--------|---------|
| Enterprise subscriptions | 5 tenants | 10 tenants | 20 tenants |
| Enterprise ARR | $180,000 | $360,000 | $720,000 |
| Appliance deals | 0 | 1 | 3 |
| Appliance ARR | $0 | $75,000 | $300,000 |
| Professional services | $30,000 | $45,000 | $75,000 |
| **Total ARR** | **$210,000** | **$480,000** | **$1,095,000** |

**Year 2 (Growth):**

| Metric | Conservative | Target | Stretch |
|--------|-------------|--------|---------|
| Enterprise tenants | 15 | 30 | 50 |
| Enterprise ARR | $540,000 | $1,080,000 | $1,800,000 |
| Appliance deals | 2 | 5 | 10 |
| Appliance ARR | $150,000 | $375,000 | $750,000 |
| Professional services | $75,000 | $150,000 | $300,000 |
| **Total ARR** | **$765,000** | **$1,605,000** | **$2,850,000** |

**Year 3 (Scale):**

| Metric | Conservative | Target | Stretch |
|--------|-------------|--------|---------|
| Enterprise tenants | 50 | 100 | 200 |
| Enterprise ARR | $1,800,000 | $3,600,000 | $7,200,000 |
| Appliance deals | 10 | 20 | 40 |
| Appliance ARR | $750,000 | $1,500,000 | $3,000,000 |
| Professional services | $200,000 | $400,000 | $750,000 |
| **Total ARR** | **$2,750,000** | **$5,500,000** | **$10,950,000** |

### 11.3 Unit Economics

**Enterprise tier:**
- Average deal size: $36,000/year (3 tenants at $1,000/month/tenant)
- Average sales cycle: 90 days from first contact to close
- Customer acquisition cost (CAC): $25,000 (AE + SE time, marketing attribution)
- CAC payback: 8 months
- Net revenue retention (NRR): 120% (expansion: additional tenants, upgrade to appliance)
- Gross margin: 82% (infrastructure for enterprise delivery is minimal — most is support cost)

**Appliance tier:**
- Average deal size: $100,000/year (hardware + subscription)
- Sales cycle: 120 days (hardware procurement adds time)
- CAC: $40,000 (longer cycle, SE travel for on-site install)
- Gross margin: 55% (hardware cost is ~40%, support is ~5%)

### 11.4 Pricing Elasticity

- Annual prepay discount: 10% (reduces churn risk)
- Multi-year (2-3 year) commitment: 15-20% discount (improves predictability)
- Volume pricing: 10+ tenants: 15% off, 50+ tenants: 25% off
- Non-profit / academic: 50% discount (goodwill, referrals)
- Open-source to enterprise conversion: First year at 20% discount for named account

---

## 12. GTM Timeline

### 12.1 Pre-Launch (Months -6 to 0)

**Product:**
- Complete Stage 1 (Phases 1-7): MVP with core pipeline, streaming, multi-locale, documentation
- Production Readiness Review (Phase 6.5)
- Property-based test suite passing

**Community building:**
- Seed repository with 13-section README, architecture diagram
- Open-source LICENSE (Apache 2.0), NOTICE, SECURITY.md, CHANGELOG.md
- Publish to Hacker News ("Show HN: AnonReq — Open-Source AI Security Gateway")
- Discord server setup
- Initial blog posts on architecture decisions
- GitHub Discussions enabled for community Q&A

**Content:**
- Architecture deep-dive blog post
- "Why We Built an Open-Source AI Security Gateway" (announcement blog)
- Quickstart guides (EN, DE, FR, ES, PT-BR)
- SDK examples (curl, Python, TypeScript, Go)

**Sales prep:**
- Pricing page (transparent, no "contact sales")
- Enterprise trial sign-up flow
- Pilot playbook and checklist
- Sales deck and one-pager
- FAQ document for enterprise procurement

**Partnership:**
- Identify and recruit 2 MSP partners (guided by customer demand)
- AWS Marketplace listing preparation

### 12.2 Launch (Month 0)

**Press & community:**
- Hacker News launch post (timed for US morning Pacific)
- Product Hunt launch (with landing page)
- Tech press outreach (The Register, TechCrunch, SecurityWeek, CSO Online)
- Reddit posts: r/netsec, r/MachineLearning, r/selfhosted
- LinkedIn thought-leadership posts from founding team

**Product:**
- v1.0.0 release on GitHub
- Docker Hub images published
- GitHub Releases with signed artifacts and SBOM

**Outbound:**
- Targeted email outreach to 50 CISOs in financial services
- Partner webinars (with MSPs)
- 5 enterprise pilot commitments target

### 12.3 Post-Launch (Months 1-3)

**Pilot program:**
- 10 enterprise pilots (target 4 conversions)
- Weekly check-in with pilot participants
- Collect case study material, testimonials
- Iterate on product based on pilot feedback

**Community:**
- Respond to GitHub Issues and Discussions
- Publish community contributor guide
- First community-contributed recognizer bundles
- Office hours (bi-weekly)

**Content:**
- Case study #1 (pilot customer who deployed to production)
- Compliance mapping whitepaper (GDPR, DORA, NIS2)
- Latency benchmark results
- "How we property-tested streaming restoration" (engineering blog)

**Product iteration:**
- Bug fixes and performance improvements from pilot feedback
- Additional locale bundles (community contributions)
- Helm chart improvements

### 12.4 Scale (Months 4-12)

**Enterprise sales:**
- Assign named account execs for enterprise pipeline
- Target: 20 active enterprise deals in pipeline
- Close first appliance deal
- SI partnership (engage with 2 system integrators)

**Channel:**
- 4 MSP partners signed and enabled
- AWS Marketplace transactable listing
- Azure Marketplace listing

**Content:**
- Case study #2 and #3
- Featured in analyst report (Gartner, Forrester)
- Conference talks: KubeCon, RSA (if accepted)
- ROI calculator for enterprise deployment

**Product iteration:**
- Stage 2 features: Rate limiting, multimodal, AI firewall (Phases 8-16)
- Enterprise SSO/RBAC
- Compliance reports

**Community growth:**
- 2,500+ GitHub stars target
- 50+ community contributors
- First community-contributed provider adapter

### 12.5 Expansion (Year 2)

**New regions:**
- APAC expansion: Singapore office, targeted marketing
- LATAM expansion: Portuguese/Spanish content, Brazil-focused partnerships
- MENA expansion: Arabic content, UAE distributor

**Appliance tier:**
- Physical appliance manufacturing partner
- Air-gapped deployment beta with government customer
- Voice/meeting protection capability

**Compliance:**
- SOC 2 Type II certification
- ISO 27001 certification
- DORA conformity assessment package

**Product:**
- Stage 3 features: Universal gateway, transparent proxy, agent governance
- SIEM integrations: Splunk, Sentinel, QRadar, Elastic

**Revenue target:** $1.6M ARR

---

## 13. Success Metrics

### 13.1 Open-Source Community Metrics

| Metric | Y1 Target | Y2 Target | Y3 Target |
|--------|-----------|-----------|-----------|
| GitHub stars | 2,500 | 7,500 | 15,000 |
| GitHub forks | 500 | 1,500 | 3,000 |
| Unique contributors | 30 | 100 | 250 |
| Docker pulls/week | 500 | 2,000 | 5,000 |
| Discord/Slack members | 500 | 2,000 | 5,000 |
| Active community contributors (monthly) | 10 | 30 | 50 |
| Community-contributed recognizer bundles | 3 | 10 | 20 |
| Languages in quickstart translations | 5 | 8 | 12 |
| Third-party integrations built by community | 2 | 8 | 20 |

### 13.2 Pilot & Sales Metrics

| Metric | Y1 Target | Y2 Target |
|--------|-----------|-----------|
| Total pilots started | 20 | 50 |
| Pilot conversion rate | 40% | 50% |
| Average pilot-to-close (days) | 60 | 45 |
| Time-to-value (pilot deployment to first verified request) | 2 hours | 1 hour |
| Enterprise deals in pipeline (monthly average) | 10 | 25 |
| Sales cycle (first contact to closed-won) | 90 days | 75 days |
| Win rate (competitive deals) | 35% | 45% |

### 13.3 Revenue Metrics

| Metric | Y1 Target | Y2 Target | Y3 Target |
|--------|-----------|-----------|-----------|
| Annual Recurring Revenue (ARR) | $480,000 | $1,600,000 | $5,500,000 |
| Average Contract Value (ACV) | $36,000 | $55,000 | $75,000 |
| Customer Acquisition Cost (CAC) | $25,000 | $20,000 | $15,000 |
| CAC Payback Period | 8 months | 6 months | 4 months |
| Gross Margin (enterprise) | 82% | 85% | 87% |
| Net Revenue Retention (NRR) | 120% | 125% | 130% |
| Monthly Churn (enterprise) | < 2% | < 1% | < 0.5% |
| Monthly Churn (appliance) | < 1% | < 0.5% | < 0.3% |

### 13.4 Adoption Metrics

| Metric | Y1 Target | Y2 Target |
|--------|-----------|-----------|
| Active enterprise tenants (paid) | 10 | 30 |
| Active open-source deployments (estimated) | 200 | 1,000 |
| Total requests processed (monthly, paid tenants) | 50M | 500M |
| AI providers used through gateway | 4+ | 6+ |
| Avg tenant deployment size (employees) | 2,500 | 5,000 |
| Languages/locales detected across all tenants | 8 | 12 |
| Compliance presets activated | 6 | 10 |

### 13.5 Customer Health Metrics

| Metric | Target | Alert if |
|--------|--------|----------|
| NPS (enterprise customers) | > 40 | < 20 |
| Support ticket volume | < 20/month/tenant | > 50/month/tenant |
| Critical issue response time | < 1 hour | > 4 hours |
| On-time renewal rate | > 95% | < 85% |
| Referenceable customers | > 50% of paid base | < 25% |

### 13.6 Product Quality Metrics

| Metric | Target | Source |
|--------|--------|--------|
| Open-source issue response time (first response) | < 48 hours | GitHub |
| Open-source PR merge time | < 7 days | GitHub |
| CI/CD pipeline reliability | > 99% | Build system |
| Property-based test pass rate | 100% | CI pipeline |
| Latency overhead P95 | < 100ms (non-streaming) | /metrics |
| Streaming restoration accuracy | > 99.99% bytes matched | Property test suite |

### 13.7 Marketing Metrics

| Metric | Y1 Target |
|--------|-----------|
| Website visitors/month | 25,000 |
| Whitepaper downloads/month | 500 |
| Newsletter subscribers | 2,000 |
| Conference talks given | 6 |
| Analyst briefings | 5 |
| Case studies published | 3 |
| Blog posts published (engineering + product) | 30 |
| Social media followers (LinkedIn, X) | 5,000 |

---

## Appendix A: Competitive Landscape Matrix

| Feature | AnonReq | NodeShift | AISG | AWS Bedrock Guardrails | Azure AI Content Safety | In-House (Presidio) |
|---------|---------|-----------|------|------------------------|-------------------------|---------------------|
| Self-hosted | Yes | No | No | No | No | Yes |
| Open source | Yes (Apache 2.0) | No | No | No | No | Yes (Presidio) |
| PII Detection | Regex + NER | Unknown | Regex + NER | Content filters | Content filters | Regex + NER |
| Tokenization | Yes (`[TYPE_N]`) | No | Limited | No | No | Manual |
| Restoration | Yes (bidirectional) | N/A | No | N/A | N/A | Manual |
| SSE Streaming | Yes | Limited | Limited | N/A | N/A | No |
| Multi-provider | 4+ providers | Their models | 2-3 providers | AWS Bedrock only | Azure OpenAI only | Manual integration |
| Locales | 8 | Unknown | 3-4 | US only | Region-specific | Manual |
| Compliance presets | 6 | Unknown | 2 | None | None | Manual |
| Fail-secure | Yes (property-tested) | Unknown | Partial | Partial | Partial | Rare |
| Property tests | Yes (Hypothesis) | No | No | No | No | No |
| Audit logging | Metadata-only | Yes | Yes | CloudTrail | Monitor | Manual |
| Docker Compose | Yes | N/A | N/A | N/A | N/A | Yes |
| Kubernetes | Helm chart (Phase 8) | N/A | N/A | EKS only | AKS only | Manual |
| Transparent proxy | Appliance tier | No | No | No | No | No |
| AI firewall | Enterprise tier | Unknown | Limited | Guardrails | Safety filters | No |
| Voice protection | Appliance tier | No | No | No | No | No |

## Appendix B: Pricing Summary Card (Sales Tool)

```
ANONREQ PRICING (2026)

OPEN SOURCE CORE (Free)
  - Apache 2.0 | Forever free | No time limits
  - 8 locales | 4 providers | SSE streaming
  - Property-tested | Docker Compose
  - Community support (Discord + GitHub)

ENTERPRISE ($2,500-$15,000/tenant/month)
  Everything in Open Source, plus:
  - SSO/RBAC (OIDC, SAML, mTLS)
  - Policy engine (rate, spend, classification)
  - Compliance reports (GDPR, DORA, NIS2, HIPAA, SEC)
  - AI firewall (injection, jailbreak, output policy)
  - SBOM, attestation, supply chain
  - Governance framework (ISO 42001, EU AI Act)
  - 99.9% SLA | Priority support | Helm chart
  - Volume discounts: 10+ tenants (−15%), 50+ tenants (−25%)

APPLIANCE ($50,000-$200,000/year)
  Everything in Enterprise, plus:
  - Transparent proxy (TLS interception)
  - Voice/meeting AI protection
  - Agent governance (MCP protocol)
  - AI network discovery + CASB + RAG protection
  - SIEM integration (5 platforms)
  - Air-gapped mode | Physical hardware option
  - 1-hour SLA | Dedicated engineer

PROFESSIONAL SERVICES
  - Implementation: $25,000-$50,000
  - Custom recognizers: $5,000-$15,000
  - Compliance mapping: $10,000-$20,000
  - Training: $3,000-$5,000/session
```

## Appendix C: Sales Qualification Questions

**Discovery questions for CISO:**
1. "What AI services are your teams using today — sanctioned and unsanctioned?"
2. "Have you had any data exposure incidents related to AI usage?"
3. "How are you currently controlling what data goes to external LLMs?"
4. "What regulatory frameworks apply to your AI data flows?"
5. "What is your comfort level with self-hosted open-source security infrastructure?"

**Discovery questions for CIO/CTO:**
1. "What is your AI adoption timeline over the next 12 months?"
2. "How many AI providers are you using or evaluating?"
3. "Are you standardizing on a single AI platform or maintaining multi-provider flexibility?"
4. "What is your deployment infrastructure preference (cloud, on-prem, hybrid)?"
5. "Have you evaluated building an in-house solution?"

**Discovery questions for DPO/Compliance:**
1. "What is your current posture on employee use of external AI tools?"
2. "Have you completed a Data Protection Impact Assessment for AI usage?"
3. "Which regulatory frameworks are driving your AI governance requirements?"
4. "How would you demonstrate AI data protection to a regulator today?"
5. "What evidence would satisfy your auditors?"

## Appendix D: Launch Day Checklist

**Pre-launch (T-30 days):**
- [ ] v1.0.0 tagged, release artifacts published
- [ ] Docker images pushed to Docker Hub
- [ ] SBOM generated and attached to release
- [ ] NOTICE file finalized with all third-party dependencies
- [ ] SECURITY.md with disclosure contact and response SLA
- [ ] CHANGELOG.md with Keep a Changelog format
- [ ] README with all 13 sections
- [ ] Quickstart guides in 5 languages
- [ ] SDK examples (curl, Python, TypeScript, Go)
- [ ] Architecture diagram published
- [ ] OpenAPI spec published
- [ ] Pricing page live
- [ ] Enterprise trial sign-up flow tested
- [ ] Discord server set up
- [ ] Landing page / product website
- [ ] HN post drafted and reviewed

**Launch day:**
- [ ] HN post live (US morning PT)
- [ ] Product Hunt launch
- [ ] Social media announcements (LinkedIn, X, Mastodon)
- [ ] Tech press outreach emails sent
- [ ] Reddit posts (r/netsec, r/MachineLearning, r/selfhosted)
- [ ] Email outreach to 50 targeted CISO contacts
- [ ] Monitor GitHub Issues and Discord for launch feedback
- [ ] Launch webinar recording available

**Post-launch (T+7 days):**
- [ ] Launch metrics review (stars, pulls, visitors, sign-ups)
- [ ] First 5 pilot participants onboarded
- [ ] Blog post: "One Week In: AnonReq Launch Retrospective"
- [ ] Community Q&A on Discord
- [ ] Iterate on launch feedback (prioritize common issues)
- [ ] Begin case study documentation with first pilot customer

---

*Document version 1.0 | June 2026 | Prepared for AnonReq founding team*
*All pricing in USD. Subject to change. Contact sales@anonreq.ai for current pricing.*
