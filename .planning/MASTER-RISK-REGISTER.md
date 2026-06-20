# AnonReq Master Risk Register

| Risk | Impact | Likelihood | Mitigation | Owner |
|---|---:|---:|---|---|
| Detection false negative sends sensitive data | Critical | Medium | Benchmark thresholds, DLP layering, policy gates, fairness datasets, red-team tests | Security |
| Cache outage blocks production traffic | High | Medium | HA Valkey, fail-secure 503, SLO alerting, DR drills | SRE |
| Logs contain raw content | Critical | Low | Field allowlist, property tests, UI/export allowlists, code review gates | Security |
| Tenant data leak | Critical | Low | Context-derived keys, authz filters, concurrent isolation tests | Platform |
| Provider adapter schema drift | High | Medium | Contract tests, provider mocks, OpenAPI source of truth, feature flags | Platform |
| Transparent proxy certificate misuse | Critical | Low | Tenant-managed CA, explicit acknowledgement, HSM/encrypted storage, audit | Security |
| Compliance evidence drift | Medium | Medium | Traceability CI, evidence manifests, release checklist | Compliance |
| Performance misses SLO | High | Medium | k6 budgets, profiling, backpressure, capacity model | SRE |
