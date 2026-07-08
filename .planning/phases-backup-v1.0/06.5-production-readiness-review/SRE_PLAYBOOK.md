# SRE Playbook — AnonReq v1.0

## Incident Severity Classification

| Severity | Label | Description | Response Time | Mitigation Time |
|----------|-------|-------------|---------------|-----------------|
| **S1** | Critical | Data exposure (PII leaked upstream), complete service unavailability, cache data corruption | 15 min acknowledgment | 60 min |
| **S2** | High | Partial degradation (streaming broken but non-streaming works), detection quality degradation, single-provider adapter failure | 30 min acknowledgment | 4 hrs |
| **S3** | Medium | Metrics unavailable, audit log missing non-critical events, single-tenant issue (multi-tenant future) | 4 hrs acknowledgment | Next business day |
| **S4** | Low | Documentation gaps, cosmetic issues, feature requests | Next business day | — |

## Incident Response Procedures

### S1 Procedure (Critical)

1. **Declare incident** — Notify on-call engineer via PagerDuty/Slack
2. **Assemble response team** — On-call engineer + SRE lead
3. **Isolate** — If data exposure is suspected, stop forwarding immediately:
   ```bash
   docker compose stop anonreq
   # or disconnect from upstream:
   docker network disconnect anonreq-net anonreq
   ```
4. **Diagnose** — Check logs, metrics, and dependency health:
   ```bash
   docker compose logs --tail=100 anonreq
   curl -s http://localhost:8000/health
   curl -s http://localhost:8000/metrics
   ```
5. **Mitigate** — Apply fix (restart, rollback, config change)
6. **Verify** — Confirm mitigation via test request
7. **Post-mortem** — Within 48 hours, using template below

### S2 Procedure (High)

1. **Diagnose** — Identify scope:
   - Is it streaming-specific? → Check Tail_Buffer FSM logs
   - Is it provider-specific? → Check provider adapter logs
   - Is it locale-specific? → Check locale recognizer configuration
2. **Triage checklist:**
   - [ ] Check if issue is reproducible with a test request
   - [ ] Review recent config changes
   - [ ] Check all dependency health endpoints
   - [ ] Review recent deployment/rollout
3. **Apply fix** — Restart affected component or rollback config
4. **Verify** — Confirm fix with test cases
5. **Post-mortem** — Within 5 business days

### S3/S4 Procedure

1. **Log ticket** — Create issue with full context
2. **Schedule fix** — Assign to next sprint or maintenance window
3. **Verify** — Confirm resolution after fix deployed

## Escalation Paths

| Level | Contact | Method | Response SLO |
|-------|---------|--------|-------------|
| On-call engineer | — | PagerDuty / Slack | 15 min (S1) |
| SRE lead | — | Phone / Slack | 30 min |
| Engineering manager | — | Phone / Email | 1 hr |
| Security team | — | Slack / Email | Add to any S1 involving data exposure |

**Security incidents:** Add security team to any S1 involving potential data exposure.

*Contact details are placeholders — operator to fill in with actual contacts.*

## Monitoring Alert Responses

| Alert Name | Condition | Severity | Automated Response | Human Response | Recovery Verification |
|------------|-----------|----------|-------------------|----------------|----------------------|
| `fail_secure_event_rate_high` | > 5 fail-secure events in 5 min | S1 | Log incident | Investigate detection/cache health; check logs for pattern | Rate drops below threshold |
| `cache_unreachable` | Valkey health check fails | S1 | — | Check valkey container; verify network | Health check passes |
| `detection_latency_spike` | P95 detection latency > 500ms | S2 | — | Check presidio container resource usage | Latency returns to baseline |
| `residual_tokens_detected` | Any residual token found in response | S2 | — | Check restoration engine; review streaming path | Zero residual tokens |
| `provider_timeout_rate_high` | > 10% provider requests timeout in 5 min | S2 | — | Check provider status page; increase timeout | Timeout rate < 1% |
| `audit_write_failure` | Audit write fails | S3 | — | Check disk/logging setup | Audit writes succeeding |
| `health_check_failure` | /health returns non-200 | S1 | — | Investigate all dependencies | /health returns 200 |
| `high_memory_pressure` | Container memory > 85% for 5 min | S3 | — | Review scaling; restart if needed | Memory < 70% |

## Post-Mortem Template

