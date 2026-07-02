# AnonReq v5 — Go-To-Market Plan

**Version:** 1.0  
**Date:** 2026-07-02  
**Status:** Active

---

## Overview

AnonReq's go-to-market strategy runs four parallel motions:

1. **Direct Enterprise Sales** — Regulation-driven buyers (CISO, DPO, Chief Compliance Officer) in financial services, legal, and regulated enterprises. High ACV, long sales cycle, low volume.
2. **AnonReq Cloud (Managed SaaS)** — Fully hosted, usage-based subscription for mid-market companies and smaller firms that need compliance without infrastructure complexity. Fast close, monthly cashflow, feeds enterprise pipeline.
3. **Infrastructure Partner Embed** — NodeShift, AWS, GCP, Azure embed AnonReq as their built-in compliance layer. Low direct sales effort, high distribution leverage.
4. **Marketplace / Developer-Led** — Self-service via cloud marketplaces and open-source. Fast trial, low ACV, path to enterprise or SaaS upgrade.

Each motion feeds the others: SaaS signups generate warm enterprise leads; marketplace deployments validate product-market fit; enterprise customers justify infrastructure partnerships; infrastructure partners generate SaaS and marketplace deployments at scale.

---

## 1. Positioning

### 1.1 Core Positioning Statement

> **AnonReq is the universal data privacy and compliance infrastructure for enterprise AI.**
> Deploy on any platform. Enforce in real time. Comply with every jurisdiction.

### 1.2 Positioning by Audience

| Audience | Positioning | Key Message |
|----------|-------------|-------------|
| **CISO / Security team** | Inline AI data security | "Stop sensitive data from reaching external AI providers — without changing any application code." |
| **DPO / Chief Compliance Officer** | Multi-jurisdiction compliance automation | "Evidence-ready compliance for GDPR, EU AI Act, Saudi PDPL, PIPL — automatically collected, audit-ready." |
| **Infrastructure / Platform Engineering** | Deploy-anywhere appliance | "Runs anywhere you deploy AI: AWS, GCP, Azure, NodeShift, your laptop, your on-prem cluster." |
| **Legal / GC** | Attorney-client privilege + matter isolation | "The only solution that protects privileged communications and enforces matter-level data isolation before data reaches AI." |
| **Insurance Compliance** | Zero-tolerance compliance layer | "NAIC Model Law, Solvency II, Lloyd's standards — enforced at the infrastructure layer, not the application layer." |
| **NodeShift / Infrastructure Providers** | Embedded compliance differentiation | "Offer your customers compliant GPU compute without building a compliance product yourself." |

### 1.3 Differentiators

1. **Self-hosted / deploy-anywhere**: Customers own their data, no SaaS vendor trust required
2. **Transparent proxy**: Intercepts AI traffic without application code changes
3. **Fail-secure architecture**: Any error → block, never forward unsanitized data — verifiable by compliance officers
4. **Vanata**: Multi-jurisdiction compliance depth (EU + Middle East + Asia) + zero-tolerance verticals (insurance, legal)
5. **Infrastructure embed**: AnonReq integrates into cloud and GPU infrastructure as a first-class layer

---

## 2. Target Audience Segments

### Priority 1: Insurance Carriers & Reinsurers

**Why first**: Zero tolerance for non-compliance. Heavily regulated across multiple jurisdictions simultaneously. AI adoption accelerating (underwriting, claims, actuarial). High ACV. Strong word-of-mouth.

**Key Titles**: Chief Compliance Officer, CISO, VP Technology Risk, VP Data Governance, Chief Data Officer
**Key Regulators**: NAIC, EIOPA (EU), Lloyd's, state insurance departments
**Key Pain**: Cannot send actuarial data, claims data, or policyholder PII to external AI
**Entry Point**: Vanata Insurance Track (Phase 31)

**Named Target Accounts (Tier 1)**:
- Munich Re, Swiss Re, Lloyd's syndicates
- Allianz, AXA, Zurich Insurance (EU cross-jurisdiction)
- Chubb, Travelers, Hartford (US NAIC)
- Manulife, Sun Life (Canada → PIPEDA + state/provincial)

