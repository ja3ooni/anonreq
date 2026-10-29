# AnonReq — Frankfurt AI Week Build Days Speaker Guide & Live Script (30 October 2026)

## Recommendation & Positioning
Use **Scenario 1: Bank Support Ticket (SEPA Dispute)** as the primary 90-second live demonstration. It connects an unmistakable Frankfurt buyer (Bank Ops / CISO / DPO under BaFin VAIT & DORA), a document everyone recognizes, and a practical daily task: **drafting a customer acknowledgement without leaking `IBAN_DE` or `Steuer-ID` to an external LLM**.

Keep **Scenario 2 (Insurance Claim)** and **Scenario 5 (Agent Tool Call + Leaked `API_KEY`)** ready for live follow-up questions—Scenario 5 is especially strong for technical judges because it shows **differential restoration** (customer PII is restored in Column 04, while a leaked `API_KEY` stays permanently masked).

> **Honesty & Verification Discipline:**
> - **Verified live in this stack:** 4-column round-trip UI (`01 Raw prompt` → `02 Anonymized prompt` → `03 Model reply (before restore)` → `04 Re-identified answer`), German Presidio (`de_core_news_lg`) + custom recognizers (`IBAN_DE`, `TAX_ID_DE`, `KVNR`, `PERSONAL_AUSWEIS`, `SITE_ID`, `API_KEY`, tuned `MNPI_TICKER` exclusions), multi-format text extraction (`.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.json`, `.log`, `.eml`), upstream `grok-4` routing via xAI (`https://api.x.ai/v1`), metadata-only DPO CSV export, and fail-closed HTTP 503 when `presidio-analyzer` is stopped.
> - **Sponsor telemetry mode:** GlassFlow Rius (3-span OpenTelemetry trace) and GlassFlow Tares (CloudEvent 1.0 correlated context) payloads are generated and validated locally with zero PII (`POST /api/glassflow`). Live webhook/OTLP forwarding activates only when `GLASSFLOW_RIUS_OTLP_ENDPOINT` or `GLASSFLOW_TARES_WEBHOOK_URL` are configured in `.env`. State clearly whether you are showing local payload validation or a live endpoint.

---

## Opening & Closing Hooks

- **Opening (15s):**
  > *"Every support and operations team in Frankfurt wants to use frontier models like Grok on customer tickets and documents—but compliance blocks them because those files contain German IBANs, Tax IDs, and health numbers. AnonReq is a self-hosted, fail-closed AI privacy gateway that detects and tokenizes sensitive entities at the edge before a single byte leaves your network, and restores them when the answer comes back."*

- **Closing (10s):**
  > *"Document in, PII tokenized at the edge, raw model reply verified over the wire, and a restored answer back to the user—with a zero-PII audit CSV for your DPO. Bring us one synthetic workflow from your team, and let's run a 30-minute Germany PoC."*

---

## 90-Second Live Demo Script (Four-Column Theater)

**Pre-flight state:** Open `http://localhost:3000/en` (or `/de`). Select **1. Bank Support Ticket**. Click **`.pdf`** in the *"Download sample file to test upload"* bar so `anonreq-bank-en-US.pdf` (or `de-DE`) is in your Downloads folder ready to drag-and-drop.

### `0:00 – 0:15` · The Problem & File Upload
- **Action:** Drag and drop the downloaded sample bank ticket `.pdf` into the **Document & File Readiness Check** dropzone (or click **1. Bank Support Ticket**).
- **Say:**
  > *"Here is a synthetic SEPA dispute ticket PDF. A bank support agent wants AI to draft a customer confirmation reply, but the file contains the customer's name, Frankfurt street address, German IBAN (`DE89...`), and `Steuer-ID`."*

### `0:15 – 0:35` · Instant Readiness Check ("Scan Only — Is It OK?")
- **Action:** Point to the **AI Gate Verdict Card** (`Direct to Cloud LLM: BLOCKED` vs `Via AnonReq Gateway: GOVERNED & SAFE`) and the color-coded entity chips (`IBAN_DE`, `TAX_ID_DE`, `PERSON`, `STREET_ADDRESS_DE`, `DATE_DE`).
- **Say:**
  > *"Uploading extracts the readable text stream locally and automatically runs a zero-LLM pre-flight scan. Before calling any external model, AnonReq flags that sending this directly to a cloud LLM is blocked, lists every detected German identifier, and lets the user copy or download a sanitized `.txt` version."*

### `0:35 – 0:60` · Anonymize & Ask Grok (Columns `01` → `02` → `03`)
- **Action:** Select task preset **Draft Reply** (or **As-Is**) and click **Anonymize & Ask Grok**. Point across **Column 01**, **Column 02**, and **Column 03**.
- **Say:**
  > *"Now we send it through AnonReq to `grok-4` on xAI. Look at the four columns:*
  > - *Column 01 is the raw prompt with highlighted PII spans.*
  > - *Column 02 is the tokenized prompt that leaves our perimeter—every identifier is replaced with a deterministic HMAC token like `[IBAN_DE_…6951]` stored in encrypted Valkey.*
  > - *Column 03 is the actual raw response returned by Grok over the wire before re-identification—proving Grok reasoned over the tokens and never saw the real IBAN or Tax ID."*

### `0:60 – 0:75` · Re-identification (Column `04`)
- **Action:** Point to **Column 04 (Re-identified answer)** and the completion response headers (`X-AnonReq-Processed: true`, `X-AnonReq-Entity-Count`, `X-AnonReq-Sensitivity: HIGH`).
- **Say:**
  > *"In Column 04, AnonReq's restoration stage swaps the reversible tokens back in millisecond time so the support agent gets a ready-to-send reply with `Jörg Müller` and the real IBAN intact."*

