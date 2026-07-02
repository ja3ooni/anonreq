# AnonReq v5 — Sales Pipeline & Process

**Version:** 1.0  
**Date:** 2026-07-02  
**Status:** Active

---

## 1. Executive Summary

AnonReq's sales model combines **enterprise direct sales** (high ACV, long cycle) with **infrastructure partnership** distribution and **marketplace self-service**. This document defines the sales pipeline stages, qualification criteria, sales plays, and metrics for each motion.

**Pipeline Goals (2027)**:
- $50M total pipeline value
- 20 closed-won enterprise customers
- 1–2 infrastructure partnerships live
- 250+ marketplace deployments

---

## 2. Sales Motions

### Motion 1: Enterprise Direct Sales

**Target**: Financial services, legal, regulated enterprises with 500+ employees
**ACV**: $100K–$750K
**Sales Cycle**: 6–12 months
**Team**: Account Executives (AEs) + Sales Engineers (SEs)

**Buyer Committee**:
- Economic buyer: CISO, Chief Compliance Officer, VP Legal
- Technical buyer: VP Engineering, Security Architect, Platform Engineering Lead
- Influencers: DPO, GC, procurement
- Champion: Internal advocate (often CISO or DPO)

### Motion 2: Infrastructure Partner Embed

**Target**: NodeShift, AWS, GCP, Azure, CoreWeave, Lambda Labs
**Structure**: Revenue share or OEM licensing
**Sales Cycle**: 12–24 months (partnership development)
**Team**: CEO, VP Sales, VP Engineering

**Decision Makers**:
- VP Product, VP Engineering, Chief Revenue Officer

### Motion 3: Marketplace Self-Service

**Target**: Mid-market, startups, individual developers
**ACV**: $5K–$50K
**Sales Cycle**: Self-service → sales-assisted upgrade
**Team**: Inside sales reps (ISRs) for upgrade conversations

---

## 3. Sales Pipeline Stages

### Stage 0: Target Account Identification

**Definition**: Account identified as ICP (Ideal Customer Profile), no contact yet

**Exit Criteria**:
- Account matches ICP (regulated industry, 500+ employees, AI usage confirmed)
- Contact information found for at least one decision-maker

**Activities**:
- Research company AI usage (job postings, conference attendance, press)
- Identify tech stack (LinkedIn, BuiltWith, job ads)
- Map org chart (LinkedIn Sales Navigator)

**Metrics**:
- Target account list: 200 accounts

### Stage 1: Outreach / Initial Contact

**Definition**: First outbound contact made (email, LinkedIn, conference meeting)

**Exit Criteria**:
- Response from prospect (email reply, LinkedIn acceptance, meeting booked)
- OR 5 touchpoints completed with no response → mark "unresponsive"

**Activities**:
- Cold email (personalized, reference recent AI initiative or compliance event)
- LinkedIn connection request + DM
- Conference booth conversation / meeting
- Warm intro via investor, advisor, or customer

**Metrics**:
- Response rate: 15% target
- Meetings booked: 10/month target (across 4 AEs)

**Sales Play**: See "Enterprise Outreach Play" below

### Stage 2: Discovery / Qualification

**Definition**: First discovery call scheduled

**Exit Criteria**:
- BANT qualified (Budget, Authority, Need, Timeline)
- Pain confirmed (compliance gap, data exfiltration risk, multi-jurisdiction complexity)
- Use case defined (anonymization, agent governance, compliance audit, etc.)
- OR disqualified (no budget, no authority, no timeline, no pain)

**Activities**:
- 60-minute discovery call (AE + SE if technical)
- AI compliance assessment: map current AI usage, data handling, compliance requirements
- Identify jurisdictions in scope (GDPR, PIPL, Saudi PDPL, etc.)
- Understand buyer committee, procurement process, decision timeline