### Priority 2: Global Law Firms

**Why first**: Attorney-client privilege breach is existential. Firms have been told by bar associations to be "competent" with AI. High ACV. Partners drive decisions.

**Key Titles**: General Counsel, Chief Information Officer, Chief Information Security Officer, Knowledge Management Partner, Innovation Partner
**Key Regulators**: ABA, SRA (UK), CCBE (EU), local bar associations
**Key Pain**: Cannot send client matter data to external AI without privilege analysis
**Entry Point**: Vanata Legal Track (Phase 32)

**Named Target Accounts (Tier 1)**:
- Clifford Chance, Freshfields, Linklaters, Allen & Overy (Magic Circle, EU exposure)
- DLA Piper, Norton Rose (multi-jurisdiction)
- Latham & Watkins, Skadden, Sullivan & Cromwell (US heavy)

### Priority 3: Enterprise Banks & Asset Managers

**Why**: MRM requirements (SR 11-7), DORA, MNPI controls. Large IT budgets. Long sales cycles but high ACV.

**Key Titles**: CISO, Chief Data Officer, Head of AI Governance, Chief Compliance Officer
**Key Regulators**: Fed, OCC, FCA, ECB, FINRA, SEC
**Key Pain**: AI governance for model risk management; anonymization for MNPI in AI-assisted research
**Entry Point**: Enterprise Gateway → Financial Services compliance pack

### Priority 4: Infrastructure Providers (Strategic Partners)

**Why**: Distribution leverage. NodeShift specifically — clear gap in their offering (GPU compute without compliance layer).

**Target Partners**:
- **NodeShift** (GPU cloud): Immediate target — AnonReq sidecar on GPU nodes = "Compliant GPU Compute"
- **AWS** (Marketplace + Bedrock): AnonReq as AI compliance layer for Bedrock customers
- **GCP** (Marketplace + Vertex): Vertex AI compliance for regulated industries
- **Azure** (Marketplace + Azure OpenAI): Azure OpenAI governance for financial/healthcare

---

## 3. AnonReq Cloud — Managed SaaS Motion

### 3.1 Why This Motion Exists

The enterprise direct sales motion is high-value but slow. A 6–12 month sales cycle means revenue starts late, and the first 12–18 months of operation run on burn. AnonReq Cloud (managed SaaS) solves three things simultaneously:

1. **Cashflow**: Monthly recurring revenue from day one, no POC, no security review, no 8-week procurement
2. **Lead qualification**: SaaS users who hit limits or need Vanata become warm, pre-qualified enterprise leads — they already trust the product
3. **Market reach**: Smaller law firms, regional insurance brokers, mid-market companies have the same zero-tolerance compliance need as large enterprises but cannot run self-hosted infrastructure

**The trust paradox addressed**: AnonReq's core message is "deploy in your own infrastructure, trust no vendor." SaaS appears to contradict this. It doesn't — it targets a different customer:

- **Zero-tolerance, large enterprise** → self-hosted (Appliance, Vanata) — they demand it
- **Zero-tolerance, mid-market** → AnonReq Cloud — they need compliance but lack infra teams
- **Mid-market / startups** → AnonReq Cloud → free tier or low-cost subscription

The SaaS product must be architecturally transparent to earn trust: customer chooses data-center region, no raw data logging guarantee is enforced in architecture (not just policy), SOC 2 Type II is mandatory before GA.

---

### 3.2 AnonReq Cloud Tiers

| Tier | Monthly Price | Included | Target Customer |
|------|--------------|----------|-----------------|
| **Starter** | Free | 500K tokens/month, 1 tenant, GDPR preset only, community support | Developers, early evaluation |
| **Professional** | $299/month | 5M tokens/month, 3 tenants, all locale presets, email support | Startups, small teams |
| **Business** | $999/month | 25M tokens/month, 10 tenants, Vanata single-jurisdiction add-on available, SLA 99.9%, email + chat support | Mid-market (50–500 employees) |
| **Business+** | $2,499/month | 100M tokens/month, unlimited tenants, Vanata regional bundle, SSO, SLA 99.95%, priority support | Mid-market enterprise, regional firms |
| **Enterprise SaaS** | Custom ($5K–$20K/month) | Unlimited tokens, dedicated tenant infrastructure, Vanata vertical tracks, SLA 99.99%, dedicated CSM | Enterprise customers who prefer managed deployment over self-hosted |

