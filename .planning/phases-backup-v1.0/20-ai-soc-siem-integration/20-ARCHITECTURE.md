# Phase 20 Architecture: AI SOC / SIEM Integration

## Position in Request Pipeline

Phase 20 is NOT in the request path. It is an output sink layer that consumes events from detection engines:

```
Inbound Request → PDP #1 → Phase 9 Dispatcher → Detection Pipeline → PDP #2 → Provider → Restore → Client
                                                        │
                                                        ▼
                                              ┌──────────────────────┐
                                              │  Event Sources        │
                                              │  (Phases 10, 13, 12, │
                                              │   8, 17, 18)         │
                                              └──────────┬───────────┘
                                                         │
                                                         ▼
                                              ┌──────────────────────┐
                                              │  Event Normalizer     │
                                              │  - Strip raw content  │
                                              │  - Apply MITRE IDs    │
                                              │  - Normalize format   │
                                              └──────────┬───────────┘
                                                         │
                                              ┌──────────▼───────────┐
                                              │  Sink Router          │
                                              │  (fan-out per sink)   │
                                              └──┬────┬────┬────┬────┘
                                                 │    │    │    │
                     ┌───────────────────────────┼────┼────┼────┼───────────┐
                     ▼              ▼              ▼              ▼         │
              ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
              │ Splunk   │  │ QRadar   │  │ Sentinel │  │ Elastic  │      │
              │ HEC      │  │ Syslog   │  │ DCR API  │  │ Bulk API │      │
              │ Sink     │  │ CEF Sink │  │ Sink     │  │ Sink     │      │
              └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘      │
                   │              │              │              │          │
              ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐     │
              │ Buffer   │  │ Buffer   │  │ Buffer   │  │ Buffer   │     │
              │ + Retry  │  │ + Retry  │  │ + Retry  │  │ + Retry  │     │
              └──────────┘  └──────────┘  └──────────┘  └──────────┘     │
                                                                          │
              ┌──────────┐                                               │
              │ Datadog  │◄──────────────────────────────────────────────┘
              │ Logs API │
              │ Sink     │
              └────┬─────┘
                   │
              ┌────▼─────┐
              │ Buffer   │
              │ + Retry  │
              └──────────┘

              ┌──────────┐
              │ Generic  │
              │ Webhook  │
              │ Sink     │
              └────┬─────┘
                   │
              ┌────▼─────┐
              │ Buffer   │
              │ + Retry  │
              └──────────┘
```

## Multi-Sink Architecture

```
                       ┌──────────────────┐
                       │  soc-sinks.yaml   │
                       │  (sink config)    │
                       └────────┬─────────┘
                                │ loads
                                ▼
              ┌─────────────────────────────────┐
              │      SOC Integration Service     │
              │                                  │
              │  ┌──────────────────────────┐    │
              │  │ Event Normalizer          │    │
              │  │  - Subscribes to event    │    │
              │  │    bus via asyncio.Queue  │    │
              │  │  - Strips content fields  │    │
              │  │  - Applies MITRE mapping  │    │
              │  │  - Produces NormalizedEvt │    │
              │  └──────────┬───────────────┘    │
              │             │                     │
              │  ┌──────────▼─────────────────┐  │
              │  │    Sink Router             │  │
              │  │  - Fan-out per sink        │  │
              │  │  - Per-sink background     │  │
              │  │    task with buffer+retry  │  │
              │  └────────────────────────────┘  │
              │                                  │
              │  ┌────────────────────────────┐  │
              │  │    Health Monitor          │  │
              │  │  - Periodic sink probes    │  │
              │  │  - Exposes /status endpoint│  │
              │  └────────────────────────────┘  │
              └──────────────────────────────────┘
```

## Buffer & Retry Flow

```
Normalized Event
       │
       ▼
┌──────────────────┐
│  Per-Sink Queue   │  ← asyncio.Queue(maxsize=10000)
│  (FIFO + LRU)     │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Retry Loop       │  ← background asyncio task
│                   │
│  attempt = 0      │
│  while event:     │
│    try:           │
│      send(event)  │
│      break        │
│    except:        │
│      attempt += 1 │
│      sleep(backoff│
│        (attempt)) │
│      if attempt== │
│        max:       │
│        drop event │
│        log overflow│
└──────────────────┘
       │
       ▼
   SIEM Sink
```

