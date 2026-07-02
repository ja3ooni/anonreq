# Phase 21 Architecture: Endpoint Visibility & Sovereign Control

## Content-Type Dispatcher Routing (Extended)

```
Inbound Request
      ↓
Network Interception Layer (Transparent Proxy)
  ├── Reverse Proxy (DEPLOYMENT_MODE=reverse)
  ├── Transparent Proxy (DEPLOYMENT_MODE=transparent) ← TLS intercept + DNS/iptables
  ├── Virtual Appliance (DEPLOYMENT_MODE=virtual)
  └── Physical Appliance (DEPLOYMENT_MODE=physical)
      ↓
AI Firewall (Phase 21) ← inline, before anything else, <20ms budget
  ├── Jailbreak detection
  ├── Injection detection
  ├── System prompt extraction detection
  └── HTTP 403 on block
      ↓
PDP #1
      ↓
Threat Engine (Phase 10)
      ↓
Content-Type Dispatcher (Phase 9) — extended types:
  ├── chat / completion          → Detection → Anonymization → Provider
  ├── rag                       → Detection → Anonymization → RAG pipeline
  ├── voice_stream              → Voice Pipeline (see below)
  ├── agent_tool_call           → Tool Call Inspection (see below)
  ├── agent_tool_result         → Tool Result Inspection (see below)
  └── mcp_message               → MCP Protocol Parsing (see below)
      ↓
Detection + Anonymization (Phase 2/9)
      ↓
Classification (Phase 12)
      ↓
DLP Engine (Phase 13)
      ↓
PDP #2 (Phase 8)
      ↓
ForwardingGuard → Provider Adapter → Provider → Restore → Client
```

## Transparent Proxy Flow

```
┌─────────────┐     DNS: api.openai.com → Appliance IP     ┌───────────────┐
│  Client App  │ ────────────────────────────────────────▶  │  AnonReq       │
│  (Chat UI,   │           or iptables REDIRECT 443        │  Appliance     │
│   CRM AI,    │ ◀────────────────────────────────────────  │                │
│   Desktop    │         TLS interception flow:            │  ┌───────────┐ │
│   Assistant) │         1. Client connects to              │  │ TLS       │ │
│              │            api.openai.com:443               │  │ Intercept │ │
│              │         2. DNS resolves → Appliance IP      │  │ Engine    │ │
│              │         3. Appliance does TLS handshake     │  │           │ │
│              │            presenting dynamic cert for       │  │ - Dynamic │ │
│              │            *.openai.com signed by            │  │   cert    │ │
│              │            enterprise CA                    │  │   gen     │ │
│              │         4. Appliance decrypts request       │  │ - CA cert │ │
│              │         5. Runs policy pipeline             │  │   loaded  │ │
│              │         6. Re-encrypts to upstream          │  │ - Pinning │ │
│              │            via TLS 1.3 outbound             │  │   detect  │ │
│              │                                            │  └───────────┘ │
│              │                                            └───────┬───────┘
│              │                                                    │
│              │                                            ┌───────▼───────┐
│              │                                            │  Upstream     │
│              │                                            │  API Provider │
│              │                                            │  (OpenAI,     │
│              │                                            │   Anthropic,  │
│              │                                            │   Gemini)     │
│              │                                            └───────────────┘
└─────────────┘

Non-AI Traffic (Fail_Closed default):
  - Cannot parse → HTTP 451 (blocked)
  - Certificate pinned → HTTP 451 (blocked)
  - Unknown protocol → HTTP 451 (blocked)

Non-AI Traffic (Fail_Open):
  - Cannot parse → forward untouched (pass-through)
  - Certificate pinned → log + forward untouched
```

## Voice Pipeline