**Vanata Add-Ons** (available on Business tier and above):

| Add-On | Monthly Price | Coverage |
|--------|--------------|---------|
| Vanata EU | +$200/month | GDPR, ePrivacy, NIS2, EU AI Act, DORA |
| Vanata Middle East | +$300/month | Saudi PDPL, UAE PDPL, DIFC, Qatar, Bahrain |
| Vanata Asia | +$300/month | PIPL, APPI, DPDP, PDPA (SG/TH), PIPA |
| Vanata Insurance Track | +$500/month | NAIC Model Law, Solvency II, Lloyd's |
| Vanata Legal Track | +$500/month | Privilege detection, matter isolation, bar association compliance |
| Vanata Full Bundle | +$1,200/month | All jurisdictions + both vertical tracks |

---

### 3.3 Target Customers for SaaS

**Primary SaaS Customers**:

| Segment | Profile | Monthly Spend | Entry Point |
|---------|---------|--------------|-------------|
| **Small / mid-size law firms** | 10–200 lawyers, using AI for contract review, research | $999–$2,499 + Vanata Legal Add-On | Legal Track add-on |
| **Regional insurance brokers** | 50–500 employees, regional NAIC exposure | $999–$2,499 + Vanata Insurance Add-On | Insurance Track add-on |
| **Mid-market startups** | 50–500 employees, GDPR/CCPA compliance needed | $299–$999 | Professional or Business tier |
| **Legal tech platforms** | SaaS products serving law firms, need compliance layer for their customers | $999–$5K (depending on resell volume) | Business+ or Enterprise SaaS |
| **InsurTech platforms** | SaaS products serving insurers, need compliance layer built in | $999–$5K | Business+ or Enterprise SaaS |

**Why mid-size law firms and regional insurance brokers are the SaaS sweet spot**:
- Same zero-tolerance compliance need as large enterprise customers
- No platform engineering team to run self-hosted infrastructure
- Budget exists (compliance spend is line-item justified)
- Sales cycle: 1–4 weeks (one decision-maker — the managing partner or compliance officer)
- High Vanata add-on attach rate → average revenue per customer $1,500–$3,000/month

---

### 3.4 SaaS Go-to-Market

**Acquisition Channels**:

| Channel | Tactic | Expected Conversion |
|---------|--------|-------------------|
| **Organic / SEO** | Blog posts targeting "GDPR AI compliance tool", "attorney-client privilege AI", "NAIC AI compliance" | 5% visit → trial |
| **Product Hunt / Hacker News** | Launch Starter tier free | Broad awareness, developer adoption |
| **LinkedIn Ads** | Target managing partners (law firms), compliance officers (regional insurers) | 2% click → trial |
| **Bar association & insurance association newsletters** | Sponsored content / advertising | 3% → trial |
| **Legal tech and insurtech directories** | G2, Capterra, legal tech vendor directories | 4% → paid |
| **Referral program** | Existing customers refer → 1 month free for referrer + referee | 15% of new signups |

**Conversion Funnel**:

```
Free Trial (Starter tier)
    ↓ (7-day onboarding sequence)
Professional ($299/month) — hit 500K token limit
    ↓ (usage-based upgrade prompt)
Business ($999/month) — needs multi-tenant or Vanata
    ↓ (Vanata add-on upsell)
Business + Vanata ($1,499–$2,499/month)
    ↓ (at 6 months of usage, sales-assisted)
Enterprise SaaS or Self-Hosted Enterprise ($5K–$20K/month)
```

**Onboarding Sequence** (automated, 7 days):
- Day 0: Welcome email + 5-minute quickstart video
- Day 1: "Route your first AI request through AnonReq" tutorial
- Day 3: "You've processed X requests — here's what was detected" usage email
- Day 5: "Add your second AI provider" feature spotlight
- Day 7: "Upgrade to Business for multi-tenant + Vanata" prompt (if near limit)

