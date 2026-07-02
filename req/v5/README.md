# AnonReq v5 — Strategic Planning Documents

**Version:** 1.0  
**Date:** 2026-07-02  
**Status:** Active

---

## Overview

This folder (`req/v5/`) contains all strategic planning documents for AnonReq v5 — the evolution from self-hosted gateway to universal compliance infrastructure.

**What v5 Changes**:
- **Deployment**: From Docker-only to native appliances (OS packages, marketplace listings, transparent proxy)
- **Distribution**: From direct sales to infrastructure embed (NodeShift, AWS, GCP, Azure partnerships)
- **Compliance**: From basic presets to Vanata (multi-jurisdiction: EU + Middle East + Asia)
- **Verticals**: From generic enterprise to zero-tolerance tracks (insurance, legal)

---

## Document Index

### Core Strategy Documents

| Document | Purpose | Key Audiences |
|----------|---------|---------------|
| **[VISION-CLARIFICATION.md](./VISION-CLARIFICATION.md)** | Clarifies the strategic vision: AnonReq as universal infrastructure, NodeShift partnership model, Vanata as compliance moat | CEO, Board, Leadership Team |
| **[VISION.md](./VISION.md)** | High-level product vision: two pillars (Universal Appliance + Vanata), v4 → v5 evolution | Product Team, Engineering, Leadership |
| **[BUSINESS-PLAN.md](./BUSINESS-PLAN.md)** | Comprehensive business plan: market analysis, competitive landscape, product strategy, revenue model, organizational plan, funding requirements | CEO, Board, Investors, Leadership |
| **[GTM.md](./GTM.md)** | Go-to-market strategy: positioning, target segments, launch plan, content strategy, partnerships (NodeShift, AWS, GCP, Azure), sales enablement | Sales, Marketing, Partnerships |
| **[MARKETING-PLAN.md](./MARKETING-PLAN.md)** | Marketing strategy: content pillars, campaigns, demand generation, metrics, budget | Marketing, CEO, Leadership |
| **[SALES-PIPELINE.md](./SALES-PIPELINE.md)** | Sales pipeline definition: stages, qualification, plays (outreach, demo, POC), metrics, compensation | Sales, Sales Ops, Leadership |

### Technical Planning Documents

| Document | Purpose | Key Audiences |
|----------|---------|---------------|
| **[ROADMAP.md](./ROADMAP.md)** | Phase-by-phase roadmap: Stage 4 (Appliance), Stage 5 (Infrastructure), Stage 6 (Vanata Core), Stage 7 (Verticals) | Engineering, Product, Leadership |
| **[REQUIREMENTS-SUMMARY.md](./REQUIREMENTS-SUMMARY.md)** | High-level summary of all 90+ requirements across phases 22–32, organized by stage | Engineering, Product, QA |
| **[REQUIREMENTS.md](./REQUIREMENTS.md)** | Full requirements document with detailed acceptance criteria for all phases (in progress — currently Phase 22 started) | Engineering, Product, QA |
| **[GAP-ANALYSIS.md](./GAP-ANALYSIS.md)** | Competitive gap analysis: NodeShift and Vanta comparisons, feature gaps, recommended actions | Product, Leadership, Engineering |

---

## How to Use These Documents

### For Leadership / Board

**Start with**:
1. [VISION-CLARIFICATION.md](./VISION-CLARIFICATION.md) — understand the strategic shift
2. [BUSINESS-PLAN.md](./BUSINESS-PLAN.md) — market opportunity, revenue model, funding needs

### For Sales / Marketing

**Start with**:
1. [GTM.md](./GTM.md) — go-to-market strategy, target segments, partnerships
2. [MARKETING-PLAN.md](./MARKETING-PLAN.md) — content strategy, campaigns, metrics
3. [SALES-PIPELINE.md](./SALES-PIPELINE.md) — sales process, plays, compensation

### For Engineering / Product

**Start with**:
1. [ROADMAP.md](./ROADMAP.md) — phase-by-phase technical plan
2. [REQUIREMENTS-SUMMARY.md](./REQUIREMENTS-SUMMARY.md) — high-level requirements overview
3. [REQUIREMENTS.md](./REQUIREMENTS.md) — detailed acceptance criteria (in progress)
4. [GAP-ANALYSIS.md](./GAP-ANALYSIS.md) — competitive gaps to address

### For Partnerships (NodeShift, AWS, GCP, Azure)

**Start with**:
1. [VISION-CLARIFICATION.md](./VISION-CLARIFICATION.md) — infrastructure embed strategy
2. [GTM.md](./GTM.md) — partnership structure, co-marketing, revenue share
3. [ROADMAP.md](./ROADMAP.md) — Phase 27 (NodeShift), Phase 25–26 (AWS/GCP/Azure)

---

## Key Strategic Insights

### 1. Infrastructure, Not SaaS

AnonReq deploys in customer infrastructure (AWS, GCP, Azure, NodeShift, on-prem, laptop) — not as a SaaS endpoint. This eliminates the "trust another vendor" objection and positions AnonReq as **infrastructure** like load balancers or API gateways.

### 2. NodeShift as First Infrastructure Partner

