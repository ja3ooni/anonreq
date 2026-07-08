# Operations Runbook — AnonReq v1.0

## Startup Sequence

```bash
# Step 1: Verify configuration
test -f .env && echo ".env found" || echo "ERROR: .env missing"
grep -q "ANONREQ_API_KEY" .env && echo "API key set" || echo "ERROR: API key missing"

# Step 2: Pull latest images
docker compose pull

# Step 3: Start all services
docker compose up -d --build

# Step 4: Wait for healthy (poll every 10s, max 90s)
for i in $(seq 1 9); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null)
  if [ "$STATUS" = "200" ]; then
    echo "✓ All services healthy after ${i}0s"
    break
  fi
  echo "Waiting... (${i}0s)"
  sleep 10
done

# Step 5: Verify with test request
curl -s -H "Authorization: Bearer $ANONREQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4","messages":[{"role":"user","content":"Hello, my email is test@example.com"}]}' \
  http://localhost:8000/v1/chat/completions
```

**Expected output (Step 5):** JSON response with restored content (original email appears in response).

## Shutdown Sequence

### Graceful Shutdown
```bash
# Send SIGTERM to all services
docker compose stop

# Verify no in-flight requests (wait for drain)
sleep 5
docker compose ps  # All should show "exited (0)"
```

### Force Shutdown (Emergency)
```bash
# Immediate shutdown — discards all in-flight requests
docker compose down

# Note: Valkey data loss is intentional (ephemeral by design).
# In-flight token mappings are lost; sessions cannot be resumed.
```

## Health Check Endpoints

### `GET /health`

Aggregate health status for all dependencies.

**Response 200:**
```json
{
  "status": "pass",
  "version": "1.0.0",
  "checks": {
    "presidio": "pass",
    "valkey": "pass",
    "api_key_configured": true,
    "uptime_seconds": 3600
  }
}
```

**Response 503 (degraded):**
```json
{
  "status": "fail",
  "version": "1.0.0",
  "checks": {
    "presidio": "fail",
    "valkey": "pass",
    "error": "Presidio Analyzer unreachable at http://presidio-analyzer:5001"
  }
}
```

### `GET /metrics`

Prometheus metrics endpoint.

| Metric | Type | Description |
|--------|------|-------------|
| `anonreq_requests_total` | Counter | Total requests by status and provider |
| `anonreq_detection_latency_ms` | Histogram | PII detection latency in ms |
| `anonreq_fail_secure_events_total` | Counter | Fail-secure events by trigger |
| `anonreq_entities_detected_total` | Counter | Entities detected by type |
| `anonreq_cache_health` | Gauge | Cache health (1 = healthy, 0 = unhealthy) |
| `anonreq_audit_write_failures_total` | Counter | Audit log write failures |
| `anonreq_unrestored_tokens_total` | Counter | Tokens not restored in response |

### Valkey Health
```bash
docker compose exec valkey redis-cli -a $ANONREQ_CACHE_PASSWORD ping
# Expected: PONG
```

### Presidio Health (via Gateway)
```bash
# Internal — gateway probes presidio automatically.
# Check via gateway health endpoint:
curl -s http://localhost:8000/health | python3 -c "import sys,json; print(json.load(sys.stdin)['checks']['presidio'])"
```

## Log Interpretation

### Log Format
```json
{
  "timestamp": "2026-07-02T12:00:00.123456Z",
  "level": "INFO",
  "event": "request_processed",
  "session_id": "sess_abc123",
  "tenant_id": "tenant_001",
  "component": "gateway",
  "latency_ms": 245,
  "entity_count": 3,
  "provider": "openai",
  "status_code": 200
}
```

### Log Levels

| Level | Usage | Operational Guidance |
|-------|-------|---------------------|
| DEBUG | Detailed diagnostic info | Enable during development or incident investigation only |
| INFO | Normal operational events | Monitor for request volume trends |
| WARNING | Degraded but functioning | Investigate within business hours |
| ERROR | Operation failed | Respond within 1 hour during business hours |
| CRITICAL | System may be compromised | Respond immediately, 24/7 |