---

### 3.5 SaaS Architecture (Trust Model)

To earn trust from compliance-sensitive customers, AnonReq Cloud must be architecturally verifiable, not just policy-based:

**Data Residency**:
- Customer selects data-center region at signup: EU (Frankfurt), US (Virginia), UAE (Dubai), APAC (Singapore)
- Token mappings stored only in selected region
- Audit logs written to customer-controlled S3/GCS/Azure Blob (not AnonReq-owned storage)

**No Raw Data Logging**:
- Architecture enforces metadata-only audit logs (Session_ID, entity types, token counts — no raw values)
- Same fail-secure guarantee as self-hosted: any error → HTTP 500, nothing forwarded
- Customer can verify: open-source core, architecture documentation, SOC 2 Type II report

**Isolation**:
- Each paying customer: dedicated Valkey/Redis instance (no shared cache)
- Tenant token mappings never co-located with other customers' data

**Certifications required before GA**:
- SOC 2 Type II (mandatory)
- ISO 27001 (Year 2)
- GDPR DPA (Data Processing Agreement) with all customers
- EU-US Data Privacy Framework certification

---

### 3.6 SaaS Revenue Projection

**Assumptions**:
- Free tier launches with v1.0 GA (Q4 2026)
- Paid tiers convert at: 8% free → Professional, 20% Professional → Business
- Vanata add-on attach rate: 35% of Business+ customers
- Monthly churn: 3% (compliance tooling is sticky)

| Month | Free Users | Paid Customers | Avg MRR/Customer | Total MRR | ARR Run Rate |
|-------|-----------|---------------|-----------------|-----------|-------------|
| M3 (Q4 2026) | 200 | 30 | $400 | $12K | $144K |
| M6 (Q1 2027) | 500 | 75 | $500 | $37.5K | $450K |
| M9 (Q2 2027) | 1,000 | 150 | $650 | $97.5K | $1.17M |
| M12 (Q3 2027) | 2,000 | 280 | $800 | $224K | $2.69M |
| M18 (Q1 2028) | 4,000 | 550 | $950 | $522K | $6.27M |
| M24 (Q3 2028) | 7,000 | 950 | $1,100 | $1.04M | $12.5M |

**SaaS contributes ~25% of total ARR by end of 2027** — and more importantly, provides predictable monthly cashflow that bridges the gap between enterprise sales cycles.

---

## 4. Messaging Matrix

### 3.1 For Insurance / Legal (Vanata)

**Problem**: "Your AI assistant knows your client's policy limits. Your underwriting model has seen the claims data. Your chatbot has answered questions about your customer's health history. You have no proof of what left your perimeter — and neither do your regulators."

**Solution**: "AnonReq anonymizes sensitive data before it reaches any external AI, and Vanata automatically collects the compliance evidence your regulator will ask for. NAIC Model Law control mapping, evidence packages, breach workflows — generated automatically from your actual AI traffic."

**Proof Points**:
- 95%+ PII detection precision (validated by property-based testing)
- Fail-secure: any error → HTTP 500, nothing forwarded (verifiable)
- Jurisdiction-specific: Saudi PDPL, UAE PDPL, DIFC, Qatar PDPL — not just GDPR
- Audit-ready: regulator export packages, not spreadsheets

### 3.2 For Infrastructure Partners (NodeShift / Cloud Providers)

**Problem**: "Your GPU compute customers are running AI workloads. Some of those workloads process regulated data — medical records, legal documents, financial data. Your customers need compliance but you don't offer it. They go elsewhere, or they buy from a competitor who bundles compliance."

**Solution**: "Embed AnonReq as a sidecar on your compute nodes. Your customers get anonymization + audit built in. You offer 'Compliant GPU Compute' as a differentiated tier. We handle the compliance product. You handle the infrastructure."

**Proof Points**:
- < 5ms overhead in transparent proxy mode (P95)
- Zero application code changes required
- Works with vLLM, Ollama, and every major LLM provider
- Apache 2.0 core — no license conflict

---

## 5. Launch Plan

### Phase 1: Foundation (2026 Q3) — Private Beta

