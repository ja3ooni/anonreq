# AnonReq Operations Guide

This guide provides operational runbooks, configuration structures, monitoring specifications, and troubleshooting steps for system operators managing the AnonReq gateway.

## Configuration Management

The gateway configurations are managed via YAML files loaded at container startup. The main configurations are:

- **Policy Engine (`config/policy.yaml`):** Defines tenant rules, rate limits, spend budgets, and residency boundaries.
- **SLO Configuration (`config/slo.yaml`):** Declares operational targets for success rate, latencies, fail-secure states, and audit writes.
- **Trust Center (`config/trust_center.yaml`):** Gates public compliance portals and display metadata.

Configurations are hot-reloaded automatically on receiving a `SIGHUP` signal.

### Policy Configuration Example

```yaml
version: "1.0"
rules:
  - rule_id: "block_restricted_pii"
    name: "Block Restricted Data"
    action: "BLOCK"
    priority: 100
    enabled: true
    conditions:
      classification_level: "Restricted"
rate_limits:
  enabled: true
  rpm: 1000
```

## Monitoring Service Level Objectives (SLOs)

AnonReq tracks 4 primary SLOs to guarantee system safety and performance:

1. **Success Rate:** ≥99.9% of gateway requests must succeed.
2. **P95 Latency:** Processing overhead must remain ≤100ms.
3. **Fail-Secure Rate:** ≤0.1% of transactions should trigger fail-secure blocks.
4. **Audit Write Rate:** ≥99.99% of audit log writes must complete successfully.

### Observability Infrastructure

- **Prometheus Dashboard:** Scrapes metrics from `/metrics` on port `8080`.
- **Grafana Dashboard:** Visualizes SLO compliance targets and error budgets.

## Administrative CLI Operations

System operators use curl requests to query status, fetch metrics, and perform updates.

### 1. Check Active Policies
```bash
curl -X GET http://localhost:8080/v1/admin/policies \
  -H "Authorization: Bearer <ADMIN_API_KEY>" \
  -H "X-AnonReq-Role: operator" \
  -H "X-AnonReq-Tenant-ID: default"
```

### 2. Query Real-Time SLO Compliance
```bash
curl -H "Authorization: Bearer <ADMIN_API_KEY>" \
     -H "X-AnonReq-Role: administrator" \
     http://localhost:8080/v1/governance/status
```

### 3. Verify Cryptographic Audit Chain Integrity
```bash
curl -X POST http://localhost:8080/v1/governance/audit/verify \
  -H "Authorization: Bearer <ADMIN_API_KEY>" \
  -H "X-AnonReq-Role: administrator"
```

## Troubleshooting and Breach Recovery

When an SLO is breached, the gateway automatically issues alerts. Operators should check the following subsystems:

- **Success Rate drop:** Verify network connectivity to upstream LLM providers (OpenAI/Gemini) and inspect local Valkey resource consumption.
- **Latency spikes:** Check CPU/Memory load on the gateway containers and scale instances as necessary.
- **Fail-Secure rate increase:** Inspect the logs to verify if Microsoft Presidio Analyzer container is responding or if custom regex patterns are failing to compile.
- **Audit Write failures:** Inspect Valkey connectivity or the SQL database connection pool capacity. Check for deadlocks or storage volume depletion.