## Backoff Formula

```
backoff(attempt) = min(2^attempt * 1s, 60s) ± jitter(10%)
```

- Initial: 1s
- Multiplier: 2
- Max: 60s
- Jitter: ±10% uniform random
- Max retries: 5 (total ~63s before drop)

## Event Format Specification

### Normalized Event Schema

```json
{
  "severity": "high",
  "event_type": "dlp_violation",
  "tenant_id": "tenant-abc123",
  "session_id": "sess-f6a2b8c0",
  "timestamp": "2026-06-26T14:30:00.123456Z",
  "gateway_version": "1.5.0",
  "appliance_instance_id": "anonreq-prod-us-east-1a",
  "mitre_technique_id": "T1566.001",
  "metadata": {
    "dlp_category": "pii",
    "action_taken": "block",
    "confidence_score": 0.97
  }
}
```

### Sink-Specific Format Transformations

| Sink | Format | Content-Type |
|------|--------|-------------|
| Splunk HEC | JSON wrapped in HEC event envelope | application/json |
| QRadar | CEF:0|AnonReq|Appliance|1.0|{mitre_id}|{event_type}|{severity}| {fields} | syslog/TCP |
| Sentinel | JSON matching DCR stream schema | application/json |
| Elastic | Bulk action + index pairs (NDJSON) | application/x-ndjson |
| Datadog | JSON array of events | application/json |
| Webhook | Configurable JSON template | application/json (configurable) |

### QRadar CEF Format Example

```
CEF:0|AnonReq|Appliance|1.0|T1566.001|dlp_violation|High| \
  tenantId=tenant-abc123 sessionId=sess-f6a2b8c0 \
  applianceInstanceId=anonreq-prod-us-east-1a \
  gatewayVersion=1.5.0 \
  suser=tenant-abc123 msg=DLP violation: pii category blocked
```

### Splunk HEC Envelope Example

```json
{
  "time": 1719402600.123456,
  "host": "anonreq-prod-us-east-1a",
  "source": "anonreq",
  "sourcetype": "anonreq:ai_security",
  "event": {
    "severity": "high",
    "event_type": "dlp_violation",
    "tenant_id": "tenant-abc123",
    "session_id": "sess-f6a2b8c0",
    "gateway_version": "1.5.0",
    "appliance_instance_id": "anonreq-prod-us-east-1a",
    "mitre_technique_id": "T1566.001",
    "metadata": {
      "dlp_category": "pii",
      "action_taken": "block"
    }
  }
}
```

## MITRE Mapping Config Structure

```yaml
# config/mitre-mapping.yaml
event_type_mappings:
  prompt_injection_blocked:
    mitre_id: T1566.001
    framework: ATT&CK
    technique: Phishing: Spearphishing Attachment
  jailbreak_flagged:
    mitre_id: T1566.002
    framework: ATT&CK
    technique: Phishing: Spearphishing Link
  dlp_violation:
    mitre_id: T1048
    framework: ATT&CK
    technique: Exfiltration Over Alternative Protocol
  dlp_exfiltration_detected:
    mitre_id: T1048.003
    framework: ATT&CK
    technique: Exfiltration Over Unencrypted Non-C2 Protocol
  shadow_ai_detected:
    mitre_id: T1213.002
    framework: ATT&CK
    technique: Data from Information Repositories: Sharepoint
  mnpi_detected:
    mitre_id: AML.T0025
    framework: ATLAS
    technique: Exfiltration from AI System
  firewall_violation:
    mitre_id: T1190
    framework: ATT&CK
    technique: Exploit Public-Facing Application
  classification_blocked:
    mitre_id: T1530
    framework: ATT&CK
    technique: Data from Cloud Storage
  governance_action_applied:
    mitre_id: AML.T0043
    framework: ATLAS
    technique: Model Access via Compromised Credentials
```
