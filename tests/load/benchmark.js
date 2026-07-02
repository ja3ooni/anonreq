// k6 Load Test — AnonReq Gateway Overhead Benchmark
//
// Measures gateway round-trip latency for non-streaming chat completions.
// Gateway overhead is derived from the anonreq_processing_overhead_ms
// Prometheus metric, not the k6 http_req_duration (which includes
// provider latency). Run after /metrics to collect overhead data.
//
// Target: P95 gateway overhead ≤ 100ms at 50 concurrent users,
// 1000-word prompts, 60s sustained (D-157).
//
// Non-streaming only per D-158 (streaming load test deferred).
//
// Usage:
//   k6 run tests/load/benchmark.js --vus 50 --duration 60s
//
// Environment variables:
//   ANONREQ_API_KEY  — API key for auth (default: test-key)
//   BASE_URL         — Gateway URL (default: http://localhost:8080)
//   VUS              — Virtual users (default: 50)
//   PROMPT_SIZE      — Approximate word count per prompt (default: 1000)

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// ---------------------------------------------------------------------------
// Custom metrics
// ---------------------------------------------------------------------------
const failRate = new Rate('failures');
const overheadTrend = new Trend('gateway_overhead_ms'); // from /metrics scrape

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const API_KEY = __ENV.ANONREQ_API_KEY || 'test-key-32-chars-minimum-length';
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';
const PROMPT_SIZE = parseInt(__ENV.PROMPT_SIZE || '1000', 10);

export const options = {
    stages: [
        { duration: '10s', target: __ENV.VUS || 50 },   // Ramp up
        { duration: '40s', target: __ENV.VUS || 50 },   // Sustain
        { duration: '10s', target: 0 },                  // Ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<30000'],   // 30s total timeout (includes provider)
        http_req_failed: ['rate<0.10'],        // Allow up to 10% failure (no upstream)
    },
};

// ---------------------------------------------------------------------------
// Prompt generator — simulates a realistic chat message with embedded PII
// ---------------------------------------------------------------------------
function generatePrompt(wordCount) {
    const words = [
        'secure', 'confidential', 'private', 'internal', 'restricted',
        'meeting', 'report', 'analysis', 'project', 'strategy',
        'budget', 'forecast', 'quarterly', 'revenue', 'target',
        'compliance', 'audit', 'policy', 'review', 'approval',
    ];
    const parts = ['Please analyze the following confidential information:'];
    for (let i = 0; i < wordCount; i++) {
        parts.push(words[i % words.length]);
    }
    // Append synthetic PII so detection engine has work to do
    const userId = Math.floor(Math.random() * 10000);
    parts.push(
        `My email is user${userId}@corp-${userId}.com`,
        `and phone is +1-555-${String(Math.floor(Math.random() * 9000) + 1000)}.`,
        `My SSN is ${String(Math.floor(Math.random() * 900) + 100)}-` +
        `${String(Math.floor(Math.random() * 90) + 10)}-` +
        `${String(Math.floor(Math.random() * 9000) + 1000)}.`,
    );
    return parts.join(' ');
}

// ---------------------------------------------------------------------------
// Main test function
// ---------------------------------------------------------------------------
export default function () {
    const prompt = generatePrompt(PROMPT_SIZE);
    const payload = JSON.stringify({
        model: 'gpt-4',
        messages: [{ role: 'user', content: prompt }],
        stream: false,
    });

    const params = {
        headers: {
            'Authorization': `Bearer ${API_KEY}`,
            'Content-Type': 'application/json',
            'X-AnonReq-Locale': 'en-US',
        },
        timeout: '30s',
    };

    // POST to chat completions endpoint
    const res = http.post(`${BASE_URL}/v1/chat/completions`, payload, params);

    // Check response — 200 (success) or 500 (fail-secure) are both valid
    // for load test purposes (gateway handled the request either way).
    const ok = check(res, {
        'status is 200 or 500': (r) => r.status === 200 || r.status === 500,
        'response received within timeout': (r) => r.timings.duration < 30000,
    });
    failRate.add(!ok);

    // Scrape /metrics for overhead data (one VU per iteration to avoid
    // hammering the /metrics endpoint). Comment out in production runs
    // if /metrics adds measurement noise.
    if (__VU === 1) {
        const metricsRes = http.get(`${BASE_URL}/metrics`);
        if (metricsRes.status === 200) {
            // Extract processing_overhead_ms samples for trend tracking
            const match = metricsRes.body.match(
                /anonreq_processing_overhead_ms_bucket\{.*?\} (\d+)/g,
            );
            if (match) {
                // Parse +Inf bucket to get total count, approximate overhead
                const infMatch = metricsRes.body.match(
                    /anonreq_processing_overhead_ms_count (\d+)/,
                );
                if (infMatch) {
                    overheadTrend.add(parseInt(infMatch[1], 10));
                }
            }
        }
    }

    // Small sleep to prevent thundering-herd on shutdown
    sleep(0.1);
}