NodeShift provides GPU compute without a compliance story. AnonReq fills that gap, enabling NodeShift to offer "Compliant GPU Compute" to regulated industries (financial, legal, healthcare). Revenue share model: NodeShift charges premium, splits with AnonReq. Distribution at scale without direct sales effort.

### 3. Vanata as Compliance Moat

Vanata combines:
- **Enforcement**: Inline anonymization + blocking (not just policy documents)
- **Evidence**: Automated compliance evidence collection per jurisdiction
- **Depth**: 8 Middle East regimes + 8 Asia regimes + 5 EU frameworks — not just GDPR

Zero-tolerance verticals (insurance, legal) provide high willingness-to-pay and validate product depth.

### 4. Three Parallel GTM Motions

1. **Direct Enterprise Sales**: High ACV ($100K–$750K), long cycle (6–12 months), insurance/legal/financial
2. **Infrastructure Embed**: NodeShift, AWS, GCP, Azure partnerships, revenue share, distribution leverage
3. **Marketplace Self-Service**: AWS/GCP/Azure marketplaces, developer-led growth, fast trial

Each motion feeds the others: marketplace → enterprise leads; enterprise → infrastructure validation; infrastructure → marketplace deployments.

---

## Revenue Model

**2027 Target: $10.5M ARR**

| Revenue Stream | Contribution |
|---------------|-------------|
| Enterprise direct sales (20 customers × $100K–$500K) | $8M |
| Infrastructure embed (NodeShift + 1 cloud provider) | $2M |
| Marketplace self-service (250 deployments × $5K–$50K) | $500K |

---

## Phases at a Glance

### Stage 4: Appliance Foundation (Phases 22–24)
- **Goal**: Deploy-anywhere packaging
- **Deliverables**: Docker, Helm, .deb, .rpm, .pkg, .msi, marketplace listings, transparent proxy

### Stage 5: Infrastructure Integrations (Phases 25–27)
- **Goal**: Deep cloud + GPU integrations
- **Deliverables**: AWS GWLB/Bedrock/Security Hub, GCP Cloud Armor/Vertex, Azure App Gateway/Azure OpenAI, NodeShift sidecar/vLLM/Ollama

### Stage 6: Vanata Core (Phases 28–30)
- **Goal**: Multi-jurisdiction compliance automation
- **Deliverables**: EU module (GDPR, NIS2, EU AI Act, DORA), Middle East module (8 jurisdictions), Asia module (8 jurisdictions)

### Stage 7: Vertical Tracks (Phases 31–32)
- **Goal**: Zero-tolerance compliance for insurance and legal
- **Deliverables**: Insurance track (NAIC, Solvency II, Lloyd's), Legal track (privilege, matter isolation, bar associations, eDiscovery)

---

## Success Metrics (2027)

| Metric | Target |
|--------|--------|
| **ARR** | $10.5M |
| **Enterprise customers** | 20 |
| **Infrastructure partnerships** | 2 (NodeShift + 1 cloud) |
| **Marketplace deployments** | 250+ |
| **GitHub stars** | 2,000 |
| **Signature research reports** | 3 |
| **Press mentions (tier-1)** | 10 |

---

## Next Actions

### Immediate (Week 1–2)

1. **Review & approval**: Leadership reviews all strategic documents
2. **NodeShift outreach**: Initiate partnership conversation (CEO → NodeShift CEO/VP Product)
3. **Funding preparation**: Prepare Series A deck using business plan
4. **Engineering kickoff**: Phase 22 (Appliance Packaging) planning begins

### Short-Term (Month 1–2)

1. **Expand REQUIREMENTS.md**: Complete acceptance criteria for all phases
2. **Phase planning**: Create detailed phase plans in `.planning/phases/22-32/`
3. **Marketing content**: Start "State of AI Compliance 2027" research report
4. **Sales enablement**: Build discovery question bank, demo environment, POC playbook

### Medium-Term (Month 3–6)

1. **Phase 22 execution**: Ship first native packages (Docker, Helm, .deb, .rpm)
2. **NodeShift partnership**: Finalize agreement, begin technical integration
3. **Marketplace listings**: Initiate AWS/GCP/Azure marketplace listing processes
4. **First enterprise customers**: Close 3–5 design partners

---

## Questions / Feedback

For questions about these documents or feedback on the v5 strategy:

- **Product Strategy**: [Product Leadership]
- **Technical Feasibility**: [Engineering Leadership]
- **Go-to-Market**: [Sales/Marketing Leadership]
- **Partnerships**: [CEO / VP Partnerships]

---

## Document History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-07-02 | 1.0 | Initial v5 strategic planning documents created | Product Team |

---

## Related Documents

- **Core Requirements**: `req/requirements.md` (Req 1–21)
- **Enterprise Requirements**: `req/requirements_v2.md` (Req 22–56, v4 scope)
- **Gap Analysis**: `req/v5/GAP-ANALYSIS.md` (NodeShift, Vanta competitive analysis)
- **v4 Planning**: `.planning/phases/01-21/` (Stages 1–3 execution)

---

**AnonReq v5: Universal compliance infrastructure for enterprise AI. Deploy anywhere. Enforce everywhere. Comply with every jurisdiction.**
