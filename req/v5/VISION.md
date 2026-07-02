# AnonReq v5 — Vision

**Produced:** 2026-07-02
**Status:** Active

---

## What AnonReq v5 Is

AnonReq v5 is a **deployable anonymization and compliance appliance** — not just a SaaS gateway.

It sits as a transparent layer between any application and any AI or data backend, intercepting,
anonymizing, auditing, and enforcing data privacy rules in real time. It deploys anywhere:
AWS, GCP, Azure, NodeShift, macOS, Windows, Linux — as a native package, marketplace appliance,
or infrastructure sidecar.

**Vanata** is the compliance automation module built on top of that audit layer. It provides
jurisdiction-specific evidence collection, policy management, and reporting for organizations
operating under EU, Middle East, and Asian data privacy regimes — with a dedicated track for
insurance carriers and law firms who have zero tolerance for non-compliance.

---

## The Two Pillars

### Pillar 1 — Universal Appliance (AnonReq Infrastructure)

AnonReq deploys like infrastructure, not like a SaaS subscription:

```
[Any App / User / Agent / AI Tool]
              ↓
  ┌───────────────────────────┐
  │     AnonReq Appliance     │  ← transparent, sits everywhere
  │  anonymization + audit    │
  │  + policy enforcement     │
  └───────────────────────────┘
              ↓
[NodeShift / AWS / GCP / Azure / On-Prem / Local Model]
```

Deployment targets:
- AWS Marketplace AMI / CloudFormation
- GCP Marketplace VM / Deployment Manager
- Azure Marketplace VM / ARM template
- NodeShift bare metal / GPU node sidecar
- macOS `.pkg` native app
- Windows `.msi` service
- Linux `.deb` / `.rpm` package
- Docker / Helm / Kubernetes operator

Modes:
- Reverse proxy (explicit routing)
- Transparent proxy (TLS interception, no app changes required)
- Sidecar (Kubernetes, ECS, Nomad)
- Network appliance (inline, bump-in-the-wire)

### Pillar 2 — Vanata (Regional Compliance Automation)

Vanata is the compliance layer for organizations that have no choice but to comply:

- Insurance carriers — NAIC model law, Lloyd's data handling, actuarial data privacy
- Law firms — legal privilege classification, matter-level data isolation, bar association rules
- EU — GDPR, ePrivacy, NIS2, EU AI Act enforcement
- Middle East — Saudi PDPL, UAE PDPL, DIFC DP Law, Qatar PDPL, Bahrain PDPL
- Asia — PIPL (China), PDPA (Thailand, Singapore), APPI (Japan), DPDP (India), PIPA (South Korea)

Vanata provides:
- Jurisdiction-specific control mappings (not generic SOC 2 checklists)
- Automated evidence collection per regime
- Policy lifecycle: write → approve → version → distribute
- Audit-ready export packages per regulator
- Employee training tracking
- Access reviews
- Security questionnaire automation

---

## What Changes from v4 to v5

| v4 | v5 |
|---|---|
| SaaS gateway with enterprise features | Deployable appliance + SaaS option |
| GDPR / LGPD / PDPA / POPIA presets | Full regional compliance: EU + Middle East + Asia |
| NodeShift mentioned as gap | NodeShift as first-class deployment target |
| No packaging story | AWS / GCP / Azure / macOS / Windows / Linux packages |
| Vanta gaps identified | Vanata module with full compliance automation |
| Insurance/legal as generic enterprise | Insurance and law firm as dedicated vertical tracks |
| Transparent proxy planned | Transparent proxy as core deployment mode |

---

## V5 Release Shape

| Stage | Phases | Goal |
|---|---|---|
| Stage 4 — Appliance Foundation | 22–24 | Packaging, marketplace listings, transparent proxy |
| Stage 5 — Infrastructure Integrations | 25–27 | NodeShift, AWS, GCP, Azure native integrations |
| Stage 6 — Vanata Core | 28–30 | EU + Middle East + Asia compliance modules |
| Stage 7 — Vertical Tracks | 31–32 | Insurance and law firm dedicated compliance tracks |