**Goal**: First 5 production deployments in insurance and legal verticals.

**Actions**:

| Action | Owner | Timeline |
|--------|-------|----------|
| Launch private beta program — hand-select 5–10 design partners | CEO / Sales | Immediately |
| Publish documentation site (docs.anonreq.io) | Engineering / Marketing | Week 2 |
| Build "Compliance Stack" landing page with GDPR, Saudi PDPL, PIPL, NAIC messaging | Marketing | Week 2 |
| LinkedIn content series: "Why AI compliance is broken" (5-part) | Marketing | Weeks 2–6 |
| Reach out to insurance CISO community (ISACA, ISSA chapters) | Sales | Week 3 |
| Conference presentations: IAPP Privacy Summit, InsureTech Connect | Marketing / CEO | Q3–Q4 2026 |
| Design partner case study: first production anonymization deployment | Marketing | Post-GA |

**KPIs**:
- 5 private beta customers
- 10M+ requests anonymized in beta
- 3 case studies (anonymized if needed)

### Phase 2: Market Entry (2026 Q4) — v1.0 GA

**Goal**: Public launch, AWS/GCP/Azure marketplace listings, 20 pipeline opportunities.

**Actions**:

| Action | Owner | Timeline |
|--------|-------|----------|
| v1.0 GA announcement (Product Hunt, Hacker News, LinkedIn) | Marketing / CEO | Week of v1.0 |
| AWS Marketplace listing — Enterprise Gateway | Engineering | Q4 2026 |
| GCP Marketplace listing — Enterprise Gateway | Engineering | Q4 2026 |
| Azure Marketplace listing — Enterprise Gateway | Engineering | Q4 2026 |
| NodeShift partnership announcement | CEO / Sales | Q4 2026 |
| RSA Conference abstract submission (for 2027) | Marketing | Q4 2026 |
| "AnonReq vs. SaaS AI privacy tools" comparison content | Marketing | Q4 2026 |
| SOC 2 Type I audit initiation | Compliance | Q4 2026 |

**KPIs**:
- 5+ AWS/GCP/Azure marketplace deployments
- 20+ enterprise pipeline opportunities
- 1 infrastructure partnership LOI (NodeShift)

### Phase 3: Scaling (2027 H1) — Appliance + Vanata Beta

**Goal**: Vanata modules in beta, infrastructure embed live with NodeShift, 12 paying enterprise customers.

**Actions**:

| Action | Owner | Timeline |
|--------|-------|----------|
| Vanata EU module beta — 3 design partners | Sales / Engineering | Q1 2027 |
| Vanata Middle East module beta | Sales / Engineering | Q2 2027 |
| NodeShift "Compliant GPU Compute" co-launch | Sales / NodeShift | Q1 2027 |
| AWS Marketplace listing — Appliance tier | Engineering | Q2 2027 |
| RSA Conference presentation (accepted) | Marketing / CEO | May 2027 |
| Insurance vertical campaign: "AI in insurance without the risk" | Marketing | Q1 2027 |
| Legal vertical campaign: "Privilege-safe AI for law firms" | Marketing | Q2 2027 |
| Customer advisory board (CAB) formation | CEO | Q1 2027 |

**KPIs**:
- 12 paying enterprise customers
- $5M ARR
- 1 infrastructure partnership live (NodeShift)
- Vanata EU: 3 design partners + first GA release

---

## 6. Content & Thought Leadership

### 5.1 Content Pillars

| Pillar | Target Audience | Content Types |
|--------|-----------------|---------------|
| **AI compliance explainer** | DPO, CCO, CISO | Blog posts, white papers, regulatory guides |
| **Multi-jurisdiction PII** | DPO, legal, data engineers | Technical posts, how-to guides, comparison tables |
| **Fail-secure architecture** | CISO, security architects | Architecture diagrams, threat model posts |
| **Vanata jurisdiction deep-dives** | Regional compliance officers | White papers, regulatory summaries |
| **Infrastructure integration** | Platform engineers, DevOps | Tutorial posts, GitHub samples, Helm chart guides |

### 5.2 Signature Content Pieces

