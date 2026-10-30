---
marp: true
theme: default
paginate: true
title: "AnonReq — Pitch & Live Demo Deck (Frankfurt AI Week 2026)"
description: "Intro, Origin Story, Linked Regulatory Violations & Controls (GDPR, EU AI Act, DORA, NIS2, BetrVG), 4-Column Wire Proof, and 2-Week Germany PoC"
---

# 01 · Introduction
## AnonReq — See What Never Leaves.
**The Fail-Closed, Self-Hosted AI Privacy Gateway for Regulated EU Enterprises**

- **Who We Are:** Built by **Abdullah Al-Jauni ([InfraTechton](https://infratechton.com/))** — AI infrastructure strategist & architect based in Frankfurt am Main.
- **The Core Thesis:** *"Legal said 'No' to Cloud AI. This proxy makes the same model a 'Yes.'"*
- **What It Is:** Not a new model or a "140-model cloud platform." An on-prem edge gateway sitting in front of the API key you already bought (`xAI Grok`, OpenAI, Claude, Gemini).
- **Event:** Frankfurt AI Week Build Days · The Squaire · Friday, 30 October 2026

---

# 02 · Origin Story & History
## How AnonReq Was Born in Frankfurt Rooms
> *"Frankfurt banks that ban Claude or ChatGPT still have Steuer-IDs landing in personal chats."*

1. **Act I — The Boardroom Ban:** Across Frankfurt banks, Munich insurers, and Berlin agencies, teams built promising AI pilots for support and claims—until Legal & the DPO froze them overnight over `DE-IBAN`, `Steuer-ID`, and `KVNR` under GDPR Art. 44, EU AI Act & DORA.
2. **Act II — The Shadow AI Reality:** When summarizing a claim takes 2 hours manually, employees don't stop using AI—they paste tickets into personal chats on unmanaged phones. **Bans create Shadow AI; governance creates an audit trail.**
3. **Act III — Building AnonReq:** We built what CISOs and DPOs actually asked for on Day 1: keep your existing LLM API key, strip German PII in memory before it leaves your VPC, restore context in the reply, and export a clean audit CSV.

---

# 03 · The Problem: Laws & Policies Broken (`[P1]`–`[P9]`)
## What Breaks When Teams Paste Documents Into Cloud AI

| Violation Group | Specific Articles & Policies Broken (`[P1]`–`[P9]`) |
| :--- | :--- |
| **1. GDPR & German Labor Law (`BDSG` / `BetrVG`)** | • **`[P1]` GDPR Art. 44 (Third-Country Transfer):** Sending cleartext `DE-IBAN`, `Steuer-ID`, or `KVNR` to US/external LLM servers without supplementary technical safeguards.<br>• **`[P2]` GDPR Art. 5(1)(c)/(e) & Art. 25:** Data minimisation & storage limitation breached when whole PDFs are sent upstream and logged on disk.<br>• **`[P3]` GDPR Art. 9 & `BetrVG § 87` / `BDSG § 26`:** Unprotected medical claims (`KVNR`) and candidate CVs screened without Works Council (`Betriebsrat`) approval. |
| **2. EU AI Act (`2024/1689`) & `DORA` (`2022/2554`)** | • **`[P4]` EU AI Act Art. 12 & Art. 26(6) (Deployer Logging):** Shadow AI leaves zero audit trail of who sent what prompt to which GPAI model.<br>• **`[P5]` EU AI Act Art. 14 & Art. 26(5) (Human Oversight):** No pre-flight readiness gate before sensitive documents hit GPAI.<br>• **`[P6]` DORA Art. 5, 9, 28 + BaFin VAIT:** Uncontrolled ICT third-party data exposure with no fail-secure circuit breaker. |
| **3. `NIS2` (`KRITIS`) & Legacy DLP** | • **`[P7]` NIS2 Art. 21 & 24 / BSIG `KRITIS`:** Ops logs leak critical substation IDs (`SITE_ID`) and live `API_KEY` credentials.<br>• **`[P8]` Broken `[REDACTED]` DLP:** Static masks destroy multi-entity relationships so the LLM mixes up accounts.<br>• **`[P9]` Local 70B LLM Trap:** High GPU cost, and PII/keys still leak into app logs & OTEL traces. |

---

# 04 · The Solution: Linked 1-to-1 Policy Controls (`→ [P1]`–`[P9]`)
## How AnonReq Solves Each Violation at the Network Edge

| Linked Target | AnonReq Technical Countermeasure |
| :--- | :--- |
| **Solves `[P1, P2, P3]`**<br>*(GDPR Art. 44, 32, 25, 9, 5 & BetrVG § 87)* | • **`→ [P1]` GDPR Art. 44 & 32:** Hybrid `de-DE` detector (`MOD-97` + Presidio `de_core_news_lg`) replaces `IBAN_DE`, `Steuer-ID` & `KVNR` with deterministic HMAC tokens (`[IBAN_DE_…6951]`) inside your VPC.<br>• **`→ [P2]` GDPR Art. 5(1)(c)/(e) & 25:** Ephemeral AES-256-GCM Valkey vault (`save ""`, `appendonly no`) auto-evicts mappings after TTL.<br>• **`→ [P3]` BetrVG § 87 & Art. 9:** Strips candidate/patient PII pre-LLM; `stdout` JSON logs redact all prompt/response values. |
| **Solves `[P4, P5, P6]`**<br>*(EU AI Act Art. 12, 14, 26 & DORA Art. 5, 9, 28)* | • **`→ [P4]` EU AI Act Art. 12/26(6) + GDPR Art. 30:** Immutable metadata-only **DPO Audit CSV** (who, when, model, `entity_types`) + zero-PII **GlassFlow Rius** OTEL traces.<br>• **`→ [P5]` EU AI Act Art. 14/26(5):** *"Is This File OK?"* `Scan Only` Verdict Card + **4-Column Wire Proof** for maker-checker oversight.<br>• **`→ [P6]` DORA Art. 5, 9 & 28:** Fail-closed **HTTP 503** if Presidio/Valkey is down; upstream provider only ever processes tokens. |
| **Solves `[P7, P8, P9]`**<br>*(NIS2 Art. 21/24 & Multi-Entity Accuracy)* | • **`→ [P7]` NIS2 Art. 21/24 (`KRITIS`):** Tokenizes substation `SITE_ID`s and enforces `Permanent Mask` (`reversible: false`) on `API_KEY`s.<br>• **`→ [P8]` Fixes `[REDACTED]`:** Deterministic tokens preserve relationships; `RestorationStage` swaps PII back in milliseconds.<br>• **`→ [P9]` No GPU Lock-In:** Runs on CPU in Docker/Helm while unlocking frontier `grok-4` reasoning safely. |

---

# 05 · Problem ↔ Solution Compliance Matrix
## Direct 1-to-1 Crosswalk for CISO, DPO & Legal Sign-Off

| Policy / Regulation | What Breaks Without AnonReq (Problem) | How AnonReq Enforces It (Solution) |
| :--- | :--- | :--- |
| **`[P1/P2]` GDPR Art. 44, 32, 25 & 5(1)(c)/(e)** | Cleartext `DE-IBAN`, `Steuer-ID` & names sent to US/external LLM servers; stored on disk. | Preset `germany` (`de-DE`) tokenizes PII at VPC edge; AES-256-GCM Valkey with `save ""` & TTL eviction. |
| **`[P3]` GDPR Art. 9, BDSG § 26 & BetrVG § 87** | Medical `KVNR` in claims & employee CVs screened in cloud AI without Works Council safeguard. | `KVNR`, `Personalausweis` & candidate PII stripped pre-LLM; `stdout` JSON logs redact all prompt values. |
| **`[P4/P5]` EU AI Act Art. 12, 14 & 26(5)/(6)** | Shadow AI has no deployer log, no input readiness check, and no human-in-the-loop verification. | `Scan Only` Verdict Card + 4-Column Wire Proof + 1-click DPO CSV (who, when, model, `entity_types`). |
| **`[P6]` DORA Art. 5, 9, 28, 30 & BaFin VAIT** | ICT third-party concentration risk & uncontrolled cleartext fallback if a security tool crashes. | Self-hosted gateway (Helm/Compose); provider only sees tokens; fail-closed `HTTP 503` on detector failure. |
| **`[P7/P8]` NIS2 Art. 21/24 (`KRITIS`) & DLP** | Substation `SITE_ID`s & live `API_KEY`s leaked; static `[REDACTED]` breaks LLM replies. | `Reversible` tokens for customer PII (restored in Col 04) + `Permanent Mask` (`reversible: false`) for `API_KEY`. |

---

# 06 · Product Feature 1: Document Readiness Check
## Upload Any File → Instant *"Is It OK?"* Compliance Verdict
*Enforces GDPR Art. 25 & EU AI Act Art. 26(5) before spending a single upstream LLM token.*

1. **Multi-Format Upload (`POST /api/extract`):**
   - Drag & drop `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.json`, `.log`, or `.eml` (up to 5 MB / 7,200 chars).
   - Pure local stream extraction (`node:zlib` FlateDecode & OOXML parser—zero external upload).
2. **Automatic `Scan Only` (`POST /v1/debug/anonymize-preview`):**
   - Evaluates the document against German & EU recognizers **without calling the upstream LLM**.
3. **AI Gate Verdict Card:**
   - **Direct to Cloud LLM:** `BLOCKED (GDPR Art. 44 / DORA risk — PII spans detected)`
   - **Via AnonReq Gateway:** `GOVERNED & SAFE (GDPR Art. 32 pseudonymised)`
   - 1-click **Copy Masked Text** or **Download Sanitized (`.txt`)**.

---

# 07 · Product Feature 2: Four-Column Wire Proof
## Why Column 03 Convinces Skeptical CISOs & Judges
*Visualizes GDPR Art. 32 pseudonymisation & Art. 44 transfer protection across the entire wire round-trip.*

| Column | What It Shows | Bank Ticket Example (`de-DE`) |
| :--- | :--- | :--- |
| **01 Raw prompt** | Original document with detected spans highlighted | `Customer: Jörg Müller … IBAN DE89 3704 0044 0532 0130 00 … Tax ID 86095742719` |
| **02 Anonymized prompt** | Exact tokenized payload sent outbound | `Customer: [PERSON_…6951] … IBAN [IBAN_DE_…6951] … Tax ID [TAX_ID_DE_…6951]` |
| **03 Model reply (before restore)** | Verbatim `grok-4` response (`anonreq_raw_content`) *before* `RestorationStage` | `Dear [PERSON_…6776], we verified IBAN [IBAN_DE_…6776] and Tax ID [TAX_ID_DE_…6776]…` |
| **04 Re-identified answer** | Final restored reply delivered to the agent | `Dear Jörg Müller, we verified IBAN DE89 3704 0044 0532 0130 00 and Tax ID 86095742719…` |

---

# 08 · Five EU Buyer Use Cases & Policy Frameworks

| # | Scenario | Regulations Addressed | Key Entities Governed | Special Proof |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Bank Support Ticket (Primary)** | GDPR Art. 44 · DORA Art. 28 · BaFin VAIT | `IBAN_DE`, `TAX_ID_DE`, `PERSON`, `STREET_ADDRESS_DE`, `DATE_DE` | Tuned `MNPI_TICKER` exclusions (`SEPA`, `ID` never false-positive) |
| **2** | **Insurance Claim (`Kfz`)** | GDPR Art. 9 (Health) · Art. 32 · BDSG | `KVNR`, `PERSONAL_AUSWEIS`, `AKTENZEICHEN`, `HR_NUMBER`, `IBAN_DE` | Protects health & national ID numbers during claim triage |
| **3** | **HR / CV Screening** | `BetrVG § 87` (`Betriebsrat`) · `BDSG § 26` · AGG | `PERSON`, `DATE_DE`, `STREET_ADDRESS_DE`, `TAX_ID_DE`, `IBAN_DE` | Works-council-friendly blind skills extraction |
| **4** | **Energy & Grid Ops (`KRITIS`)** | NIS2 Art. 21/24 · BSIG `KRITIS` · GDPR | `SITE_ID` (`UW-NORD-0417`), `ACCOUNT_NUMBER_DE`, `PERSON` | Masks substation IDs & on-call mobile numbers |
| **5** | **Agent Tool Call + Secret** | EU AI Act Art. 12/14 · NIS2 Supply Chain | `PERSON`, `IBAN_DE` (`Reversible`) + `API_KEY` (`Permanent Mask`) | **Differential policy:** PII restores in Col 04; `API_KEY` stays masked |

---

# 09 · Sponsor Architecture: xAI Grok + GlassFlow

1. **xAI `grok-4` Upstream (`https://api.x.ai/v1`) — GDPR Art. 44 Safeguard:**
   - Drop-in OpenAI-compatible routing via `config/model_aliases.demo.yaml`.
   - `grok-4` receives only tokenized prompts (`[IBAN_DE_…]`) for summarization, reply drafting, and JSON field extraction.
2. **GlassFlow Rius — Zero-PII Agent Observability (EU AI Act Art. 12):**
   - Generates a 3-span OpenTelemetry trace (`anonreq.gateway.chat` → `anonreq.presidio.anonymize` → `xai.grok.chat_completions`) recording latency, token counts, and entity types—**never cleartext PII**.
3. **GlassFlow Tares — Sanitized Context Timeline (CloudEvents 1.0):**
   - Emits `ai.anonreq.gateway.sanitized_interaction` CloudEvents so downstream Tares triggers wake agents with **already-tokenized context**.

---

# 10 · CISO & DPO Controls: Fail-Closed & Audit CSV

### 1-Click DPO Metadata-Only Audit CSV (GDPR Art. 30 & EU AI Act Art. 26(6))
- Every gateway call records an immutable audit row (`GET /v1/admin/anonymization-events/export`):
  `event_id, timestamp, tenant_id, entity_types, entity_count, action_taken, sensitivity`
- **Zero raw PII stored in the audit database**—ready for BaFin / DSB inspections.

### Fail-Closed Circuit Breaker (GDPR Art. 25 & DORA Art. 9)
- Stop `presidio-analyzer` mid-demo:
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.germany.yml -f docker-compose.demo.yml stop presidio-analyzer
  ```
- Gateway immediately returns **HTTP 503 (`fail_closed`)**—zero upstream requests reach xAI.

---

# 11 · Production Depth: Beyond the Hackathon UI

Mapped across **9 regulatory frameworks** (`GDPR`, `EU AI Act`, `DORA`, `NIS2`, `ISO 27001`, `ISO 42001`, `EBA`, `SEC`, `FINRA`):
- **Security & Policy Engine:** RBAC (`PDP/PEP` — ISO 27001 A.5.15), AI Firewall (prompt injection & jailbreak classification), 8 locale bundles, and 6 compliance presets (`GDPR`, `LGPD`, `PDPA`, `POPIA`, `PIPEDA`).
- **Streaming & Protocols:** Real-time token restoration across Server-Sent Events (SSE) streams using a split-token **Tail Buffer**, plus MCP tool inspection and voice transcript sanitization.
- **SOC & VPC Deployment:** Native SIEM sinks (`Splunk HEC`, `Elastic`, `Sentinel`, `QRadar`, `Datadog`), DORA Art. 11/28 incident escalation & provider concentration inventory, and 1-day Docker Compose or Helm rollout.

---

# 12 · 90-Second Live Stage Runbook (`http://localhost:3000/en`)

| Time | Action on Screen | Regulatory Proof Point |
| :--- | :--- | :--- |
| **`0:00–0:15`** | Select **1. Bank Support Ticket** and drop the sample `.pdf` into the upload zone. | Real-world SEPA ticket with `IBAN_DE` and `Steuer-ID` (GDPR Art. 44 / BaFin VAIT blocker). |
| **`0:15–0:35`** | Point to the **AI Gate Verdict Card** (`Scan Only` auto-runs on upload). | Pre-flight check (EU AI Act Art. 14): `Direct to LLM: BLOCKED` vs `Via AnonReq: SAFE`. |
| **`0:35–0:60`** | Choose **Draft Reply** → click **Anonymize & Ask Grok**. Walk across **Col 01 → Col 02 → Col 03**. | **Col 02** shows tokens leaving (GDPR Art. 32); **Col 03** proves `grok-4` replied with tokens over the wire. |
| **`0:60–0:75`** | Point to **Col 04 (Re-identified answer)** and response headers. | Reversible tokens restored from ephemeral Valkey (`save ""`); ready for the agent. |
| **`0:75–0:90`** | Click **Emit to GlassFlow Rius & Tares** + **Download DPO Audit CSV**. | Zero-PII OTEL traces (EU AI Act Art. 12) + DPO metadata CSV (GDPR Art. 30). |

---

# 13 · Honest Scope & 2-Week Germany PoC Offer

- **Verified Live Today:** Readable text extraction (`.pdf`, `.docx`, `.txt`, `.csv`, `.json`, `.md`, `.log`, `.eml` up to 5 MB / 7,200 chars), German NER + checksum recognizers, 4-column wire verification with `grok-4` (GDPR Art. 32/44), differential `API_KEY` masking (NIS2), fail-closed HTTP 503 (DORA Art. 9), and DPO CSV export (GDPR Art. 30).
- **Scoped Together in a 2-Week PoC:**
  1. Residual risk & recall benchmark on **your synthetic domain tickets** (input for GDPR Art. 35 DPIA).
  2. Large-file **Sanitized RAG chunking** (anonymizing chunks before vector embedding).
  3. OCR for scanned image PDFs + VPC Helm deployment with our **Germany Trust Pack & DPA Annex**.

> **Closing Hook:** *"Bring one synthetic workflow. Together we can inspect what is detected, what leaves, and whether the answer is useful."* — **Abdullah Al-Jauni ([infratechton.com](https://infratechton.com/))**
