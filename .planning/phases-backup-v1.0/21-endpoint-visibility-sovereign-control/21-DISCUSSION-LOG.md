# Phase 21: Endpoint Visibility & Sovereign Control - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md.

**Date:** 2026-06-26
**Phase:** 21-endpoint-visibility-sovereign-control
**Areas discussed:** Single vs separate gateways, Transparent proxy architecture, Deployment topologies, Voice pipeline architecture, STT localization, Agent governance scope, AI Firewall approach, MITRE ATLAS vs ATT&CK, Fail-closed defaults, Active scanning opt-in

---

## Single Gateway vs Separate Gateways
| Option | Selected |
|--------|----------|
| Single gateway: all content types through Phase 9 Dispatcher | ✓ |
| Separate gateway instances per content type (chat, RAG, voice, agents) | |
| Hybrid: single proxy process, separate routing rules | |

**Reasoning:** Single gateway avoids operational complexity of managing multiple proxy instances, health checks, and configuration surfaces. The Phase 9 Content-Type Dispatcher already supports extensible routing — adding new content types is far cheaper than deploying and coordinating separate gateways. User confirmed this aligns with "Single `content_type` routing field."

## Transparent Proxy TLS Interception
| Option | Selected |
|--------|----------|
| iptables + dynamic TLS certs with enterprise CA | ✓ |
| eBPF-based interception only | |
| DNS proxy with static routing | |
| SOCKS proxy configuration | |

**Reasoning:** iptables provides universal Linux compatibility (all distros). eBPF is an optional high-performance path for supported kernels. DNS redirection alone is insufficient for TLS-level interception (no decryption capability). TLS interception with enterprise CA is the industry standard pattern (Zscaler, Netskope, Palo Alto).

## Deployment Topology Abstraction
| Option | Selected |
|--------|----------|
| Four explicit modes (reverse, transparent, VM, physical) | ✓ |
| Single mode with configurable network attachment | |
| Reverse+transparent only; VM/physical as deployment packaging | |

**Reasoning:** Four modes match Req 48 AC-2 explicitly. VM and physical are distinct from software deployment because they involve provisioning, HSM integration, and GPU passthrough. User confirmed all four are in scope.

## Voice Pipeline: Local STT vs Cloud STT
| Option | Selected |
|--------|----------|
| Local self-hosted Whisper (air-gapped) | ✓ |
| Configurable: local or cloud STT with explicit opt-in | |
| Cloud STT only with DPA in place | |

**Reasoning:** Req 50 AC-2 explicitly requires transcription "within the customer's perimeter" and "no audio shall be transmitted to an external transcription service unless explicitly configured and approved." Local Whisper is the default, with cloud STT as an opt-in alternative requiring explicit configuration.

## Voice Pipeline: Text vs Audio Sanitization Paths
| Option | Selected |
|--------|----------|
| Both: text tokenization AND audio muting/beeping | ✓ |
| Text-only: tokenize transcript, forward clean text | |
| Audio-only: mute frames, forward raw audio | |

**Reasoning:** Req 58 AC-4 (text tokenization) and Req 58 AC-5 (audio muting/beeping) are both required. Which path executes depends on whether the downstream service expects text or raw audio. The voice connector configuration specifies the output format.

## Agent Governance: MCP vs Native Tool Calls
| Option | Selected |
|--------|----------|
| Both: MCP protocol + native tool_calls/tool_outputs | ✓ |
| MCP only | |
| Native OpenAI/Anthropic tool calls only | |

**Reasoning:** Req 59 explicitly names MCP (Model Context Protocol) AND native function calls. These are different wire protocols reaching the same proxy endpoint. The Content-Type Dispatcher routes `mcp_message` differently from `agent_tool_call` — different parsers, same policy pipeline.

## AI Firewall: Local Classifier vs LLM-as-Judge
| Option | Selected |
|--------|----------|
| Local small-footprint classifier (ONNX) | ✓ |
| LLM-as-judge (gpt-4o-mini or similar) | |
| Hybrid: fast local + fallback LLM | |

**Reasoning:** LLM-as-judge creates recursive dependency (AI Firewall depends on external LLM to secure LLM access), adds latency (impossible to hit 20ms), and incurs model spend even for blocked requests. Local ONNX classifier is fast (<20ms), zero external dependency, zero marginal cost per request. User explicitly chose local classifier.

## MITRE ATLAS vs MITRE ATT&CK
| Option | Selected |
|--------|----------|
| Dedicated MITRE ATLAS mapping (separate from Phase 13 ATT&CK) | ✓ |
| Extend Phase 13 ATT&CK config to include ATLAS techniques | |
| No MITRE mapping for Phase 21 events | |

**Reasoning:** MITRE ATLAS is specific to AI adversarial threats. Phase 13 ATT&CK covers traditional enterprise threats. The techniques, tactics, and procedures are fundamentally different. Separate config file keeps each mapping clean. Both coexist in the audit system; events can carry both IDs where applicable.

## Fail-Closed Default
| Option | Selected |
|--------|----------|
| Default fail-closed; optional fail-open config | ✓ |
| Default fail-open; optional fail-closed config | |
| Always fail-closed, no config option | |

**Reasoning:** Fail-secure is a core AnonReq design constraint (AGENTS.md). Making fail-open optional and opt-in preserves the security posture while allowing operators to choose pass-through for non-AI traffic. Certificate-pinned traffic handling is the primary reason for fail-open: some operators may prefer logging over blocking.

## Active Network Scanning
| Option | Selected |
|--------|----------|
| No active scanning without explicit opt-in | ✓ |
| Active scanning enabled by default | |
| Passive discovery only (no scanning) | |

**Reasoning:** User explicitly directed: "No active scanning without opt-in." Active network scanning (Req 53 AI Network Discovery) is deferred to a later phase and will require clear operator consent due to potential network disruption risks.

## AI Firewall Position in Pipeline
| Option | Selected |
|--------|----------|
| AI Firewall inline BEFORE all processing (before PDP #1) | ✓ |
| AI Firewall between PDP #1 and Threat Engine | |
| AI Firewall as part of Threat Engine | |

**Reasoning:** Inline before all processing ensures blocked requests incur zero downstream cost — no detection pipeline, no model spend, no logs beyond the firewall audit event. Req 60 AC-1 explicitly requires execution "prior to launching the PII/DLP tokenization engines." This also aligns with the user's priority to "block at the perimeter."

## Content-Type Dispatcher Extension
| Option | Selected |
|--------|----------|
| Extend existing dispatcher with new content types | ✓ |
| New dispatcher instance for Phase 21 traffic | |
| Bypass dispatcher for agent/voice traffic | |

**Reasoning:** Single gateway requires single dispatcher. The Phase 9 dispatcher was designed for extensibility. New route handlers register alongside existing ones. No core dispatcher changes needed.
