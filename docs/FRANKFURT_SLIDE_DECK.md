---
marp: true
theme: default
paginate: true
title: "AnonReq — Fail-Closed AI Privacy Gateway (Frankfurt AI Week 2026)"
description: "Use Frontier Models like xAI Grok Without Cleartext PII Leaving Your Perimeter"
---

# AnonReq
### Fail-Closed AI Privacy Gateway for Regulated EU Enterprises
**See what never leaves.**

- **Event:** Frankfurt AI Week Build Days · The Squaire · 30 October 2026
- **Stack:** Self-Hosted Gateway (`de-DE`) · xAI `grok-4` · GlassFlow Rius & Tares
- **Live Demo:** `http://localhost:3000/en` | `http://localhost:3000/de`

> **Speaker Note:** "Teams want AI help with customer documents, but those documents contain names, IBANs, and Tax IDs. AnonReq is a self-hosted gateway that detects and tokenizes sensitive identifiers at the edge before forwarding requests to frontier models like Grok—and restores them when the answer comes back."

---

# 1. The Frankfurt Enterprise Dilemma

| The Business Pressure | The Compliance Block |
| :--- | :--- |
| Support, claims, HR & ops teams paste tickets, PDFs, and logs into ChatGPT / Grok to draft replies and summarize cases. | **GDPR Art. 25/32, BaFin VAIT, DORA & Works Councils (`Betriebsrat`)** prohibit sending cleartext customer PII to external cloud LLMs. |
| Blocking AI outright creates **Shadow AI**—employees use personal devices with zero audit trail. | Naive redaction (`[REDACTED]`) breaks multi-entity reasoning and forces manual copy-paste restoration. |

### The AnonReq Solution
**Deterministic, Reversible Edge Tokenization** — Give the LLM structural tokens (`[IBAN_DE_…6951]`) it can reason over, while keeping real identities encrypted inside your VPC.

---

# 2. Four-Column Round-Trip Architecture

```
[01 Raw Prompt / File] ──► [AnonReq Edge Gateway (de-DE)]
                                 │  1. Presidio + DE Checksum Recognizers
                                 │  2. AES-256-GCM Vault in Valkey
                                 ▼
                           [02 Anonymized Prompt] ──► xAI Grok (grok-4)
                                                           │
                           [03 Model Reply (Before Restore)] ◄─┘
                                 │  3. Deterministic Token Restoration
                                 │     (Reversible PII restored; API_KEY stays masked)
                                 ▼
                           [04 Re-identified Answer] + [DPO Metadata Audit CSV]
```

- **Fail-Closed Guarantee:** If detection or Valkey is unreachable, AnonReq returns **HTTP 503**—zero bytes leave the network.

---

# 3. Document Readiness Check: *"Is This File OK?"*

### Instant Pre-Flight Governance Before Spending a Single Token
1. **Multi-Format Upload (`POST /api/extract`):**
   - Drag & drop `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.json`, `.log`, or `.eml` (up to 5 MB / 7,200 chars).
   - Pure local stream extraction (`node:zlib` FlateDecode & OOXML parser—zero external upload).
2. **Automatic `Scan Only` (`POST /v1/debug/anonymize-preview`):**
   - Evaluates the document against German & EU recognizers **without calling the upstream LLM**.
3. **AI Gate Verdict Card:**
   - **Direct to Cloud LLM:** `BLOCKED (9 PII spans detected)`
   - **Via AnonReq Gateway:** `GOVERNED & SAFE (Reversible session tokens)`
   - 1-click **Copy Masked Text** or **Download Sanitized (`.txt`)**.

---

# 4. Proof Over the Wire: Why Column 03 Matters

A preview header alone doesn't prove to a skeptical CISO what the model actually saw and returned. Our **4-Column Theater** shows the complete wire lifecycle:

| Column | What It Shows | Bank Ticket Example (`de-DE`) |
| :--- | :--- | :--- |
| **01 Raw prompt** | Original document with detected spans highlighted | `Customer: Jörg Müller … IBAN DE89 3704 0044 0532 0130 00 … Tax ID 86095742719` |
| **02 Anonymized prompt** | Exact tokenized payload sent outbound | `Customer: [PERSON_…6951] … IBAN [IBAN_DE_…6951] … Tax ID [TAX_ID_DE_…6951]` |
| **03 Model reply (before restore)** | Verbatim `grok-4` response (`anonreq_raw_content`) *before* `RestorationStage` | `Dear [PERSON_…6776], we verified IBAN [IBAN_DE_…6776] and Tax ID [TAX_ID_DE_…6776]…` |
| **04 Re-identified answer** | Final restored reply delivered to the agent | `Dear Jörg Müller, we verified IBAN DE89 3704 0044 0532 0130 00 and Tax ID 86095742719…` |

---

# 5. Five EU Buyer Scenarios (Built Into the Demo)