1. **"The State of AI Compliance in Financial Services 2027"** — Annual industry report (positions AnonReq as thought leader)
2. **"GDPR vs. Saudi PDPL vs. PIPL: What's Different for AI"** — Technical white paper (drives multi-region inbound)
3. **"Attorney-Client Privilege and AI: A Guide for Law Firms"** — Legal vertical entry (positions Vanata Legal Track)
4. **"Building Compliant GPU Infrastructure with NodeShift + AnonReq"** — Infrastructure partner story
5. **"Fail-Secure AI: How to Pass Your AI Governance Audit"** — CISO/CCO audience

### 5.3 Events & Conferences

| Event | Region | Audience | Priority |
|-------|--------|----------|----------|
| IAPP Privacy Summit | US / EU | DPO, privacy professionals | Tier 1 |
| RSA Conference | US | CISO, security | Tier 1 |
| InsureTech Connect | US | Insurance CTO/CIO | Tier 1 |
| Gartner Security Summit | US / EU | CISO, buyers | Tier 1 |
| GITEX Global | UAE / ME | Middle East enterprise | Tier 1 |
| Legal Innovation & Technology Summit | US / UK | Legal innovation | Tier 2 |
| Cloud Expo Europe | EU | Cloud/infrastructure | Tier 2 |
| AWS re:Invent | US | Cloud engineers, enterprise | Tier 2 |
| NodeShift / GPU cloud events | Global | Infrastructure | Tier 2 |
| Japan IT Week | Japan | Asia enterprise | Tier 3 |

---

## 7. Partner Strategy

### 6.1 NodeShift Partnership (Immediate Priority)

**Goal**: AnonReq embedded as the compliance layer in NodeShift's GPU infrastructure offering.

**What AnonReq Brings**:
- Compliance and anonymization layer for GPU workloads
- Vanata audit automation for regulated customers
- Transparent proxy mode — no application changes required

**What NodeShift Brings**:
- GPU compute infrastructure
- Customer base of AI workload operators
- Distribution channel into regulated verticals

**Partnership Structure**:
1. **Technical Integration** (Phase 27 in roadmap): AnonReq sidecar on NodeShift GPU nodes
2. **Co-marketing**: "Compliant GPU Compute" tier — joint solution brief, customer case studies
3. **Revenue Share**: NodeShift charges premium for "Compliant" tier → 25% to AnonReq
4. **Go-to-Market**: NodeShift sales teams refer compliance-sensitive customers to AnonReq

**Target Launch**: Q1 2027 alongside Phase 27 completion

### 6.2 Cloud Marketplace Strategy

**Goal**: Presence on all major marketplaces = discoverability + procurement vehicle for enterprises with cloud commitments (EDP, MACC, etc.)

| Marketplace | Tier 1 Listing | Tier 2 Listing | Revenue |
|-------------|----------------|----------------|---------|
| **AWS Marketplace** | Enterprise Gateway | Appliance | Cloud spend commitment draw-down |
| **GCP Marketplace** | Enterprise Gateway | Appliance | Cloud spend commitment draw-down |
| **Azure Marketplace** | Enterprise Gateway | Appliance | Azure MACC draw-down |

**Key Benefit**: Enterprise customers with $X million cloud commitments can pay for AnonReq through their existing cloud spend → removes procurement friction.

### 6.3 Channel Partners

| Partner Type | Example Partners | Role | Priority |
|-------------|------------------|------|----------|
| **Compliance consulting** | Deloitte, PwC, KPMG, EY (risk & regulatory practices) | Recommend AnonReq in AI governance engagements | Tier 1 |
| **Legal tech consultants** | Consilio, FTI Technology, Epiq | Recommend Vanata Legal Track | Tier 1 |
| **System integrators** | Accenture, Capgemini, Cognizant | Deploy AnonReq in large enterprise programs | Tier 2 |
| **Insurance tech consultants** | Majesco, Guidewire partners | Recommend Vanata Insurance Track | Tier 2 |
| **Security VARs** | CDW, SHI, Optiv | Distribute Enterprise Gateway in SMB/mid-market | Tier 3 |

---

