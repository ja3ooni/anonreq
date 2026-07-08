# Phase 17 Architecture: Universal AI Traffic Gateway

## Deployment Topologies
```
Reverse Proxy:
  Client → Gateway → Provider (Docker Compose, direct)

Transparent Proxy:
  Client → (PAC) → Gateway (MITM TLS) → Provider
  Client CA cert installed → Gateway terminates + re-originates

Virtual Appliance:
  [VM/AMI] → Docker Compose + systemd + management agent
```

## Traffic Detection Layers
```
1. PAC File: Browser/OS auto-config → gateway
2. Hostname Allowlist: DNS/IP match → known AI providers
3. Flow Analysis: Pattern detection → unidentified AI traffic
      ↓
Policy Rule (Phase 8): source != proxy AND dest = AI provider → BLOCK
```

## Performance Targets
| Metric | Target | Mode |
|--------|--------|------|
| P50    | < 2ms | Proxy-only |
| P95    | < 5ms | Proxy-only |
| P99    | < 10ms | Proxy-only |

## Modes
```
Proxy-only:   routing + TLS + audit only (no detection/anon)
Full:         proxy + policy + detection + anonymization + restoration
```