```markdown
# Post-Mortem: {{INCIDENT_TITLE}}

**Date:** {{DATE}}
**Severity:** S{{N}}
**Duration:** {{DURATION}}
**Incident ID:** {{ID}}

## Summary

{{2-3 sentence overview of what happened and impact}}

## Impact

- {{affects, e.g., "15% of requests failed for 12 minutes"}}
- {{affected users/tenants}}

## Timeline

| Time (UTC) | Event |
|------------|-------|
| HH:MM | {{event}} |
| HH:MM | {{event}} |
| HH:MM | {{resolution}} |

## Root Cause

{{1-2 paragraph explanation of the root cause}}

## Detection

- **How was it detected?** {{alert / user report / manual check}}
- **Time to detection:** {{X minutes}}

## Response

- **Time to acknowledge:** {{X minutes}}
- **Time to mitigate:** {{X minutes}}
- **What worked well:** {{list}}
- **What could be improved:** {{list}}

## Resolution

{{steps taken to resolve}}

## Lessons Learned

### What went well
- {{item}}
- {{item}}

### What went wrong
- {{item}}
- {{item}}

### Where we got lucky
- {{item}}

## Action Items

| # | Action | Owner | Due Date |
|---|--------|-------|----------|
| 1 | {{action}} | @person | YYYY-MM-DD |
| 2 | {{action}} | @person | YYYY-MM-DD |

## Blamelessness Statement

This post-mortem is a blameless analysis of what happened, why it happened, and how to prevent recurrence. No individual is at fault for systemic issues.
```

---

## Docker Deployment Verification

### Prerequisites Checklist

- [ ] Docker Engine v24+ installed (`docker --version`)
- [ ] Docker Compose v2+ installed (`docker compose version`)
- [ ] Provider API keys generated:
  - [ ] OpenAI: `sk-...` from platform.openai.com
  - [ ] Anthropic: `sk-ant-...` from console.anthropic.com (if using)
  - [ ] Gemini: `AIza...` from aistudio.google.com (if using)
- [ ] `.env` file configured with API keys and `ANONREQ_API_KEY` (≥ 32 chars)
- [ ] Minimum 8 GB RAM available

### Verification Steps

| # | Step | Command | Expected Outcome | Pass/Fail |
|---|------|---------|-----------------|-----------|
| 1 | Start all services | `docker compose up -d --build` | All 3 containers start without errors | ☐ |
| 2 | Check service status | `docker compose ps` | All 3 services show "healthy" within 60 seconds | ☐ |
| 3 | Health endpoint | `curl http://localhost:8000/health` | HTTP 200, all dependencies "pass" | ☐ |
| 4 | Metrics endpoint | `curl http://localhost:8000/metrics` | HTTP 200, Prometheus-format metrics returned | ☐ |
| 5 | No-auth request | `curl http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"gpt-4","messages":[{"role":"user","content":"hi"}]}'` | HTTP 401 (no bearer token) | ☐ |
| 6 | Bad-auth request | `curl -H "Authorization: Bearer wrong" -H "Content-Type: application/json" -d '{"model":"gpt-4","messages":[{"role":"user","content":"hi"}]}' http://localhost:8000/v1/chat/completions` | HTTP 401 (invalid token) | ☐ |
| 7 | Valid auth, non-streaming | See below* | HTTP 200, response contains restored original values | ☐ |
| 8 | Valid auth, streaming | Same request with `"stream": true` | SSE stream, tokens restored in real-time | ☐ |
| 9 | No PII in logs | `docker compose logs anonreq \| grep -iE '(email\|ssn\|credit\|phone\|@\|\.com)'` | No matches (empty output) | ☐ |
| 10 | Valkey persistence disabled | `docker compose exec valkey redis-cli CONFIG GET save` | Returns `save ""` | ☐ |

*\*Step 7 test request:*
```bash
curl -s -H "Authorization: Bearer $ANONREQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "My email is alice@example.com and my phone is +1-555-123-4567"}
    ]
  }' \
  http://localhost:8000/v1/chat/completions
```

### Sign-Off

| Item | Value |
|------|-------|
| **Date** | |
| **Operator** | |
| **Environment** | |
| **AnonReq version** | |
| **Docker version** | |
| **Provider(s) tested** | |
| **Steps passed** | /10 |
| **Notes** | |

**Signature:** ________________________ **Date:** ________________

*All 10 verification steps must pass before signing off on production readiness.*