```
┌──────────────┐     SIP/RTP / WebRTC / WebSocket / gRPC     ┌───────────────┐
│  Voice Bot   │ ──────────────────────────────────────────▶  │  AnonReq      │
│  or Meeting  │                                              │  Appliance    │
│  Assistant   │   Audio chunks (PCM, WAV, Opus)              │               │
│              │ ◀──────────────────────────────────────────  │               │
└──────────────┘                                              │  ┌─────────┐ │
                                                              │  │ Content │ │
                                                              │  │ Type    │ │
                                                              │  │ Dispat. │ │
                                                              │  │ voice   │ │
                                                              │  │ _stream │ │
                                                              │  └────┬────┘ │
                                                              │       │       │
                                                              │  ┌────▼────┐ │
                                                              │  │ STT     │ │
                                                              │  │ Engine  │ │
                                                              │  │ (Local  │ │
                                                              │  │ Whisper) │ │
                                                              │  │ GPU acc.│ │
                                                              │  └────┬────┘ │
                                                              │       │       │
                                                              │       │ text  │
                                                              │  ┌────▼────┐ │
                                                              │  │ Sliding │ │
                                                              │  │ Window  │ │
                                                              │  │ Detect. │ │
                                                              │  │ 500ms   │ │
                                                              │  └────┬────┘ │
                                                              │       │       │
                                                              │  ┌────▼────┐ │
                                                              │  │ Sensit. │ │
                                                              │  │ Entity  │ │
                                                              │  │ Found?  │ │
                                                              │  └────┬────┘ │
                                                              │   │No  │Yes  │
                                                              │   ▼    ▼     │
                                                      ┌───────┐  ┌──────────┐
                                                      │Forward│  │ Tokenize │
                                                      │text   │  │ text OR  │
                                                      │as-is  │  │ mute/    │
                                                      │       │  │ beep     │
                                                      │       │  │ audio    │
                                                      │       │  │ frame    │
                                                      └───────┘  └──────────┘
                                                              │       │       │
                                                              │  ┌────▼────┐ │
                                                              │  │ Outbound │ │
                                                              │  │ Stream   │ │
                                                              │  │ (text or │ │
                                                              │  │  audio)  │ │
                                                              │  └─────────┘ │
                                                              │               │
                                                              │  Latency:    │
                                                              │  <150ms P99  │
                                                              └───────────────┘

Connectors (configurable):
  - SIP trunk → SIP proxy insertion
  - WebRTC → media server integration
  - WebSockets → streaming API proxy
  - gRPC → bidirectional stream proxy
```

## Agent Governance Flow

```
┌──────────────┐    content_type: agent_tool_call     ┌───────────────┐
│  Agent       │ ───────────────────────────────────▶  │  AnonReq      │
│  Framework   │   {                                   │  Appliance    │
│  (LangChain, │     "tool_calls": [{                  │               │
│   CrewAI,    │       "function": {                   │  ┌─────────┐ │
│   AutoGPT)   │         "arguments": {...},           │  │ Content │ │
│              │         "name": "exec_sql"            │  │ Type    │ │
│              │       }]                              │  │ Dispat. │ │
│              │   }                                   │  │ agent_  │ │
│              │                                        │  │ tool_   │ │
│              │                                        │  │ call    │ │
│              │                                        │  └────┬────┘ │
│              │                                        │       │       │
│              │          Tool Call Inspection          │  ┌────▼────┐ │
│              │          ┌──────────────────┐          │  │ AI      │ │
│              │          │ Parse arguments  │          │  │ Firewall│ │
│              │          │  (JSON schema)   │          │  │ Scan    │ │
│              │          │                  │          │  │ argum.  │ │
│              │          │ ← Injection?     │──inject──▶  │ for     │ │
│              │          │ ← Malicious code?│          │  │ inject  │ │
│              │          │ ← Schema enforce │  clean   │  │ & code  │ │
│              │          └──────────────────┘          │  └────┬────┘ │
│              │                                        │       │       │
│              │          If clean: forward to tool     │  ┌────▼────┐ │
│              │          If injection: BLOCK (403)     │  │ Forward │ │
│              │                                        │  │ to Tool │ │
│              │                                        │  └─────────┘ │
│              │                                        └───────────────┘
│              │
│              │    content_type: agent_tool_result
│              │ ◀───────────────────────────────────
│              │   {                                  ┌───────────────┐
│              │     "tool_outputs": {                │  AnonReq      │
│              │       "result": "raw DB data...",    │  Appliance    │
│              │       "columns": ["name","salary"]   │               │
│              │     }                                │  ┌─────────┐ │
│              │   }                                  │  │ Content │ │
│              │                                        │  │ Type    │ │
│              │          Tool Result Inspection        │  │ Dispat. │ │
│              │          ┌──────────────────┐          │  │ agent_  │ │
│              │          │ Force through    │          │  │ tool_   │ │
│              │          │ Detection_Engine │          │  │ result  │ │
│              │          │                  │          │  └────┬────┘ │
│              │          │ Tokenize values  │          │       │       │
│              │          │ Preserve keys    │          │  ┌────▼────┐ │
│              │          │                  │          │  │ Detect. │ │
│              │          │ Redact errors    │          │  │ Engine  │ │
│              │          │ (stack traces,   │          │  │ PII/PHI │ │
│              │          │  internal IPs)   │          │  │ MNPI    │ │
│              │          │                  │          │  └────┬────┘ │
│              │          │ Emit audit event │          │       │       │
│              │          └──────────────────┘          │  ┌────▼────┐ │
│              │                                        │  │ Tokeniz.│ │
│              │          Tokenized result → LLM        │  │ Engine  │ │
│              │                                        │  │ Keys↦Keep│ │
│              │                                        │  │ Vals↦Tok│ │
│              │                                        │  └────┬────┘ │
│              │                                        │       │       │
│              │                                        │  ┌────▼────┐ │
│              │                                        │  │ Error   │ │
│              │                                        │  │ Redact. │ │
│              │                                        │  └─────────┘ │
│              │                                        └───────────────┘
```