| # | Scenario | Buyer Persona | Key Entities Governed | Special Proof |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Bank Support Ticket (Primary)** | Bank Ops Lead / CISO (BaFin VAIT) | `IBAN_DE`, `TAX_ID_DE`, `PERSON`, `STREET_ADDRESS_DE`, `DATE_DE` | Tuned `MNPI_TICKER` exclusions (`SEPA`, `ID` never false-positive) |
| **2** | **Insurance Claim (`Kfz`)** | Claims Director / DPO ( Art. 9 GDPR ) | `KVNR`, `PERSONAL_AUSWEIS`, `AKTENZEICHEN`, `HR_NUMBER`, `IBAN_DE` | Protects health & national ID numbers during claim triage |
| **3** | **HR / CV Screening** | Head of People / `Betriebsrat` | `PERSON`, `DATE_DE`, `STREET_ADDRESS_DE`, `TAX_ID_DE`, `IBAN_DE` | Works-council-friendly blind skills extraction |
| **4** | **Energy & Grid Ops (`KRITIS`)** | Grid Ops Director (NIS2) | `SITE_ID` (`UW-NORD-0417`), `ACCOUNT_NUMBER_DE`, `PERSON` | Masks substation IDs & on-call mobile numbers |
| **5** | **Agent Tool Call + Secret** | AI Platform / SecOps Lead | `PERSON`, `IBAN_DE` (`Reversible`) + `API_KEY` (`Permanent Mask`) | **Differential policy:** PII restores in Col 04; `API_KEY` stays masked |

---

# 6. Sponsor Ecosystem: xAI Grok + GlassFlow

### 1. xAI `grok-4` Upstream (`https://api.x.ai/v1`)
- Drop-in OpenAI-compatible routing via `config/model_aliases.demo.yaml`.
- `grok-4` reasons accurately over deterministic tokens (`[IBAN_DE_…]`) for summarization, reply drafting, and JSON field extraction.

### 2. GlassFlow Rius — Zero-PII Agent Observability (OTEL)
- Generates a 3-span OpenTelemetry trace (`anonreq.gateway.chat` → `anonreq.presidio.anonymize` → `xai.grok.chat_completions`) recording latency, token counts, and entity types—**never cleartext PII**.

### 3. GlassFlow Tares — Sanitized Context Timeline (CloudEvents 1.0)
- Emits `ai.anonreq.gateway.sanitized_interaction` CloudEvents so downstream Tares triggers wake agents with **already-tokenized context**.

---

# 7. CISO & DPO Controls: Fail-Closed & Audit Export

### Fail-Closed Circuit Breaker
- Stop `presidio-analyzer` mid-demo:
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.germany.yml -f docker-compose.demo.yml stop presidio-analyzer
  ```
- Gateway immediately returns **HTTP 503 (`fail_closed`)**—zero upstream requests reach xAI.

### DPO Metadata-Only Audit CSV (`GET /v1/admin/anonymization-events/export`)
- Every gateway call records an immutable audit row:
  `event_id, timestamp, tenant_id, entity_types, entity_count, action_taken, sensitivity`
- **Zero raw PII stored in the audit database**—ready for BaFin / GDPR Article 30 inspections.

---

# 8. 90-Second Live Stage Runbook

| Time | Action on Screen (`http://localhost:3000/en`) | Key Takeaway |
| :--- | :--- | :--- |
| **`0:00–0:15`** | Select **1. Bank Support Ticket** and drop the sample `.pdf` into the upload zone. | Real-world SEPA ticket with `IBAN_DE` and `Steuer-ID`. |
| **`0:15–0:35`** | Point to the **AI Gate Verdict Card** (`Scan Only` auto-runs on upload). | Instant pre-flight check: `Direct to LLM: BLOCKED` vs `Via AnonReq: SAFE`. |
| **`0:35–0:60`** | Choose **Draft Reply** → click **Anonymize & Ask Grok**. Walk across **Col 01 → Col 02 → Col 03**. | **Col 02** shows tokens leaving; **Col 03** proves `grok-4` replied with tokens over the wire. |
| **`0:60–0:75`** | Point to **Col 04 (Re-identified answer)** and response headers. | Reversible tokens restored (`Jörg Müller`, `DE89...`); ready for the agent. |
| **`0:75–0:90`** | Click **Emit to GlassFlow Rius & Tares** + **Download DPO Audit CSV**. | Zero-PII observability traces + DPO compliance proof in one click. |

---

# 9. Honest Scope & Pilot Next Steps

### What We Verified Today vs. Pilot Scope
- **Verified in this container stack:** Readable text extraction (`.pdf`, `.docx`, `.txt`, `.csv`, `.json`, `.md`, `.log`, `.eml` up to 5 MB / 7,200 chars), German NER + checksum recognizers, 4-column wire verification with `grok-4`, differential `API_KEY` masking, fail-closed HTTP 503, and DPO CSV export.
- **Evaluated during a 30-Day Pilot:**
  1. Recall/precision tuning on **your synthetic domain documents** (custom regex/checksum recognizers & exclusion lists).
  2. Large-file **Sanitized RAG chunking** (anonymizing chunks before vector embedding).
  3. OCR for scanned image PDFs and live SIEM / GlassFlow OTLP sink wiring inside your VPC.

### Let's Run a 30-Minute Germany PoC
**Bring one synthetic workflow from your team — inspect what is detected, what leaves, and what comes back.**
