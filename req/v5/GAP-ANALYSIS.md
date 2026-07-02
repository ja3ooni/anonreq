# AnonReq v5 — Competitive Gap Analysis
# NodeShift.com & Vanta.com

**Produced:** 2026-07-02
**Scope:** `.planning/` and `req/` folders reviewed against NodeShift and Vanta public feature sets.

---

## 1. NodeShift Gap Analysis

NodeShift is a GPU cloud / AI infrastructure marketplace. AnonReq is a security gateway — these are different product categories. The overlap is narrow but strategically important.

### 1.1 Feature Comparison

| NodeShift Feature | AnonReq Coverage | Status |
|---|---|---|
| GPU cloud compute / bare metal | Not applicable | Out of scope by design |
| Multi-cloud AI deployment | Phase 21 — sovereign/hybrid routing | Partial |
| Model deployment & serving | Phase 21 — local model routing (vLLM, Ollama) | Partial |
| AI workload orchestration (job scheduling, autoscaling) | Not planned | Gap |
| Cost/spend visibility per workload | Phase 8 — per-tenant spend budgets | Partial (no GPU cost tracking) |
| Developer API for infra provisioning | Not planned | Gap |
| AI model marketplace | Not planned | Out of scope |

### 1.2 Positioning Conclusion

AnonReq does not compete with NodeShift. The valid relationship is AnonReq as a security/compliance layer that sits **on top of** NodeShift-provisioned infrastructure. This integration story is not documented anywhere in the current planning.

### 1.3 NodeShift-Specific Gaps

| Gap | Description | Priority |
|---|---|---|
| NodeShift deployment profile | No deployment guide or Helm chart variant for running AnonReq on NodeShift bare metal or GPU nodes | Medium |
| NodeShift model connector | No connector for routing anonymized prompts to NodeShift-hosted model endpoints | Medium |
| GPU cost passthrough | No spend attribution or cost tracking for NodeShift GPU usage per tenant | Low |

---

## 2. Vanta Gap Analysis

Vanta is a compliance automation platform. AnonReq's Stage 2 and V4 plans overlap significantly with Vanta's feature set, but several Vanta core capabilities have no requirements, no phase, and no architecture in the current planning.

### 2.1 Feature Comparison

| Vanta Feature | AnonReq Coverage | Status |
|---|---|---|
| Automated evidence collection (SOC 2, ISO 27001, GDPR, HIPAA) | Phase 11 + Phase 16 + V4 Theme 2 | Partial — AI controls only, not general IT controls |
| Continuous control monitoring & drift detection | Phase 11 (SLO/drift) | Covered for AI controls |
| Compliance scorecards & dashboards | V4 Theme 2 + Phase 14 | Planned in V4 |
| Vendor / third-party risk management | Phase 15 (SUPP-01..05), Phase 16 | Covered for AI providers |
| Security questionnaire automation | V4_FEATURE_SET.md mention only | Gap — no requirements, no phase, no architecture |
| Trust Center (public-facing) | Phase 18-Trust-Center folder | Planned |
| Remediation task tracking with ownership | V4 Theme 2 mention only | Gap — no requirements defined |
| Employee security training tracking | Not mentioned anywhere | Gap |
| Access reviews (periodic review of who has access) | Not mentioned | Gap |
| Penetration test management | Not mentioned | Gap |
| Policy lifecycle management (write/approve/distribute) | Not mentioned | Gap |
| Risk register | Phase 14 (RISK-01..05) | Covered |
| Subprocessor management workflow | Phase 15 — sub-processor list as a field only | Partial |
| Customer-facing questionnaire portal | V4 Theme 4 mention only | Gap — no requirements |
| HR / MDM / cloud asset integrations (Okta, AWS, GitHub, Jamf) | Not planned | Gap |
| Audit evidence export | Phase 11, Phase 14 (conformity package) | Covered |
| SOC 2 readiness report | Phase 20-SOC2-ISO-Readiness | Planned |
| HIPAA / HITRUST compliance framework | V4 Theme 2 mention only | Gap — no requirements, no phase |

### 2.2 What AnonReq Does Better Than Vanta

These are areas where AnonReq is ahead of or differentiated from Vanta:

- AI-specific DLP, firewall, and anonymization — Vanta has none of this
- Agent and tool call governance — unique to AnonReq
- Financial services compliance depth (DORA, MNPI, MRM, FINRA) — Vanta is generic
- Ephemeral data handling and fail-secure architecture
- Multi-locale PII detection (8 locales)
- SIEM/SOC integration depth (Splunk, QRadar, Sentinel, Elastic, Datadog)
- Prompt injection and jailbreak detection at the infrastructure layer