## 8. Sales Enablement

### 7.1 Sales Motion by Segment

#### Insurance / Legal (Vanata Vertical Tracks)

| Stage | Activity | Tool |
|-------|----------|------|
| **Prospecting** | CISO/CCO outreach via LinkedIn, conference networking | Sales engagement platform |
| **Discovery** | AI compliance assessment (1-hour discovery call) | Discovery question bank |
| **Qualification** | Regulatory exposure matrix — map customer jurisdictions to Vanata modules | Qualification scorecard |
| **Demo** | Live demo: anonymize insurance claim in real time, generate NAIC evidence package | Demo environment |
| **POC** | 30-day POC: customer traffic through AnonReq, anonymization + audit report at end | POC playbook |
| **Proposal** | Solution brief tailored to jurisdictions + vertical | Pricing calculator |
| **Close** | Security review support, legal review support, procurement | Security documentation package |

#### Infrastructure Partners (NodeShift / Cloud Providers)

| Stage | Activity | Tool |
|-------|----------|------|
| **Outreach** | CEO/VP Engineering contact at target infrastructure providers | Direct outreach, warm intros |
| **Discovery** | "Compliant compute" opportunity sizing — how many regulated customers? | Business case template |
| **Technical POC** | Joint engineering: AnonReq sidecar on NodeShift GPU node | Integration guide |
| **Business Case** | Revenue share model, co-marketing plan, go-to-market timeline | Business case model |
| **Partnership Agreement** | OEM license, revenue share, co-marketing terms | Partnership agreement template |

### 7.2 Sales Collateral

| Piece | Audience | Purpose |
|-------|----------|---------|
| **1-page solution brief** (per vertical) | Executive / first meeting | Establish context, get next meeting |
| **Architecture white paper** | CISO / Security architects | Technical credibility |
| **Vanata jurisdiction guide** (per region) | DPO / CCO | Compliance depth demonstration |
| **ROI calculator** | CFO / procurement | Quantify compliance cost avoidance |
| **POC report template** | Post-POC | Convert POC to purchase order |
| **Security documentation package** | Infosec review teams | Accelerate security review stage |

---

## 9. Metrics & KPIs

### 8.1 Marketing Metrics

| Metric | Q4 2026 | Q2 2027 | Q4 2027 |
|--------|---------|---------|---------|
| Website visits/month | 5,000 | 15,000 | 35,000 |
| Inbound leads/month | 20 | 60 | 150 |
| MQL/month | 10 | 30 | 75 |
| Content pieces published | 15 | 40 | 80 |
| Marketplace deployments | 10 | 75 | 250 |

### 8.2 Sales Metrics

| Metric | Q4 2026 | Q2 2027 | Q4 2027 |
|--------|---------|---------|---------|
| Pipeline value | $5M | $20M | $50M |
| Deals in POC | 3 | 8 | 15 |
| Closed-won | 5 | 12 | 20 |
| Average ACV | $200K | $250K | $300K |
| Win rate | 30% | 35% | 40% |
| Sales cycle (avg days) | 270 | 240 | 210 |

### 8.3 Partnership Metrics

| Metric | Q4 2026 | Q2 2027 | Q4 2027 |
|--------|---------|---------|---------|
| Infrastructure partnerships signed | 0 | 1 (NodeShift) | 2 |
| Channel partner agreements | 0 | 3 | 8 |
| Marketplace listings live | 3 | 6 | 9 |
| Partner-sourced revenue (%) | 0% | 15% | 25% |

---

## 10. Budget Allocation

**Annual GTM Budget (2027): $3M**

| Category | Budget | % | Rationale |
|----------|--------|---|-----------|
| **Direct sales team** (4 AEs + 2 SEs) | $1.2M | 40% | Primary revenue driver |
| **Events & conferences** | $450K | 15% | IAPP, RSA, InsureTech, GITEX |
| **Content & thought leadership** | $300K | 10% | Blog, white papers, analyst relations |
| **Digital marketing & paid** | $300K | 10% | SEO, LinkedIn, targeted ads |
| **Partner marketing** | $300K | 10% | Co-marketing with NodeShift, cloud providers |
| **Customer success** | $300K | 10% | Onboarding, adoption, retention |
| **Tools & infrastructure** | $150K | 5% | CRM, sales engagement, analytics |

