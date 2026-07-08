# Phase 18: Agent & Tool Call Governance - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md.

**Date:** 2026-06-26
**Phase:** 18-agent-tool-call-governance
**Areas discussed:** Tool Policies, Enforcement Point, Approval Model, Tool Result Inspection, Governance Model, Tool Isolation, Tool Risk Classification

---

## Tool Policies
| Option | Selected |
|--------|----------|
| Phase 8 policy YAML extension | ✓ |
| Dedicated tools config | |
| Phase 8 + tools section | |

**User's choice:** Phase 8 policy YAML extension (tools section).

## Enforcement Point
| Option | Selected |
|--------|----------|
| Before PDP #2 | |
| After PDP #2 | |
| Integrated into PDP #2 | ✓ |

**User's choice:** PDP #2 evaluates tool permissions.

## Approval Model
| Option | Selected |
|--------|----------|
| Async: suspend, queue, notify | ✓ |
| Synchronous block | |
| Async with polling endpoint | |

**User's choice:** Async. HTTP 202 + Phase 14 oversight queue. Polling endpoint.

## Tool Result Inspection
| Option | Selected |
|--------|----------|
| PII/sensitive data | |
| Reconstruction attempts | |
| Both | ✓ |

**User's choice:** Both.

## Governance Model
| Option | Selected |
|--------|----------|
| Per-tool policies | |
| Per-provider policies | ✓ |
| Both (provider + tool) | |

**User's choice:** Per-provider governance. Each provider (OpenAI, Anthropic, Gemini, Ollama) gets an independent governance policy defining tool availability, credential scope, and security context.

## Credential/Config Delegation
| Option | Selected |
|--------|----------|
| Global credentials per provider | |
| Per-delegation credentials | ✓ |
| Per-user credentials (future) | |

**User's choice:** Credentials, configuration, and scope provisioned on a per-delegation basis. Each tool invocation carries its own credential context to prevent cross-delegation leakage.

## Tool Domain Isolation
| Option | Selected |
|--------|----------|
| Unified tool registry | |
| Separate registries: model vs host | ✓ |
| Per-provider tool domains | |

**User's choice:** Strict isolation. Model MCP tools (defined by provider) and host tools (enterprise tools via MCP client) are in separate registries with separate credential stores, audit namespaces, and policies. Model tools never see host tools. Host tools never see model tools.

## Tool Risk Classification
| Option | Selected |
|--------|----------|
| Binary (allowed/blocked) | |
| 3-tier (low/medium/high) | |
| 4-tier (low/medium/high/critical) | ✓ |

**User's choice:** 4-tier risk classification. Low (read-only, allow), Medium (structured data, allow_with_audit), High (write/sensitive, audit or human approval), Critical (destructive, human approval or block).