### 2.3 Vanta-Specific Gaps (No Requirements Defined)

| Gap ID | Feature | Vanta Equivalent | Current State | Priority |
|---|---|---|---|---|
| GAP-V-01 | Security questionnaire automation | Core Vanta feature | V4_FEATURE_SET.md mention only | High |
| GAP-V-02 | Policy lifecycle management | Vanta Policies module | Not mentioned in any doc | High |
| GAP-V-03 | Employee security training tracking | Vanta Training module | Not mentioned in any doc | Medium |
| GAP-V-04 | Access reviews | Vanta Access Reviews | RBAC/SSO planned, no review workflows | Medium |
| GAP-V-05 | Penetration test management | Vanta Tests module | Not mentioned in any doc | Medium |
| GAP-V-06 | HIPAA / HITRUST framework | Vanta compliance frameworks | V4 mention only, no requirements | High |
| GAP-V-07 | Subprocessor management workflow | Vanta Vendors module | Field in provider record only | Low |
| GAP-V-08 | Remediation task tracking | Vanta Remediation | V4 mention only, no requirements | Medium |
| GAP-V-09 | HR / MDM / cloud asset integrations | Vanta Integrations (Okta, AWS, GitHub, Jamf) | SIEM-only connectors planned | Medium |
| GAP-V-10 | Customer questionnaire portal | Vanta Trust Center | V4 mention only, no requirements | Medium |

---

## 3. Planning Coverage Assessment

### 3.1 Well-Covered Areas

| Area | Phases | Confidence |
|---|---|---|
| Core anonymization pipeline | 1–5 | High |
| SSE streaming | Phase 3 | High |
| Multi-locale detection | Phase 4 | High |
| Compliance presets (GDPR, LGPD, PDPA, POPIA) | Phase 4 | High |
| AI security firewall | Phase 10 | High |
| Financial services compliance (DORA, MNPI, MRM) | Phase 15 | High |
| AI governance (ISO 42001, EU AI Act) | Phase 14 | High |
| SIEM/SOC integration | Phase 20 | High |
| Agent/tool governance | Phase 18 | High |
| Sovereign/local routing | Phase 21 | High |

### 3.2 Partially-Covered Areas (V4 mention, no requirements)

| Area | Location | What's Missing |
|---|---|---|
| Questionnaire automation | V4_FEATURE_SET.md Theme 3 | Requirement IDs, phase assignment, architecture |
| Remediation task tracking | V4_FEATURE_SET.md Theme 2 | Requirement IDs, data model, API spec |
| HIPAA/HITRUST | V4_FEATURE_SET.md Theme 2 | Control mapping, requirement IDs, phase |
| Customer questionnaire portal | V4_FEATURE_SET.md Theme 4 | Requirement IDs, UX spec, phase |

### 3.3 Structural Planning Gaps

| Issue | Location | Impact |
|---|---|---|
| `09-RBAC-SSO/` has no plan files | `.planning/phases/09-RBAC-SSO/` | Stage 2 cannot start without plan files |
| `10-Tenant-Isolation/` has no plan files | `.planning/phases/10-Tenant-Isolation/` | Tenant isolation unexecutable |
| Duplicate phase numbering (09, 10, 11, 12, 13, 14, 15, 16) | `.planning/phases/` | Two parallel tracks with same numbers — ambiguous execution order |

---

---

## 4. Recommended Actions

### Immediate (before Stage 2 execution)

1. Resolve duplicate phase numbering — the `09-RBAC-SSO`, `10-Tenant-Isolation`, `11-Audit-Compliance-Center`, etc. folders conflict with `09-multimodal-document-anonymization`, `10-ai-security-firewall`, etc. Assign a clear numbering scheme.
2. Add plan files to `09-RBAC-SSO/` and `10-Tenant-Isolation/` — these are prerequisites for multi-tenant enterprise features.

### High Priority (V5 requirements to define)

3. Define `QUEST-01..05` requirements for security questionnaire automation and assign to a phase.
4. Define `POLICY-01..05` requirements for policy lifecycle management (write, approve, version, distribute).
5. Decide explicitly whether HIPAA/HITRUST are in scope — if yes, add requirement IDs and a phase; if no, document as out of scope.

### Medium Priority

6. Define `TRAIN-01..03` requirements for employee security training tracking.
7. Define `ACCREV-01..03` requirements for periodic access reviews.
8. Expand subprocessor management from a field to a workflow (`SUBP-01..04`).
9. Add a NodeShift deployment profile to Phase 15 or Phase 21 documentation.

### Low Priority

10. Define `PENTEST-01..03` for penetration test management and evidence tracking.
11. Add HR/MDM/cloud asset integration connectors to Phase 13-Enterprise-Connectors scope.
