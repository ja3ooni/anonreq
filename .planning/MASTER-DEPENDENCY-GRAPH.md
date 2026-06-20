# AnonReq Master Dependency Graph

## Phase Dependencies

```mermaid
graph TD
  P01[01 Foundation] --> P08[08 Policy Engine]
  P01 --> P09[09 RBAC SSO]
  P02[02 Core Pipeline] --> P10[10 Tenant Isolation]
  P08 --> P11[11 Audit Compliance Center]
  P02 --> P12[12 DLP Advanced Detection]
  P09 --> P14[14 Admin Portal]
  P10 --> P14
  P11 --> P14
  P12 --> P13[13 Enterprise Connectors]
  P13 --> P15[15 Deployment Models]
  P15 --> P16[16 Performance Scale]
  P16 --> P17[17 Disaster Recovery]
  P11 --> P18[18 Trust Center]
  P19[19 SDK Ecosystem] --> P21[21 GA Release]
  P20[20 SOC2 ISO Readiness] --> P21
  P17 --> P21
  P18 --> P21
```

## Shared Technical Dependencies

FastAPI and Pydantic v2 define API contracts. Valkey is required before forwarding. PostgreSQL is required for durable enterprise metadata. OpenTelemetry, Prometheus, and structured logging are required before SLO and compliance reporting. OpenAPI schema stability is required before SDK release.
