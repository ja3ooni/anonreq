# Phase 12 Architecture: Data Classification & Handling Policies

## Flow

```
Incoming Request
      |
      v
Content-Type Dispatcher (Phase 9)
      |
      v
Detection Pipeline (Phase 2)
  Detected entities: [PERSON, EMAIL, API_KEY]
      |
      v
Classification Engine
  Input: detected entity types
  Logic: highest = max(entity_mapping[e] for e in entities)
  Output: { highest: "HIGHLY_RESTRICTED", labels: ["PERSON", "EMAIL", "API_KEY"] }
      |
      +-- Client-asserted X-AnonReq-Classification?
      |   Yes → take max(client_asserted, detected)
      |   No  → use detected
      |
      v
RequestContext.classification = result
      |
      v
Anonymization Engine (Phase 2)
      |
      v
PDP #2 (Phase 8)
  Consumes: classification level, entity labels
  Evaluates: per-level handling policy (default or YAML override)
  Actions: PASS, ANONYMIZE, ANONYMIZE+AUDIT, BLOCK
      |
      v
ForwardingGuard → Provider → Restore → Response
```

## Classification Levels
| Level | Aggregation | Default Action | Notes |
|-------|------------|----------------|-------|
| Public | max | PASS | No anonymization needed |
| Internal | max | PASS | Default for undetected |
| Confidential | max | ANONYMIZE | Standard anonymization |
| Restricted | max | ANONYMIZE + AUDIT | Extra audit flag |
| Highly Restricted | max | BLOCK (HTTP 451) | Blocked at PDP #2 |

## Highest-Sensitivity Algorithm
```
highest = max(entity_mapping[e] for e in detected_entities)
```
Deterministic. No AI. No confidence blending. All labels preserved.
