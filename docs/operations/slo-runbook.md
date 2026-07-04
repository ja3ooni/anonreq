# SLO Runbook

## Overview
AnonReq tracks 4 Service Level Objectives (SLOs) to ensure the operational safety, compliance, and latency performance of the anonymization gateway:
- **Success Rate**: target ≥99.9%
- **P95 Latency**: target ≤100ms
- **Fail-Secure Rate**: target ≤0.1%
- **Audit Write Rate**: target ≥99.99%

## SLO Windows
- **Fixed calendar windows**: daily (aligned to UTC day boundaries), monthly (aligned to UTC calendar months)
- **Rolling windows**: 24h, 30d

## Observability Dashboards
- **Grafana URL**: [http://localhost:3000](http://localhost:3000) (Dashboard: SLO Compliance)
- **Prometheus URL**: [http://prometheus:9090](http://prometheus:9090)

## Breach Response Procedures

When an SLO breach occurs, immediate webhook alerts are fired, and details are logged in the audit trail. Operations personnel should follow these steps:

| SLO | Severity | Root Cause Investigation | Remediation Action |
|-----|----------|--------------------------|--------------------|
| **Success Rate < 99.9%** | Critical | 1. Check upstream LLM provider API status.<br>2. Inspect Valkey connectivity and CPU load.<br>3. Check error counts in gateway logs. | 1. Failover to secondary/fallback provider.<br>2. Restart Valkey or scale resources. |
| **P95 Latency > 100ms** | Warning | 1. Check system resource utilization (CPU/Memory).<br>2. Inspect database and network connection pools.<br>3. Verify upstream provider latency. | 1. Scale gateway instances.<br>2. Adjust pool limits or connection timeouts. |
| **Fail-Secure Rate > 0.1%** | Critical | 1. Check Presidio Analyzer endpoint and container health.<br>2. Review pipeline sanitization exceptions. | 1. Reboot Presidio service.<br>2. Check version compatibility and regex compiles. |
| **Audit Write Rate < 99.99%** | Critical | 1. Verify PostgreSQL database status.<br>2. Check PostgreSQL disk space and I/O limits. | 1. Clean up old logs or extend storage volume.<br>2. Restart database container if deadlocked. |

## Verification and Diagnostics Commands

### 1. Query Real-Time SLO Status
Run from any administrative machine with the gateway API key:
```bash
curl -H "Authorization: Bearer <ADMIN_API_KEY>" \
     -H "X-AnonReq-Role: administrator" \
     http://localhost:8080/v1/governance/status
```

### 2. Query Recent Breaches
```bash
curl -H "Authorization: Bearer <ADMIN_API_KEY>" \
     -H "X-AnonReq-Role: administrator" \
     http://localhost:8080/v1/governance/breaches
```

### 3. Check Webhook Dead Letter Queue (DLQ)
If webhook alerts fail to deliver (e.g. downstream alert receiver offline), check the Valkey DLQ:
```bash
redis-cli LRANGE breach_dlq:default 0 -1
```

## Escalation Path
1. **L1 Operations**: Verify alerts, check service health, attempt automatic restarts.
2. **L2 Reliability (SRE)**: Scale containers, adjust connection pool limits, coordinate fallback routing.
3. **L3 Security Engineering**: Address any PII leaks or cryptographic chain integrity failures.