## AI Firewall Placement

```
Inbound Request
      ↓
┌──────────────────────────────────────────────────────┐
│  AI Firewall (Phase 21) — <20ms budget               │
│                                                      │
│  ┌──────────────────────────────────────────┐        │
│  │ Classifier Pipeline                      │        │
│  │                                          │        │
│  │ 1. Structural analysis                   │        │
│  │    ├── Known jailbreak pattern DB        │        │
│  │    ├── System prompt override detection  │        │
│  │    └── Adversarial optimization sigs     │        │
│  │                                          │        │
│  │ 2. Semantic classification (local ONNX)  │        │
│  │    ├── Injection intent scoring          │        │
│  │    ├── Role manipulation detection       │        │
│  │    └── Code injection heuristics         │        │
│  │                                          │        │
│  │ 3. Decision: ALLOW / BLOCK               │        │
│  │    └── BLOCK → HTTP 403, audit, no spend │        │
│  └──────────────────────────────────────────┘        │
│                                                      │
│  ● MITRE ATLAS mapping: AML-T0018 (Prompt Injection)│
│  ● MITRE ATLAS mapping: AML-T0025 (Jailbreak)       │
└──────────────────────────────────────────────────────┘
      │ pass
      ▼
PDP #1 → Threat Engine → Content-Type Dispatcher → ...
```

## Deployment Topologies

### (a) Reverse Proxy Mode

```
┌──────────┐   base_url = appliance.internal:8080   ┌───────────┐
│  Client  │ ──────────────────────────────────────▶  │  AnonReq  │──▶ Upstream
│  Apps    │ ◀──────────────────────────────────────  │  Reverse  │
└──────────┘                                         │  Proxy    │
                                                     └───────────┘
```

### (b) Transparent Proxy Mode

```
┌──────────┐   DNS: *.openai.com → Appliance IP     ┌───────────┐
│  Client  │ ──────────────────────────────────────▶  │  AnonReq  │──▶ Upstream
│  Apps    │   iptables REDIRECT 443 to 8443         │  Transp.  │
│(no conf) │ ◀──────────────────────────────────────  │  Proxy    │
└──────────┘   TLS intercept + re-originate          │  + MITM   │
                                                     └───────────┘
```

### (c) Virtual Appliance

```
┌──────────────────────────────────────────────────────┐
│  Customer Hypervisor (VMware, Hyper-V, KVM)          │
│  ┌──────────────────────────────────────────────┐    │
│  │  AnonReq VM Image                            │    │
│  │  ├── 4 vCPU, 8GB RAM, 100GB disk             │    │
│  │  ├── HSM-backed CA storage                   │    │
│  │  ├── GPU passthrough (for STT)               │    │
│  │  └── Dual NIC: inside/outside                │    │
│  └──────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

### (d) Physical Appliance

```
┌──────────────────────────────────────────────────────┐
│  1U Rackmount Appliance                              │
│  ├── Intel Xeon D, 16 cores                         │
│  ├── 64GB ECC RAM, 2×NVMe 1TB (RAID1)               │
│  ├── Dual 25GbE SFP28 (management + data)           │
│  ├── TPM 2.0 / HSM for CA key storage               │
│  ├── NVIDIA L4 GPU (STT inference)                  │
│  └── Air-gapped: no outbound management             │
└──────────────────────────────────────────────────────┘
```

## Latency Budgets

```
Layer                     Budget (P99)     Measured From
────────────────────────────────────────────────────────
Transparent Proxy         5ms              First byte in → first byte out
(no detection pipeline)                    (Req 48 AC-5)

AI Firewall               20ms             Request received → ALLOW/BLOCK
                                           (Req 60 AC-5)

Voice Pipeline addition   150ms            Audio chunk in → sanitized chunk out
                                           (Req 58 AC-6)

Agent Governance          50ms             Tool call/result → decision/transform
(not set by requirements,  internal target)

Full pipeline             500ms            Request in → response out (includes
(total end-to-end)                         provider time excluded)
```