### `0:75 – 0:90` · DPO Audit CSV, GlassFlow Telemetry & Fail-Closed Guarantee
- **Action:** Scroll to the **GlassFlow · Pilot PoC · 90s Script** panel. Click **Emit to GlassFlow Rius & Tares** to show the zero-PII OTEL spans and CloudEvent payload, then switch to **Tab 2 (Pilot & DPO Handshake)** and click **Download DPO Audit CSV**.
- **Say:**
  > *"For observability and compliance, we emit zero-PII OpenTelemetry traces and CloudEvents for GlassFlow Rius and Tares, and the DPO gets a one-click CSV export containing only entity types and counts—never raw PII. And if Presidio ever goes down, AnonReq fails closed with HTTP 503 rather than leaking cleartext."*

---

## Pre-Demo Tonight & Friday Morning Checklist

1. **Start & Warm the Stack:**
   ```bash
   cd /Users/aljaunia/Documents/Develop/DEMO-anonreq/anonreq
   make demo
   ```
   Confirm all 4 containers are healthy (`anonreq-gateway`, `anonreq-presidio`, `anonreq-valkey`, `anonreq-web-anonreq-web-1`).
2. **Verify `SEPA` / `ID` False-Positive Fix:**
   Click **1. Bank Support Ticket** and verify `SEPA` and `ID` are **not** highlighted as `MNPI_TICKER`—only true PII (`PERSON`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `STREET_ADDRESS_DE`, `LOCATION`, `IBAN_DE`, `TAX_ID_DE`, `DATE_DE`) appears in the badge strip.
3. **Rehearse the Sample PDF Upload:**
   Download the sample `.pdf` from the scenario bar (`<= 5 MB`, `< 7,200 chars`), drag it into the dropzone, verify **Scan Only** runs automatically, then click **Anonymize & Ask Grok** and verify all **4 columns** populate cleanly.
4. **Rehearse Scenario 5 (Agent Tool Call + `API_KEY`):**
   Click **5. Agent Tool Call + Secret**, run **Anonymize & Ask Grok**, and verify that `[API_KEY_…]` stays masked in **Column 04** (`Permanent Mask`), while customer PII is restored (`Reversible`).
5. **Rehearse the Fail-Closed Kill Switch (Optional 15s Bonus for Judges):**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.germany.yml -f docker-compose.demo.yml stop presidio-analyzer
   ```
   Click **Anonymize & Ask Grok** → show the red **HTTP 503 Fail-Closed** banner (zero upstream call made). Then immediately restart:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.germany.yml -f docker-compose.demo.yml start presidio-analyzer
   ```

---

## Answers for Judge & Buyer Questions (Q&A)

- **"How do we know Column 03 is really what came back from the model?"**
  > *"In demo/debug mode (`ANONREQ_DEBUG_PREVIEW_ENABLED=true` with header `X-AnonReq-Include-Raw-Response: true`), the gateway captures `proc_ctx.provider_response` immediately before `RestorationStage` runs and attaches it as `anonreq_raw_content`. Column 03 renders that exact pre-restoration string returned by xAI Grok."*

- **"What if a document contains an API key or secret that should NEVER be restored, even in the final answer?"**
  > *"Let me show you Scenario 5 (`Agent Tool Call + Secret`). Each entity recognizer has a policy (`reversible: true` vs `reversible: false`). Customer PII like `IBAN_DE` is reversible for the authorized session, whereas `API_KEY` is marked `Permanent Mask`—even in Column 04, the secret is never echoed back."*

- **"Does it anonymize the binary PDF file itself or scanned images?"**
  > *"This gateway path extracts readable text streams from `.pdf`, `.docx`, `.txt`, `.csv`, `.json`, `.md`, `.log`, and `.eml` files up to 5 MB (7,200 characters in the interactive preview) and sanitizes the text payload before it hits the LLM. Full binary PDF redaction or OCR on scanned images is a separate document-pipeline step we scope during a pilot."*

- **"What if the file is huge—say a 200-page PDF manual or contract?"**
  > *"For prompt-sized files, inline extraction + gateway tokenization is fastest and stateless. For large multi-document repositories, the production pattern is an ingestion chunker that calls AnonReq's anonymization stage per chunk before embedding into a vector DB (Sanitized RAG), so neither the embeddings nor the upstream LLM ever hold raw PII."*

- **"Is every sensitive value guaranteed to be detected?"**
  > *"No NLP/regex detector is 100%. We combine deterministic checksum/regex recognizers for structured German identifiers (`IBAN_DE`, `TAX_ID_DE`, `KVNR`, `PERSONAL_AUSWEIS`) with spaCy `de_core_news_lg` NER for names and addresses, and tune exclusions (`mnpi_recognizers.yaml`) per tenant. Our 30-day PoC specifically measures recall and precision on your synthetic documents."*

- **"Why not just run a local open-weight model?"**
  > *"Local models require heavy GPU infrastructure and still risk memorizing or echoing PII across multi-tenant logs, agent tool calls, and observability traces. AnonReq runs on CPU inside your VPC, gives you frontier reasoning (`grok-4`, OpenAI, Anthropic, Gemini) through a single OpenAI-compatible `/v1/chat/completions` endpoint, and keeps PII out of both the model provider and your OTEL traces."*
