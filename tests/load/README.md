# AnonReq Load Tests

This directory contains load test scripts for benchmarking the AnonReq gateway
under simulated production traffic.

## Prerequisites

- **[k6](https://k6.io/docs/getting-started/installation/)** installed (`brew install k6`)
- AnonReq gateway running with:
  - Prometheus metrics enabled (default)
  - A test provider configured (or Presidio-only mode)
  - `en_core_web_sm` Presidio model (fast inference, per D-142)

## Quick Start

```bash
# 50 concurrent users, 60s sustained
k6 run tests/load/benchmark.js --vus 50 --duration 60s
```

## Environment Variables

| Variable          | Default                      | Description                           |
|-------------------|------------------------------|---------------------------------------|
| `ANONREQ_API_KEY` | `test-key-32-chars-minimum-length` | Gateway API key for Bearer auth |
| `BASE_URL`        | `http://localhost:8080`      | Gateway base URL                      |
| `VUS`             | `50`                         | Concurrent virtual users              |
| `PROMPT_SIZE`     | `1000`                       | Approximate word count per prompt     |

## Interpreting Results

### Primary Target

**P95 gateway overhead ≤ 100ms at 50 concurrent users** (D-157).

Gateway overhead is **not** `http_req_duration` (which includes provider
round-trip time). To measure overhead:

1. After the load test run, scrape `/metrics`:
   ```bash
   curl -s http://localhost:8080/metrics | grep anonreq_processing_overhead_ms
   ```
2. The `anonreq_processing_overhead_ms` histogram shows gateway processing
   overhead in milliseconds. Look for the `+Inf` bucket count and `_sum`
   to compute actual overhead distribution.
3. Compare the `p95` value from k6's `http_req_duration` against the
   `anonreq_processing_overhead_ms` histogram — the difference is
   provider latency.

### k6 Output Metrics

| Metric              | What It Measures                        | Target                |
|---------------------|-----------------------------------------|-----------------------|
| `http_req_duration` | Total round-trip (gateway + provider)   | P95 < 30s             |
| `http_req_failed`   | Error rate (non-200/500 responses)      | < 10%                 |
| `failures`          | Custom failure rate (check failures)    | N/A (informational)   |

### When No Upstream Provider Is Available

Without a real provider backend, the gateway returns HTTP 500 (fail-secure).
This is expected behavior — the test still validates that:
- The gateway handles all requests without crashing
- `/metrics` returns accurate overhead data
- Middleware captures request counts

For true latency validation, run with a test provider stub or a mock
OpenAI-compatible endpoint.

## Scenarios

### Non-Streaming (MVP)

```bash
k6 run tests/load/benchmark.js --vus 50 --duration 60s
```

- 10s ramp-up → 40s sustained → 10s ramp-down
- 1,000-word prompts with synthetic PII
- Default model: `gpt-4`

### Streaming (Deferred — Phase 6+)

Streaming load test is deferred per D-158. The TailBuffer FSM adds overhead
that needs separate characterization.

### Custom Configuration

```bash
# Higher concurrency
k6 run tests/load/benchmark.js --vus 100 --duration 120s -e PROMPT_SIZE=500

# Against a different environment
k6 run tests/load/benchmark.js -e BASE_URL=https://staging.gateway.example.com
```

## Test Result Artifacts

Load test results are logged as build artifacts — **not a CI gate** in MVP
(D-159). Future phases may introduce threshold-based CI gates.

Output is written to stdout by default. To capture:

```bash
k6 run tests/load/benchmark.js --vus 50 --duration 60s \
  --summary-export=load-test-results.json
```

## Notes

- The load test measures **total gateway round-trip** using k6. Gateway
  overhead is derived from the Prometheus `anonreq_processing_overhead_ms`
  metric, not from k6's `http_req_duration`.
- Non-streaming only in MVP (D-158).
- Default Presidio model: `en_core_web_sm` (small, fast — adequate for
  latency benchmarks, per D-142).
- Synthetic PII in prompts ensures the detection engine has realistic work.
- Results should be compared against a baseline from the same environment
  for meaningful performance tracking.