---

## 11. NodeShift Specific Strategy

### 10.1 Why NodeShift First

NodeShift sits at the intersection of two powerful trends:
- **GPU compute democratization**: NodeShift makes bare metal GPU accessible to anyone
- **Enterprise AI compliance gap**: Enterprises want GPU compute for AI but cannot run regulated workloads without a compliance layer

NodeShift's current offering is **compute without compliance**. AnonReq fills that gap, turning NodeShift into "Compliant GPU Compute" — a differentiated offering that enterprise customers in regulated industries actually want.

### 10.2 Integration Architecture

```
[Enterprise Application]
         ↓
[AnonReq Sidecar — deployed alongside NodeShift GPU node]
  - Transparent proxy: intercepts AI traffic
  - Anonymizes sensitive data
  - Forwards sanitized prompts to NodeShift-hosted model (vLLM, Ollama, etc.)
  - Restores tokens in response
  - Audit events → customer SIEM
         ↓
[NodeShift GPU Node — runs vLLM, Ollama, or any model]
```

**Integration Options**:
1. **Sidecar container**: AnonReq runs as a sidecar in the same pod/VM as the model server
2. **Network appliance**: AnonReq deployed inline in front of NodeShift API endpoint
3. **NodeShift API integration**: Provision AnonReq automatically when NodeShift GPU node is provisioned

### 10.3 Business Case for NodeShift

**Revenue Opportunity** (for NodeShift):
- Regulated industries (financial, healthcare, legal) cannot use bare GPU without compliance layer
- AnonReq unlocks these customers for NodeShift
- "Compliant GPU Compute" tier: +$500–$2K/month premium per customer
- At 200 compliant customers: +$1.2M–$4.8M/year revenue for NodeShift
- AnonReq takes 25%: $300K–$1.2M/year

**Differentiation for NodeShift**:
- "Only GPU cloud provider with built-in AI compliance" — defensible positioning
- Enterprise procurement teams need compliance evidence → NodeShift can provide it
- Aligns with NodeShift's enterprise market push

---

## 12. Regional GTM

### 11.1 EU / Europe

**Entry Point**: Vanata EU module (Phase 28) — GDPR + NIS2 + EU AI Act + DORA
**Key Markets**: Germany, France, Netherlands, UK (post-Brexit compliance parity)
**Key Events**: Cloud Expo Europe, IAPP Europe, FS-ISAC EMEA
**Key Partners**: EU-based compliance consultancies, EU legal tech platforms
**Key Messages**: "EU AI Act readiness — risk classification + prohibited use detection, built into your infrastructure"

### 11.2 Middle East

**Entry Point**: Vanata Middle East module (Phase 29) — Saudi PDPL, UAE PDPL, DIFC
**Key Markets**: UAE (Dubai / Abu Dhabi / DIFC / ADGM), Saudi Arabia, Qatar
**Key Events**: GITEX Global (Dubai), IDEX, Saudi tech weeks
**Key Partnerships**: UAE DIFC-based fintech compliance consultancies, Saudi digital transformation advisors
**Key Messages**: "Saudi PDPL and UAE PDPL compliance for AI — the same gateway that protects your data for GDPR protects it for SDAIA"
**Why Middle East matters**: High enforcement activity, severe penalties, rapid enterprise AI adoption, strong demand for compliant infrastructure

### 11.3 Asia-Pacific

**Entry Point**: Vanata Asia module (Phase 30) — PIPL (China), APPI (Japan), DPDP (India)
**Key Markets**: Singapore (hub for SEA), Japan, India, Australia
**Key Events**: Gartner IT Symposium APAC, Japan IT Week, Singapore FinTech Festival
**Key Partners**: Singapore-based compliance firms (APAC jurisdiction expertise), India tech consulting (DPDP readiness)
**Key Messages**: "One infrastructure layer, eight jurisdictions — PIPL, APPI, DPDP, PDPA, PIPA, Privacy Act, all from one deployment"
