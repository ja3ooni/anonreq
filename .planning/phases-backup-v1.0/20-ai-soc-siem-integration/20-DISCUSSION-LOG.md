# Phase 20: AI SOC / SIEM Integration — Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md.

**Date:** 2026-06-26
**Phase:** 20-ai-soc-siem-integration
**Areas discussed:** Single vs Multi Gateway, Event Sources, SIEM Sinks, Event Format, Buffer/Retry, MITRE Mapping, Health Monitoring, Secret Management, Sink Configuration, No-Raw-Content Enforcement

---

## Single vs Multi Gateway
| Option | Selected |
|--------|----------|
| Single gateway, SOC is output sink layer | ✓ |
| Separate SOC gateway process | |
| Separate SOC appliance | |

**User's choice:** Single gateway. Everything routes through Phase 9 Content-Type Dispatcher. Phase 20 is output sink layer only.

## Event Sources
| Option | Selected |
|--------|----------|
| All security events (firewall, DLP, shadow AI, MNPI, prompt security, classification, governance) | ✓ |
| Only critical security events | |
| All audit log events | |

**User's choice:** All security events from Phases 10, 13, 12, 8, 17, 18. Consumed via internal event bus.

## SIEM Sinks
| Option | Selected |
|--------|----------|
| Splunk HEC, QRadar CEF, Sentinel DCR, Elastic Bulk, Datadog Logs, Generic Webhook | ✓ |
| Splunk + QRadar only | |
| All major + syslog fallback | |

**User's choice:** 6 output sinks. Generic webhook for custom SIEM.

## Event Format
| Option | Selected |
|--------|----------|
| Normalized event → per-sink format transformation | ✓ |
| Single JSON format for all sinks | |
| Raw events forwarded directly | |

**User's choice:** Normalized internal format, then transformed per sink format. No raw content.

## No-Raw-Content Enforcement
| Option | Selected |
|--------|----------|
| Strip at normalizer + fail-secure drop if content detected | ✓ |
| Trust source engines to not emit content | |
| Strip at sink formatter only | |

**User's choice:** Enforce at normalizer. If content field detected, drop event + emit `soc_strip_failure`.

## Buffer & Retry
| Option | Selected |
|--------|----------|
| In-memory, max 10,000 per sink, LRU eviction, exponential backoff | ✓ |
| In-memory, unbounded | |
| Persistent buffer (disk/Redis) | |
| No buffer, drop on failure | |

**User's choice:** In-memory per-sink buffer, max 10,000, LRU eviction. Exponential backoff with jitter. Never block request processing.

## MITRE Mapping
| Option | Selected |
|--------|----------|
| Dedicated mitre-mapping.yaml config file | ✓ |
| Hardcoded in event normalizer | |
| Embedded in source engine audit events | |

**User's choice:** Dedicated config file. Applied at normalizer stage.

## Health Monitoring
| Option | Selected |
|--------|----------|
| GET /v1/admin/soc/integration/status with periodic probes | ✓ |
| Passive (infer from delivery success/failure) | |
| External monitoring tool only | |

**User's choice:** Active periodic probes per sink + status endpoint. RBAC-protected.

## Secret Management
| Option | Selected |
|--------|----------|
| `$env:VAR_NAME` / `$file:/path` references in YAML | ✓ |
| Secrets in config YAML inline | |
| External secrets manager (HashiCorp Vault) | |

**User's choice:** References in YAML, resolved at load time. Deferred Vault integration.

## Sink Configuration
| Option | Selected |
|--------|----------|
| soc-sinks.yaml loaded at startup | ✓ |
| Per-sink env variables | |
| Admin API for sink management | |

**User's choice:** YAML config file. Hot-reload deferred.

## Generic Webhook
| Option | Selected |
|--------|----------|
| Configurable payload template (Jinja2 subset) | ✓ |
| Fixed JSON schema | |
| Raw event passthrough | |

**User's choice:** Templatable payload. Jinja2 subset for flexibility.