**Discovery Questions**:
1. "Which AI tools and models are you using today? (OpenAI, Anthropic, AWS Bedrock, etc.)"
2. "What types of data are being sent to these AI providers? (customer data, legal documents, financial data, PHI, etc.)"
3. "Which data privacy regulations apply to your organization? (GDPR, PIPL, HIPAA, etc.)"
4. "Who owns AI compliance in your organization? (CISO, DPO, Chief Compliance Officer, etc.)"
5. "What's your current approach to anonymizing data before AI? (manual redaction, no anonymization, SaaS tool, etc.)"
6. "What would a compliance failure cost you? (regulatory fine, business suspension, reputational damage)"
7. "What's your timeline for solving this? (active RFP, exploring solutions, future need)"
8. "What's your budget for AI compliance tools? ($50K–$100K, $100K–$250K, $250K+, not defined)"

**Qualification Criteria (BANT)**:
- **Budget**: $100K+ identified for AI compliance / data privacy / AI governance
- **Authority**: Access to economic buyer (CISO, CCO, VP Legal)
- **Need**: Confirmed pain (compliance audit coming, regulator inquiry, shadow AI usage, data exfiltration risk)
- **Timeline**: Decision within 6 months

**Metrics**:
- Qualification rate: 50% of discovery calls → qualified
- Disqualification reasons tracked (no budget, no authority, no pain, no timeline)

**Sales Play**: See "Discovery & Qualification Play" below

### Stage 3: Technical Demo

**Definition**: Product demo delivered to technical stakeholders

**Exit Criteria**:
- Demo delivered to security architect, platform engineer, or data engineer
- Technical questions answered
- Technical objections surfaced and addressed
- Next step: POC scope discussion OR objection that cannot be addressed → disqualify

**Activities**:
- 60-minute demo (SE-led, AE attends)
- Demo script tailored to use case (anonymization, agent governance, compliance audit, etc.)
- Live anonymization: paste sample data → show anonymization → show restoration
- Show fail-secure behavior: kill detection engine → show HTTP 500, not forwarded data
- Walk through Vanata module (if multi-jurisdiction in scope)
- Q&A: architecture, deployment, integration, performance

**Demo Script**:
1. **Setup** (5 min): "Today I'll show you how AnonReq intercepts AI traffic, anonymizes sensitive data in real time, and generates compliance evidence automatically."
2. **Anonymization** (15 min): Live demo — paste insurance claim with PII → anonymize → forward to OpenAI → restore in response
3. **Fail-secure** (10 min): Simulate detection engine failure → show request blocked, HTTP 500 returned
4. **Vanata compliance** (15 min): Generate NAIC Model Law evidence package from audit log
5. **Deployment** (10 min): Show Helm chart, Terraform module, marketplace listings
6. **Q&A** (15 min)

**Technical Objections & Responses**:
| Objection | Response |
|-----------|----------|
| "We can build this ourselves" | "True — if you have 18 months and 6 engineers. But you also need multi-jurisdiction expertise, property-based testing, fail-secure architecture, and ongoing regulatory updates. We've solved the hard parts." |
| "Performance overhead is too high" | "P95 overhead is <100ms for anonymization, <5ms for policy-only enforcement. We'll run a POC on your actual traffic to prove it." |
| "What if your detection misses PII?" | "We use hybrid regex + NER with Presidio. We'll tune detection thresholds in POC. And fail-secure means any ambiguity → block, not forward." |
| "We use Azure OpenAI, not OpenAI directly" | "We support Azure OpenAI, AWS Bedrock, GCP Vertex AI, and Anthropic. Provider adapters translate across formats." |
| "We need on-prem, not cloud" | "AnonReq deploys anywhere: on-prem, cloud, hybrid. Docker, Helm, native packages (.deb, .rpm, .pkg, .msi). You own the infrastructure." |

**Metrics**:
- Demo-to-POC rate: 60% target

**Sales Play**: See "Technical Demo Play" below

### Stage 4: POC / Pilot

**Definition**: Proof-of-concept agreed, SOW signed, POC environment live