### Important Events

| Event | Level | Meaning | Action |
|-------|-------|---------|--------|
| `fail_secure_triggered` | CRITICAL | Detection/cache/timeout failure blocked data from upstream | Investigate root cause; check dependency health |
| `detection_engine_unhealthy` | ERROR | Presidio unreachable or returning errors | Restart presidio container; check model loading |
| `cache_unreachable` | ERROR | Valkey connection failed | Check valkey container; verify `ANONREQ_CACHE_URL` |
| `forwarding_guard_blocked` | CRITICAL | SanitizedEnvelope validation failed | Immediate investigation — potential data leak vector |
| `residual_token_found` | WARNING | Token pattern found in response post-restoration | Check restoration engine; verify Tail_Buffer FSM |
| `provider_timeout` | ERROR | LLM provider request timed out | Increase timeout; check provider status |
| `auth_failure` | INFO | Invalid bearer token | Monitor for brute force attempts |
| `classification_blocked` | INFO | Request blocked by classification rules | Review BLOCK rules in config |

### Example Log Entries

**Normal operation:**
```json
{"timestamp":"2026-07-02T12:00:00Z","level":"INFO","event":"request_processed","session_id":"sess_abc123","latency_ms":245,"entity_count":3,"provider":"openai","status_code":200}
```

**Fail-secure triggered:**
```json
{"timestamp":"2026-07-02T12:00:05Z","level":"CRITICAL","event":"fail_secure_triggered","session_id":"sess_def456","trigger":"detection_unhealthy","forwarded":false,"cleanup_success":true}
```

**Cache unreachable:**
```json
{"timestamp":"2026-07-02T12:00:10Z","level":"ERROR","event":"cache_unreachable","error":"Connection refused","component":"valkey"}
```

## Restart Procedures

### Individual Container Restart

```bash
# Restart single service (zero-downtime for gateway if multi-replica)
docker compose restart anonreq

# Verify post-restart
curl -s http://localhost:8000/health
```

**When to use:** Single component failure (e.g., presidio OOM, valkey timeout).

### Full Stack Restart

```bash
# Full restart — all sessions lost
docker compose down
docker compose up -d

# Verify all services
docker compose ps
curl -s http://localhost:8000/health
```

**When to use:** Config change (new env vars), persistent errors across components, after deploy.

## Valkey Operations

### Ephemeral Constraint

Valkey runs with `save ""` — no RDB snapshots, no AOF log. All data exists only in memory for the session TTL duration. This is intentional for data privacy (no PII mappings persisted to disk).

```bash
# Verify persistence is disabled
docker compose exec valkey redis-cli CONFIG GET save
# Expected: save ""
```

### Monitoring

```bash
# Cache hit rate
docker compose exec valkey redis-cli INFO stats | grep hits

# Memory usage
docker compose exec valkey redis-cli INFO memory

# Connected clients
docker compose exec valkey redis-cli INFO clients

# Active sessions (keys)
docker compose exec valkey redis-cli DBSIZE

# List all session keys
docker compose exec valkey redis-cli KEYS "anonreq:*"
```

### Flushing Sessions

```bash
# Debug only — destroys all in-flight session mappings
docker compose exec valkey redis-cli FLUSHALL
# WARNING: All active sessions will fail to restore tokens
```

### Backup/Restore (if ever enabled)

If persistence is enabled (not default — requires config change):

```bash
# Manual snapshot (requires SAVE to be enabled)
docker compose exec valkey redis-cli SAVE
# dump.rdb is written to valkey's working directory

# Restore
# 1. Stop valkey: docker compose stop valkey
# 2. Copy dump.rdb to valkey data directory
# 3. Start valkey: docker compose start valkey
```
