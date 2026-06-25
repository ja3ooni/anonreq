# Phase 17: Universal AI Traffic Gateway - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md.

**Date:** 2026-06-20
**Phase:** 17-universal-ai-traffic-gateway
**Areas discussed:** TLS Interception, AI Traffic Detection, Appliance Model, Performance, MCP, CA Management, PAC, Enforcement Point

---

## TLS Interception
| Option | Selected |
|--------|----------|
| MITM with tenant CA | ✓ |
| PROXY protocol | |
| eBPF-based | |

**User's choice:** MITM with tenant CA.

## AI Traffic Detection
**User's choice:** 3 layers: PAC file + hostname allowlist + flow analysis.

## Appliance Model
| Option | Selected |
|--------|----------|
| Virtual only (VM/AMI) | ✓ |
| Virtual + physical | |
| Sidecar container | |

**User's choice:** Virtual appliance (same Docker Compose, packaged as VM).

## Performance
**User's choice:** P50 < 2ms, P95 < 5ms, P99 < 10ms. Gateway-internal timing. Proxy-only mode.

## MCP Handling
| Option | Selected |
|--------|----------|
| Pass-through | |
| Full MCP inspection | ✓ |
| Phase 9 extension | |

**User's choice:** Full MCP inspection.

## CA Management
**User's choice:** Admin API + file-based (dual path).

## PAC Distribution
**User's choice:** Gateway serves auto-generated PAC + admin API for customization.

## Enforcement Point
**User's choice:** Phase 8 policy engine rule (consistent with policy model).