**Exit Criteria**:
- POC success criteria met (defined in SOW)
- Security review initiated
- Business case presented to economic buyer
- OR POC fails → understand why, determine if recoverable

**POC Structure**:
- **Duration**: 30 days
- **Scope**: Anonymize traffic from 1–2 applications, process 10K–100K requests
- **Success Criteria**:
  1. 95%+ PII detection precision (manually reviewed sample)
  2. Round-trip correctness: anonymize → restore → no data loss
  3. Fail-secure behavior: any error → block, nothing forwarded
  4. Performance: P95 latency overhead ≤ 100ms
  5. Compliance evidence: generate audit report at end of POC
- **Deliverables**:
  - POC report: metrics, findings, recommendations
  - Security documentation: architecture, threat model, data flow
  - Pricing proposal

**POC Playbook**:
1. **Week 1**: Deploy AnonReq in customer environment (AWS, GCP, Azure, on-prem), configure provider adapters
2. **Week 2**: Route traffic from pilot application through AnonReq, tune detection thresholds
3. **Week 3**: Collect metrics (requests/day, latency, detection precision), address issues
4. **Week 4**: Generate POC report, present findings to economic buyer + technical buyer

**Common POC Blockers & Solutions**:
| Blocker | Solution |
|---------|----------|
| Customer security review delays POC start | Provide security documentation package upfront, offer to present to infosec team before POC |
| Detection precision below target | Tune confidence thresholds, add custom entity types, expand exclusion list |
| Performance overhead too high | Optimize detection pipeline, use smaller NER models, cache entity recognizers |
| Integration complexity | Provide SE support, create custom deployment scripts |

**Metrics**:
- POC success rate: 70% target (of POCs started, % that convert to proposal)

**Sales Play**: See "POC Execution Play" below

### Stage 5: Security Review

**Definition**: Customer infosec team reviewing AnonReq architecture, code, and deployment

**Exit Criteria**:
- Security review complete, findings addressed
- Infosec team approves AnonReq for production deployment
- OR security objection cannot be resolved → deal lost

**Activities**:
- Provide security documentation package:
  - Architecture diagrams (network, data flow, trust boundaries)
  - Threat model (STRIDE analysis)
  - Open-source core license (Apache 2.0)
  - Property-based testing report (Hypothesis test results)
  - Penetration test report (if available)
  - SOC 2 Type II report (when available)
- Answer security questionnaire
- Present to infosec team (1-hour call)
- Address findings (code review requests, architecture questions, deployment concerns)

**Common Security Objections & Responses**:
| Objection | Response |
|-----------|----------|
| "Cache stores sensitive data — what if Redis is breached?" | "Mappings are ephemeral (TTL 60–3600s), deleted post-response. No persistence (AOF/RDB disabled). Encryption at rest via Redis TLS + KMS integration optional." |
| "Detection engine is third-party (Presidio) — supply chain risk" | "Presidio is from Microsoft, Apache 2.0, widely adopted. We vendor dependencies, run property-based tests on every release." |
| "What if anonymization fails but request is forwarded?" | "Fail-secure architecture: any error → HTTP 500, request blocked. Verified by property-based tests." |
| "Logs could leak PII" | "Audit logs are metadata-only: Session_ID, entity types detected, token count. No raw values. Field allowlist enforced." |

**Metrics**:
- Security review time: 4–6 weeks median
- Security approval rate: 90% target (of reviews started, % that approve)

### Stage 6: Proposal / Business Case

**Definition**: Pricing proposal and business case presented to economic buyer

**Exit Criteria**:
- Proposal accepted, OR negotiation begins, OR deal lost

