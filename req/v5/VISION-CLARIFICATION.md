# AnonReq v5 — Vision Clarification

**Version:** 1.0  
**Date:** 2026-07-02  
**Author:** Product Leadership  
**Status:** Active

---

## What You Asked For (Clarified)

You want AnonReq to evolve from a self-hosted gateway into **universal infrastructure** that:

1. **Deploys everywhere** — not just as SaaS, but as:
   - Native OS packages (macOS `.pkg`, Windows `.msi`, Linux `.deb`/`.rpm`)
   - Cloud marketplace appliances (AWS, GCP, Azure one-click deploy)
   - Container/K8s (Docker, Helm, operators)
   - **Embedded in other infrastructure** (NodeShift, AWS, GCP, Azure as built-in feature)

2. **Works like NodeShift** — meaning:
   - **NodeShift provides GPU infrastructure**; AnonReq provides **compliance infrastructure**
   - AnonReq can deploy **alongside** NodeShift (sidecar on GPU nodes)
   - AnonReq can **integrate into** NodeShift's offering (NodeShift sells "Compliant GPU Compute" with AnonReq built-in)
   - Same model applies to AWS, GCP, Azure: they can **embed** AnonReq as their compliance layer

3. **Vanata is the compliance engine** — not a separate product, but a module that makes AnonReq valuable for:
   - Insurance carriers (NAIC, Solvency II, Lloyd's — zero tolerance for non-compliance)
   - Law firms (attorney-client privilege, matter isolation, bar association rules)
   - Multi-jurisdiction enterprises (EU + Middle East + Asia in one deployment)

4. **The "everywhere" strategy** — AnonReq becomes infrastructure like:
   - Load balancers (deployed in every cloud, every data center)
   - API gateways (Kong, Envoy, Istio — run anywhere)
   - TLS termination (nginx, HAProxy — universal)
   - **AnonReq = the compliance layer for AI, deployed everywhere**

---

## What This Means Strategically

### Strategy 1: Infrastructure, Not SaaS

**Old Model** (most competitors):
- "Trust us, send your data to our API, we'll anonymize it"
- Enterprise objection: "Now I have to trust another SaaS vendor with my data"

**AnonReq Model**:
- "Deploy AnonReq in your infrastructure (AWS, on-prem, laptop, NodeShift GPU node)"
- "It intercepts AI traffic before it leaves your perimeter"
- "You control the infrastructure, you own the data, you verify the behavior"
- **No trust required — it's infrastructure you deploy**

### Strategy 2: NodeShift as Distribution Partner

**Why NodeShift First**:
- NodeShift provides **GPU compute** but lacks **compliance story**
- Regulated industries (financial, legal, healthcare) need GPU for AI but cannot use it without compliance controls
- AnonReq + NodeShift = "Compliant GPU Compute" — differentiated offering

**Partnership Structure**:
1. **Technical Integration**: AnonReq sidecar deploys alongside NodeShift GPU nodes
2. **Go-to-Market**: NodeShift offers "Compliant" tier with AnonReq built-in
3. **Revenue Share**: NodeShift charges +$500–$2K/month per compliant node → 25% to AnonReq
4. **Win-Win**:
   - NodeShift: unlocks regulated verticals, differentiation in crowded GPU market
   - AnonReq: distribution at scale (1000s of deployments), embedded in infrastructure

**Same Model for AWS/GCP/Azure**:
- AWS Bedrock customers need compliance layer → embed AnonReq
- GCP Vertex AI customers need compliance layer → embed AnonReq
- Azure OpenAI customers need compliance layer → embed AnonReq
- **Infrastructure providers become distribution partners, not competitors**

### Strategy 3: Vanata = The Compliance Moat

**Why Vanata Matters**:
- Generic compliance automation (Vanta, Drata) covers IT controls but lacks:
  - AI-specific controls (prompt security, agent governance, anonymization)
  - Data privacy enforcement (not just policy documents, but inline blocking)
  - Jurisdiction depth (8 Middle East regimes, 8 Asia regimes — not just GDPR)
- **Vanata combines enforcement (anonymization, blocking) + evidence (audit logs, control mappings)**

**Zero-Tolerance Verticals**:
- **Insurance**: NAIC Model Law violation → business suspension in that state
- **Legal**: Attorney-client privilege breach → malpractice, disbarment, client lawsuits
- These verticals **must comply** — not "should comply" — making them high-willingness-to-pay customers

**Differentiation**:
- Vanta: "Here's a checklist and a dashboard"
- AnonReq/Vanata: "Here's enforcement at the infrastructure layer + the evidence your regulator will ask for"

---

## How This Is Different from v4

| Aspect | v4 | v5 |
|--------|----|----|
| **Deployment** | Self-hosted gateway (Docker, manual install) | Native appliances (marketplace, OS packages, transparent proxy) |
| **Distribution** | Direct sales only | Direct sales + infrastructure embed (NodeShift, AWS, GCP, Azure) |
| **NodeShift** | Mentioned as gap in analysis | First-class integration + partnership |
| **Compliance** | GDPR, LGPD, PDPA, POPIA presets | Vanata: EU (5 frameworks) + Middle East (8 jurisdictions) + Asia (8 jurisdictions) |
| **Verticals** | Generic enterprise | Insurance + Legal as dedicated zero-tolerance tracks |
| **Transparent Proxy** | Planned | Core deployment mode (no app code changes) |
| **Packaging** | Docker only | Docker + Helm + .deb + .rpm + .pkg + .msi + marketplace AMIs |

---

## Visual Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Enterprise Applications                   │
│             (CRM, HR systems, custom apps, agents)              │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       │ (all AI traffic)
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│                       AnonReq Appliance                         │
│                   (transparent proxy mode)                      │
│                                                                 │
│  ┌───────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ Detection     │  │ Tokenization │  │ Policy Enforcement │  │
│  │ Engine        │→ │ Engine       │→ │ (AI Firewall)      │  │
│  └───────────────┘  └──────────────┘  └────────────────────┘  │
│                                                                 │
│  ┌───────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ Vanata        │  │ Audit Logger │  │ Restoration Engine │  │
│  │ (Compliance)  │  │              │  │                    │  │
│  └───────────────┘  └──────────────┘  └────────────────────┘  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       │ (anonymized traffic)
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│              Infrastructure / AI Providers                      │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌─────────┐  ┌────────────────┐  │
│  │ OpenAI   │  │ Anthropic│  │ Gemini  │  │ AWS Bedrock    │  │
│  └──────────┘  └──────────┘  └─────────┘  └────────────────┘  │
│                                                                 │
│  ┌──────────────────────┐  ┌─────────────────────────────────┐│
│  │ GCP Vertex AI        │  │ Azure OpenAI                    ││
│  └──────────────────────┘  └─────────────────────────────────┘│
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ NodeShift (vLLM, Ollama on GPU nodes)                    │ │
│  └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

              AnonReq sits BETWEEN apps and AI providers
           Can deploy: on-prem, AWS, GCP, Azure, NodeShift,
                    laptop, data center, edge, hybrid
```

---

## Deployment Scenarios

### Scenario 1: Enterprise Self-Hosted (AWS)

```
Customer deploys AnonReq on their AWS account:
1. One-click from AWS Marketplace
2. AnonReq deployed as EC2 instance behind GWLB (Gateway Load Balancer)
3. VPC egress traffic → GWLB → AnonReq → inspected/anonymized → internet
4. Applications send AI traffic as normal (no code changes)
5. AnonReq intercepts, anonymizes, forwards to OpenAI/Anthropic/Bedrock
6. Vanata generates compliance evidence → customer SIEM
```

### Scenario 2: NodeShift Embedded (GPU Compliance)

```
NodeShift customer provisions GPU node with "Compliant" tier:
1. NodeShift provisions GPU node + AnonReq sidecar (automatically)
2. Customer's AI workload runs on GPU node
3. All AI traffic → AnonReq sidecar → anonymized → model endpoint (vLLM)
4. AnonReq audit events → NodeShift dashboard + customer SIEM
5. Customer gets compliance + GPU in one bundle
6. NodeShift charges premium, shares revenue with AnonReq
```

### Scenario 3: Developer Laptop (macOS)

```
Developer installs AnonReq on laptop:
1. Download .pkg from anonreq.io → install
2. AnonReq runs as launchd service, transparent proxy on localhost
3. Developer's scripts call OpenAI API as normal
4. AnonReq intercepts, anonymizes sample data, forwards
5. Developer can test AI features without sending real customer data
6. Free tier (up to 1M tokens/month)
```

### Scenario 4: Law Firm (Vanata Legal Track)

```
Global law firm deploys AnonReq with Vanata Legal Track:
1. Deploy AnonReq on-prem (Helm chart on K8s)
2. Configure matter-level isolation (tenant-within-tenant per client matter)
3. Applications (contract review, legal research) route through AnonReq
4. AnonReq detects privileged communications → blocks AI processing
5. Non-privileged data → anonymized → forwarded to OpenAI
6. Vanata generates bar association compliance evidence (ABA, SRA, CCBE)
7. eDiscovery integration: legal hold workflow, production packages
```

---

## Business Model Summary

### Revenue Streams

| Stream | Description | Annual Revenue Potential (2027) |
|--------|-------------|-------------------------------|
| **Enterprise Direct Sales** | Banks, insurance, law firms buy AnonReq + Vanata | $8M |
| **Infrastructure Embed** | NodeShift, AWS, GCP, Azure embed AnonReq (revenue share) | $2M |
| **Marketplace Self-Service** | Mid-market + startups deploy from marketplace | $500K |
| **Total** | | **$10.5M ARR** |

### Pricing

| Product | Pricing | Buyer |
|---------|---------|-------|
| **Open Core Gateway** | Free (Apache 2.0) + paid support ($10K–$50K/year) | Developers, startups |
| **Enterprise Gateway** | $50K–$250K/year | Mid-market enterprises |
| **Appliance** | $100K–$500K/year | Regulated enterprises |
| **Vanata (per jurisdiction bundle)** | $75K–$250K/year | Global enterprises |
| **Vanata (vertical track)** | $150K–$750K/year | Insurance, legal |
| **Infrastructure Embed** | 20–30% revenue share | NodeShift, AWS, GCP, Azure |

---

## Why This Works

### 1. **Market Timing**
- AI adoption accelerating in regulated industries
- Regulators publishing AI-specific guidance (EU AI Act, DORA, NAIC Model Law updates)
- Enterprises blocked by compliance → need infrastructure solution, not SaaS promise

### 2. **Differentiation**
- Only solution combining: deploy-anywhere + AI-native enforcement + multi-jurisdiction depth
- Fail-secure architecture verifiable by compliance officers (not "trust us")
- Zero-tolerance verticals (insurance, legal) validate product depth

### 3. **Distribution Leverage**
- Infrastructure embed strategy: NodeShift, AWS, GCP, Azure distribute AnonReq at scale
- Marketplace presence: AWS/GCP/Azure marketplaces = discoverability + procurement vehicle
- Direct sales: high ACV from insurance, legal, financial services

### 4. **Defensibility**
- **Vanata moat**: Multi-jurisdiction control mappings + vertical depth (insurance, legal) = years of regulatory expertise
- **Infrastructure positioning**: SaaS competitors cannot match deploy-anywhere flexibility
- **Open core strategy**: Apache 2.0 core = community adoption, proprietary Vanata/Appliance = revenue

---

## Success Metrics (2027)

- **$10.5M ARR**
- **20 enterprise customers**
- **1–2 infrastructure partnerships live** (NodeShift + 1 cloud provider)
- **250+ marketplace deployments**
- **2K GitHub stars** (open core community)
- **3 signature research reports published** (thought leadership)

---

## What Makes This Different

**Not**: "Yet another SaaS AI security tool"
**But**: "Universal compliance infrastructure for enterprise AI — deploy anywhere, enforce everywhere, comply with every jurisdiction"

**Not**: "Competing with NodeShift or AWS"
**But**: "Complementing NodeShift and AWS — we provide the compliance layer they don't have"

**Not**: "Generic GRC like Vanta"
**But**: "AI-specific enforcement + multi-jurisdiction evidence automation — especially for zero-tolerance verticals"

---

## Next Steps

1. ✅ Vision clarified and documented
2. ✅ Business plan created
3. ✅ GTM strategy created
4. ✅ Marketing plan created
5. ✅ Sales pipeline defined
6. ✅ Requirements summarized (90+ requirements across 11 phases)
7. **TODO**: Expand REQUIREMENTS.md with full acceptance criteria
8. **TODO**: Create phase-specific planning documents
9. **TODO**: Design NodeShift partnership agreement
10. **TODO**: Initiate AWS/GCP/Azure marketplace listing processes

---

## Conclusion

AnonReq v5 is not an incremental feature release — it's a strategic repositioning from **gateway** to **infrastructure**. By deploying everywhere, integrating with infrastructure providers (NodeShift, AWS, GCP, Azure), and providing jurisdiction-specific compliance depth (Vanata), AnonReq becomes the **universal compliance layer for enterprise AI**.

The market is ready. The differentiation is clear. The timing is right.

**Let's build it.**
