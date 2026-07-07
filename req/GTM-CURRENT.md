# GTM-CURRENT — AnonReq Operating Plan

**Status:** Active operating document. Supersedes `GTM.md` (v1) and `v5/GTM.md` for day-to-day decisions; those remain reference material for later stages.
**Last updated:** 2026-07-04
**Rule:** This is the only GTM document consulted until 3 design partners are live. Update it; don't fork it.

---

## 1. Current position (honest baseline)

- Product: built through Phase 21+ (core gateway + enterprise layers). Not launched.
- Customers: 0. Pipeline: 0. References: 0.
- Team: solo founder. Personal runway: ___ months (fill in — this number drives everything).
- The bottleneck is not product. No new phases until gates below say so.

## 2. Open decision: licensing

| Option | Pros | Cons |
|---|---|---|
| Apache 2.0 open-core (current repo assumption) | Max trust ("audit it"), max distribution, easiest OEM embed, procurement-friendly (forkable if vendor dies) | Anyone (incl. clouds) may resell/host it; can't be revoked once released |
| FSL / BSL source-available (Sentry/HashiCorp model) | Full auditability retained, blocks competitors from hosting/reselling, converts to Apache after 2–4 yrs | Weaker community/funnel, some enterprises' OSS policies exclude it, HN launch lands softer |
| Closed source | Full control | Kills the #1 differentiator (verifiable trust) and the zero-budget distribution channel |

**Default if undecided by launch:** FSL for the core (auditability + resale protection), permissive licenses for SDKs/clients. Revisit at Gate 2.

## 3. Motion gates (multi-product, 20-year structure)

| # | Motion | Activation gate | Status |
|---|---|---|---|
| 1 | Source launch + design partners | **NOW** | ← current focus |
| 2 | AnonReq Cloud SaaS (single region, Frankfurt) | Launch done + 2 design partners live | waiting |
| 3 | Commission freelancers / channel | SaaS live + 1 published case study | waiting |
| 4 | Infrastructure embed / OEM (GPU clouds) | 1 signed LOI (pursue conversations now) | conversations only |
| 5 | Enterprise tier + certifications (ISO 27001 → SOC 2) | €10k MRR OR first enterprise buyer requires it | waiting |
| 6 | Vanata as standalone product | Motion 2 attach rate proves demand (≥25% of Business tier) | waiting |
| 7 | Appliance / hardware | ≥€1M ARR + repeated inbound requests | frozen |

Each motion is funded by the one before it. Nothing skips its gate.

## 4. Next 90 days

**Objective: 3 signed design partners.** Everything below serves that.

**Design partner offer (write as 2-page agreement):**
- 90-day pilot, free or €5–10k, includes hands-on deployment support
- They provide: deployment feedback, anonymized case study, 2 reference calls
- Converts to €30–60k/year license (20% founding-customer discount, locked 3 years)

**Month 1 — assets (~€500):**
- [ ] Site: public pricing, 3-min demo video, 2 comparison pages
- [ ] Launch week (post-licensing decision): Show HN, Product Hunt, r/selfhosted, r/LocalLLaMA, LinkedIn
- [ ] Founder LinkedIn cadence 3×/week (EU AI Act, shadow-AI, AWS-sovereignty backstory)
- [ ] Fix CV/pitch claims to match reality (diligence-proof)

**Month 2 — vertical capture (€500–1,500):**
- [ ] German landing pages: law firms ("KI in der Kanzlei — DSGVO-konform") + insurance brokers
- [ ] 2 lead magnets: EU AI Act readiness checklist; no-PII-in-logs verification writeup
- [ ] G2 / Capterra / OMR listings; start 10-article SEO cluster (€150–400/article outsourced)
- [ ] Outbound: 50 named DACH accounts (law firms 10–200 lawyers, regional brokers, insurtechs) via AWS alumni, founder community, Wolver intros

**Month 3 — proof (€2,000–4,000):**
- [ ] Webinar co-hosted with a data-protection lawyer
- [ ] LinkedIn ads pilot €1,500–3,000 against lead magnets only; kill if CPL > €150
- [ ] First design-partner case study published

## 5. SaaS motion (activates at Gate 2)

**Launch costs (real numbers):**

| Item | Cost |
|---|---|
| Infra, Frankfurt single region (Hetzner) | €300–600/mo |
| Pen test (year-1 trust artifact — NOT SOC 2) | €8–15k/yr |
| DPA + ToS (lawyer) | €3–8k one-time |
| Stripe | ~2.3% effective |
| Support tooling | €150–300/mo |
| **Cash to first SaaS revenue** | **€15–30k** |

SOC 2 deferred to Gate 5 (€30–60k, 6–9 months). DACH trust story year 1: Frankfurt hosting + DPA + pen test + source auditability.

**Tiers (from v5, simplified to 3):** Professional €299/mo · Business €999/mo · Business+ €2,499/mo. Vanata jurisdiction add-ons per v5 pricing once attach demand is proven. No free tier until support load is understood — 14-day trial, card required (benchmark: 25–40% trial→paid vs 2–5% freemium).

**Break-even:** platform costs covered at 1 Business customer; founder salary (€4k/mo) at ~5 Business customers. Year-1 defensible target: 25–50 paid, €10–30k MRR.

**Benchmarks to plan against (replace with own data by day 90):**
trial(card)→paid 25–40% · SMB churn 3–5%/mo · LinkedIn CPC €10–20 · CPL target ≤€150 · SEO traction 4–9 months.

## 6. Sales freelancers (activates at Gate 3)

- 30% of **collected** first-12-month revenue; 10% year-2 trail
- Paid pilot bounty €1–2k + 25–30% of conversion
- 90-day clawback; deal registration with 90-day named-account exclusivity; monthly payout on cash receipt; contractor agreement, no equity
- Founder supplies first 10 warm leads + joins first 5 calls per rep
- Max 2 reps to start. Source: CommissionCrowd, RepHunter, Upwork, freelancermap (DACH — German speaker with legal/insurance book preferred)
- Longer term: prefer MSP/reseller channel at 20–30% margin

## 7. KPIs (instrument from day 1: Plausible + Stripe + sheet)

visitors → signups → activated (first proxied request) → design-partner conversations → signed partners → paid.
Weekly review. If after 2 quarters of real effort no one takes even the free pilot → revisit the entire thesis.

## 8. Top risks

1. Market consolidation: Prompt Security→SentinelOne, Lakera→Check Point, Protect AI→Palo Alto; Purview/Zscaler/Netskope bundle GenAI DLP. Counter-position: self-hosted sovereignty + multi-locale (Arabic) + fail-secure — the things platforms can't/won't do.
2. Solo-founder key-person risk (procurement blocker) → forkability/escrow answer required in sales deck.
3. Detection is probabilistic (Presidio recall < 100%) → never market "no PII ever leaves"; market "fail-secure controls + audit evidence". Legal review of claims before launch.
4. Founder focus split (consulting / job market / startup) → decide before spending on launch.