**Activities**:
- Present pricing proposal:
  - License tier (Enterprise Gateway, Appliance, Vanata modules)
  - Annual contract value (ACV)
  - Deployment scope (# of environments, # of tenants, expected request volume)
- Present business case:
  - Compliance cost avoidance: audit prep time saved, regulatory fine risk reduction
  - Operational efficiency: faster AI adoption, no per-app anonymization code
  - ROI: payback period, 3-year TCO
- Negotiate: pricing, terms, support SLA, professional services

**ROI Calculation Template**:

**Costs**:
- AnonReq license: $200K/year (example)
- Deployment & integration: $50K (one-time)
- Training: $10K (one-time)

**Benefits** (annual):
- Compliance audit prep time saved: 500 hours × $150/hour = $75K
- Regulatory fine risk reduction: (probability × fine amount) = (5% × $5M) = $250K expected value
- Developer time saved: no per-app anonymization code = 200 hours × $100/hour = $20K
- Faster AI adoption: revenue impact (estimate) = $500K

**Total annual benefit**: $845K
**Payback period**: 3.6 months
**3-year NPV**: $2.1M

**Metrics**:
- Proposal-to-close rate: 50% target

### Stage 7: Procurement / Legal Review

**Definition**: Deal approved by economic buyer, in procurement & legal review

**Exit Criteria**:
- Contract signed, PO received
- OR deal lost in procurement (budget reallocated, legal objection, etc.)

**Activities**:
- Contract negotiation: terms, liability caps, indemnification, data processing addendum (DPA)
- Procurement process: vendor onboarding, security attestation, financial review
- Legal review: terms, data privacy clauses, subprocessor list, jurisdictional compliance

**Common Procurement Blockers & Solutions**:
| Blocker | Solution |
|---------|----------|
| Budget freeze / reallocation | Escalate to economic buyer, tie to compliance deadline (audit, regulator inquiry) |
| Legal objects to liability cap | Offer higher liability cap for higher price, or provide insurance certificate |
| Procurement requires SOC 2 | Provide SOC 2 Type I (initiate Type II for renewal), offer to escrow code |
| Multi-jurisdiction DPA negotiation | Provide standard DPA with jurisdiction-specific addenda (GDPR, PIPL, etc.) |

**Metrics**:
- Procurement time: 4–8 weeks median
- Procurement close rate: 80% target (of deals in procurement, % that close)

### Stage 8: Closed-Won

**Definition**: Contract signed, PO received, deal marked closed-won

**Activities**:
- Hand off to Customer Success for onboarding
- Celebrate 🎉
- Request case study / testimonial (after 90 days of production usage)

**Metrics**:
- Win rate: (closed-won / total opportunities) = 35% target
- Average deal size: $250K ACV target

### Stage 9: Closed-Lost

**Definition**: Deal lost, reason documented

**Activities**:
- Document loss reason: no budget, competitor, build in-house, no decision, security objection, etc.
- Conduct loss analysis: interview champion or economic buyer if possible
- Add to nurture campaign: re-engage in 6 months

**Metrics**:
- Loss reason distribution tracked
- Top loss reasons addressed in product roadmap or sales enablement

---

## 4. Sales Plays

### Play 1: Enterprise Outreach (Stage 1)

**Goal**: Book discovery meeting

**Ideal Customer Profile (ICP)**:
- **Industry**: Financial services (banks, insurance, asset managers), legal (law firms, legal tech), healthcare, government
- **Size**: 500+ employees, $100M+ revenue
- **AI Usage**: Using OpenAI, Anthropic, AWS Bedrock, Azure OpenAI, or GCP Vertex AI
- **Compliance Exposure**: Multi-jurisdiction (GDPR + PIPL, GDPR + Saudi PDPL, etc.), OR zero-tolerance vertical (insurance, legal)
- **Signals**: Recent AI initiative announced, CISO or DPO active on LinkedIn discussing AI, compliance audit mentioned in earnings call

**Outreach Sequence**:

**Email 1** (Day 1):
Subject: [Company] AI + [Jurisdiction] compliance?

Hi [First Name],

I saw [Company] recently [announced AI initiative / posted AI engineering roles / etc.]. 

Quick question: how are you handling [GDPR / PIPL / Saudi PDPL] compliance for data sent to OpenAI / Anthropic / etc.?

Most enterprises we talk to are either:
1. Manually redacting data (slow, error-prone)
2. Trusting the LLM provider (risky for regulated industries)
3. Blocking AI usage entirely (shadow AI problem)

We built AnonReq to solve this: anonymize sensitive data before it reaches any external AI, generate compliance evidence automatically. Deploys in your infrastructure (AWS, GCP, Azure, on-prem).

Worth a 20-minute call to see if it's relevant?

[Signature]

**LinkedIn Connection** (Day 3):
Connection request with note: "Saw your work on [AI initiative]. We help [industry] companies handle AI compliance — would love to connect."

**Email 2** (Day 7, if no response):
Subject: Re: [Company] AI + [Jurisdiction] compliance?

Hi [First Name],

Following up on my note below.

We're working with [peer company in same industry] to anonymize [data type] before it reaches external AI. Thought it might be relevant for [Company].

Happy to send over a quick overview if helpful — or if AI compliance isn't a priority right now, no worries.

[Signature]

**LinkedIn DM** (Day 10, if connected but no response):
"Hi [First Name] — following up on my email about AI compliance. If now isn't the right time, totally understand. If it is, happy to share how [peer company] is handling [jurisdiction] compliance for AI. Let me know!"

**Email 3** (Day 14, if no response):
Subject: Last note on [Company] AI compliance

Hi [First Name],

Last note from me — don't want to be a pest.

If AI compliance (especially [jurisdiction]) is on your radar in the next 6 months, happy to share what we're seeing from [industry] companies.

If not, I'll check back in Q [next quarter].

[Signature]

**Breakup Email** (Day 21, if no response):
Subject: Closing the loop

Hi [First Name],

Haven't heard back, so I'll assume now isn't the right time.

If anything changes — or if [jurisdiction] compliance becomes urgent — feel free to reach out. We'll be here.

Best,
[Signature]

**Metrics**:
- 5 touchpoints over 21 days
- Response rate: 15% target
- Meeting rate: 10% of sequences → discovery meeting

### Play 2: Discovery & Qualification (Stage 2)

**Goal**: Qualify opportunity, identify pain, map buyer committee

**Pre-Call Prep**:
- Research company: AI usage, tech stack, recent compliance events
- Review LinkedIn: map org chart, identify decision-makers
- Prepare questions (see Stage 2 above)

**Call Structure** (60 minutes):

**1. Intro** (5 min):
"Thanks for taking the time. I'll give you a 2-minute overview of AnonReq, then I'd love to hear about your AI usage and compliance needs — and we can see if there's a fit."

**2. AnonReq Overview** (3 min):
"AnonReq is a self-hosted anonymization gateway for AI. It sits between your applications and any AI provider, detects sensitive data, replaces it with placeholder tokens, forwards the sanitized request, and restores tokens in the response. All in your infrastructure — no SaaS vendor trust required. We also have Vanata, a compliance automation module for multi-jurisdiction evidence collection."

**3. Discovery** (40 min):
Ask discovery questions (see Stage 2 above). Listen for pain signals:
- "We can't use AI because of compliance risk"
- "Our DPO won't approve AI usage without controls"
- "We're about to get audited and we don't have AI controls documented"
- "We have shadow AI usage and no visibility"
- "We operate in multiple jurisdictions and compliance is a mess"

**4. Qualification** (10 min):
- Budget: "What's your budget for AI compliance tools this year?"
- Authority: "Who ultimately approves a purchase like this? CISO? Chief Compliance Officer?"
- Need: "On a scale of 1-10, how urgent is solving this?"
- Timeline: "What's your timeline for making a decision?"

**5. Next Steps** (2 min):
- If qualified: "I'd love to show you a demo. Can we get your security architect or platform engineer on the call too?"
- If not qualified: "Sounds like now isn't the right time. Can I check back in [timeframe]?"

**Post-Call**:
- Send follow-up email: recap pain, confirm next steps, attach relevant collateral
- Update CRM: BANT qualification, pain points, buyer committee, next steps

**Metrics**:
- 50% of discovery calls → qualified opportunity

### Play 3: Technical Demo (Stage 3)

**Goal**: Demonstrate product capabilities, address technical objections, move to POC discussion

**Pre-Demo Prep**:
- Tailor demo to use case: anonymization, agent governance, compliance audit, etc.
- Prepare demo data: insurance claim, legal document, financial data, etc. (match their industry)
- Test demo environment: ensure it works
- Review technical objections from AE notes

**Demo Script** (see Stage 3 above for full script)

**Post-Demo**:
- Send follow-up email: demo recording, architecture white paper, POC proposal
- Schedule POC scoping call if interest confirmed

**Metrics**:
- 60% of demos → POC

### Play 4: POC Execution (Stage 4)

**Goal**: Prove product value, meet POC success criteria, convert to proposal

**POC Kickoff**:
- POC kickoff call: review success criteria, deployment plan, timeline, escalation path
- Deploy AnonReq in customer environment (SE-led, AE supports)
- Route traffic from pilot application

**Weekly Check-Ins**:
- Week 1: Deployment complete, traffic flowing
- Week 2: Detection tuning, latency optimization
- Week 3: Metrics collection, issue resolution
- Week 4: POC report, business case presentation

**POC Report Template**:
1. **Executive Summary**: POC goals, results, recommendation
2. **Metrics**: requests processed, PII detected, latency, precision, recall
3. **Findings**: what worked, what didn't, tuning required
4. **Recommendation**: proceed to purchase, expand scope, or end POC
5. **Appendix**: detailed logs, configuration, architecture

**Post-POC**:
- Present POC report to economic buyer + technical buyer
- If successful: move to proposal stage
- If unsuccessful: understand why, determine if recoverable

**Metrics**:
- 70% of POCs → proposal

---

## 5. Pipeline Metrics & Goals

### 5.1 Pipeline Coverage

**Pipeline Coverage Formula**: (Total Pipeline Value) / (Quarterly Quota) = X:1 coverage

**Target**: 4:1 coverage (for every $1 in quota, have $4 in pipeline)

**Example** (Q1 2027):
- Quarterly quota: $2.5M (across 4 AEs = $10M annual quota)
- Required pipeline: $10M
- Average ACV: $250K
- Required opportunities: 40 opportunities in pipeline

### 5.2 Conversion Rates by Stage

| Stage | Target Conversion to Next Stage | Average Days in Stage |
|-------|--------------------------------|---------------------|
| Stage 1: Outreach | 15% → Discovery | 14 days |
| Stage 2: Discovery | 50% → Demo | 7 days |
| Stage 3: Demo | 60% → POC | 14 days |
| Stage 4: POC | 70% → Proposal | 30 days |
| Stage 5: Security Review | 90% → Proposal | 30 days (parallel with POC) |
| Stage 6: Proposal | 50% → Procurement | 14 days |
| Stage 7: Procurement | 80% → Closed-Won | 30 days |

**Overall Win Rate**: 15% × 50% × 60% × 70% × 90% × 50% × 80% = **1.8%** (outreach → closed-won)

Alternative calculation: 50% × 60% × 70% × 50% × 80% = **8.4%** (qualified opportunity → closed-won)

**Average Sales Cycle**: 14 + 7 + 14 + 30 + 14 + 30 = **109 days** (qualified opp → closed-won) ≈ **3.5 months**

### 5.3 Activity Metrics (per AE)

| Activity | Daily | Weekly | Monthly |
|----------|-------|--------|---------|
| Outbound emails | 20 | 100 | 400 |
| LinkedIn outreach | 10 | 50 | 200 |
| Discovery calls | 1 | 5 | 20 |
| Demos | 1 | 3 | 12 |
| Proposals sent | — | 1 | 4 |

### 5.4 Pipeline Goals (2027)

| Metric | Q1 2027 | Q2 2027 | Q3 2027 | Q4 2027 |
|--------|---------|---------|---------|---------|
| **Pipeline value** | $10M | $20M | $35M | $50M |
| **Deals in pipeline** | 40 | 80 | 140 | 200 |
| **Deals in POC** | 5 | 8 | 12 | 15 |
| **Closed-won** | 3 | 4 | 6 | 7 |
| **Quarterly revenue** | $750K | $1M | $1.5M | $1.75M |
| **Cumulative ARR** | $2.5M | $5M | $8M | $10.5M |

---

## 6. Sales Compensation

### 6.1 Account Executive (AE) Compensation

**Base Salary**: $120K–$150K (depends on experience, geography)
**Variable (On-Target Earnings)**: $120K–$150K (100% of base)
**OTE**: $240K–$300K

**Quota**: $2.5M ARR per year per AE

**Commission Structure**:
- 0–50% of quota: 5% commission
- 51–100% of quota: 10% commission
- 101%+ of quota: 15% commission (accelerator)

**Example** (AE hits 100% of quota = $2.5M ARR):
- First $1.25M: 5% = $62.5K
- Next $1.25M: 10% = $125K
- **Total commission**: $187.5K (exceeds $150K OTE → clawback to $150K unless over-quota)

**Spiffs**:
- First deal closed: $5K bonus
- Infrastructure partnership closed (NodeShift, etc.): $25K bonus
- Customer case study published: $2K bonus

### 6.2 Sales Engineer (SE) Compensation

**Base Salary**: $100K–$130K
**Variable (On-Target Earnings)**: $40K–$50K
**OTE**: $140K–$180K

**Tied to team quota**: SE compensation is tied to supported AEs' quota attainment

---

## 7. Sales Enablement

### 7.1 Sales Collateral

| Asset | Purpose | Owner |
|-------|---------|-------|
| **1-page solution brief** (per vertical) | First meeting, leave-behind | Marketing |
| **Discovery question bank** | Qualification | Sales enablement |
| **Demo environment** | Demos, POCs | Engineering |
| **POC playbook** | POC execution | Sales enablement |
| **Security documentation package** | Security review | Engineering + Legal |
| **ROI calculator** | Business case | Marketing |
| **Pricing calculator** | Proposal generation | Sales ops |
| **Contract templates** | Procurement | Legal |

### 7.2 Training

| Training | Audience | Frequency |
|----------|----------|-----------|
| **Product training** | AEs, SEs | Quarterly (new features) |
| **Demo certification** | SEs | Once (upon hire) |
| **Objection handling** | AEs | Monthly (sales meeting) |
| **Competitive intelligence** | AEs, SEs | Monthly (sales meeting) |
| **Vertical deep-dive** (insurance, legal) | AEs | Once per vertical |

---

## 8. CRM & Pipeline Management

**CRM**: Salesforce (or HubSpot for early stage)

**Pipeline Hygiene Rules**:
1. Every opportunity has a close date (required field)
2. Every opportunity has a next step (required field)
3. Opportunities with no activity in 14 days → flagged for review
4. Opportunities older than 12 months → archived (unless active procurement)
5. Stage progression requires exit criteria met (enforced via validation rules)

**Weekly Pipeline Review** (every Monday, 1 hour):
- Review pipeline by stage: where are deals stuck?
- Review upcoming close dates: which deals need help?
- Review lost deals: why did we lose? What can we learn?
- Review new opportunities: are they qualified?

**Monthly Pipeline Analysis**:
- Conversion rates by stage: on track?
- Sales cycle length: improving?
- Win rate: improving?
- Average deal size: increasing?
- Loss reason distribution: patterns?

---

## 9. Success Criteria

**By End of 2027**:
- [ ] $10.5M ARR
- [ ] 20 closed-won enterprise customers
- [ ] 1–2 infrastructure partnerships live (NodeShift + 1 cloud provider)
- [ ] $50M pipeline value
- [ ] 35% win rate (qualified opp → closed-won)
- [ ] 6-month average sales cycle (qualified opp → closed-won)
- [ ] 4:1 pipeline coverage maintained
