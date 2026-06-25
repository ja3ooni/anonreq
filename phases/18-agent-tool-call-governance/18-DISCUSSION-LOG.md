# Phase 18: Agent & Tool Call Governance - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md.

**Date:** 2026-06-20
**Phase:** 18-agent-tool-call-governance
**Areas discussed:** Tool Policies, Enforcement Point, Approval Model, Tool Result Inspection

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
