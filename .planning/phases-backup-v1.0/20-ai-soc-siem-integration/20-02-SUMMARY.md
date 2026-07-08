---
phase: 20-ai-soc-siem-integration
plan: 02
subsystem: soc-sinks
tags: [splunk, hec, qradar, cef, tcp, syslog, httpx, respx, prometheus]
requires:
  - phase: 20-01
    provides: SOCNormalizer, NormalizedEvent, SeverityLevel, MITREMapper, SOCConfig
provides:
  - SinkBase abstract protocol for all SIEM sink implementations
  - SinkStatus dataclass and SinkHealth enum for per-sink health monitoring
  - SinkRouter fan-out for distributing normalized events to all registered sinks
  - SplunkHECSink — HEC JSON envelope formatter with HTTP POST delivery
  - QRadarCEFSink — CEF:0|AnonReq|Appliance|... formatter with TCP/UDP syslog delivery
  - Prometheus counters per sink (anonreq_soc_sink_splunk_hec_total, anonreq_soc_sink_qradar_cef_total)
affects: [20-03, 20-04, 20-05, 20-TEST-PLAN]

tech-stack:
  added:
    - httpx (already present, used for HEC HTTP POST)
    - respx (already present, used for HTTP mocking)
  patterns:
    - SinkBase runtime-checkable protocol for sink abstraction
    - Per-sink Prometheus counters with sink_name label
    - SinkRouter fan-out with independent per-sink error isolation

key-files:
  created:
    - src/anonreq/soc/sinks/__init__.py
    - src/anonreq/soc/router.py
    - src/anonreq/soc/sinks/splunk_hec.py
    - src/anonreq/soc/sinks/qradar_cef.py
    - tests/test_soc_sink_splunk_hec.py
    - tests/test_soc_sink_qradar_cef.py
  modified: []

key-decisions:
  - "CEF severity mapping per plan spec: informational→3, low→4, medium→6, high→8, critical→10"
  - "SinkRouter registered as normalizer callback (register_sink_callback) for integration — wiring deferred to Plan 20-05"
  - "CEF header uses 7 pipe-delimited fields with space separator before extensions (standard CEF format, no trailing pipe)"
  - "Splunk HEC consumer index parameter omitted — index set server-side via Splunk configuration"

patterns-established:
  - "SinkBase protocol: start/stop/send_event/health_check/format_event lifecycle"
  - "SinkRouter provides single registration point with independent per-sink error isolation"
  - "Per-sink Prometheus Counter with sink_name label for per-instance metrics"
  - "respx HTTP mocking for Splunk HEC tests"
  - "asyncio.start_server TCP echo server for QRadar syslog tests"

requirements-completed: [APPL-09/Req56]

duration: 28min
completed: 2026-07-05
status: complete
---

# Phase 20 Plan 02: Splunk HEC + QRadar CEF SIEM Sinks

**SinkBase protocol, SinkRouter fan-out, Splunk HEC envelope formatter with HTTP POST delivery, and QRadar CEF formatter with TCP/UDP syslog delivery — 17 tests passing**

## Performance

- **Duration:** 28 min
- **Started:** 2026-07-05T14:40:00Z
- **Completed:** 2026-07-05T15:08:00Z
- **Tasks:** 3
- **Tests:** 17 (8 Splunk HEC + 9 QRadar CEF)

## Accomplishments

- Created SinkBase runtime-checkable protocol with SinkStatus/SinkHealth abstractions
- SinkRouter with register/fan_out/get_sinks/start_all/stop_all lifecycle
- SplunkHECSink formats events as HEC JSON envelopes with `sourcetype: anonreq:ai_security`, authenticates via `Authorization: Splunk {token}`, handles batch sends and health checks
- QRadarCEFSink formats events as `CEF:0|AnonReq|Appliance|` with ArcSight camelCase extensions, delivers over TCP (with auto-reconnect) and UDP syslog
- CEF special character escaping (backslash, equals, pipe)
- Prometheus counters per sink for operational monitoring
- All 17 sink tests pass; all 43 SOC tests pass (11 MITRE + 15 normalizer + 17 sinks)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create SinkBase abstract class and SinkRouter** - `9eff533` (feat)
2. **Task 2: Implement Splunk HEC sink** - `dd87a46` (feat) — TDD (RED + GREEN)
3. **Task 3: Implement QRadar CEF sink** - `170e8d9` (feat), `dac98bd` (fix) — TDD (RED + GREEN + fix severity mapping)

**Plan metadata:** (committed as part of plan execution tracking)

## Files Created/Modified

- `src/anonreq/soc/sinks/__init__.py` - SinkBase protocol, SinkStatus dataclass, SinkHealth enum (210 lines)
- `src/anonreq/soc/router.py` - SinkRouter with register/fan_out/get_sinks lifecycle management
- `src/anonreq/soc/sinks/splunk_hec.py` - SplunkHECSink with HEC envelope format, HTTP POST, batch send, health check
- `src/anonreq/soc/sinks/qradar_cef.py` - QRadarCEFSink with CEF format, TCP/UDP syslog delivery, char escaping, health check
- `tests/test_soc_sink_splunk_hec.py` - 8 tests including format, auth, send, batch, health check, connection errors
- `tests/test_soc_sink_qradar_cef.py` - 9 tests including header format, severity mapping, extensions, TCP send, health check, empty metadata

## Decisions Made

- **CEF severity mapping:** Per plan spec: informational→3, low→4, medium→6, high→8, critical→10. Matches standard CEF 0-10 scale with non-linear step.
- **SinkRouter integration:** Router's `fan_out` will be registered as a single callback on the SOCNormalizer's `register_sink_callback`. Full wiring with per-sink configuration deferred to Plan 20-05 (health monitoring) when sink config becomes user-configurable.
- **CEF header format:** No trailing pipe before extensions. Standard CEF: `CEF:0|AnonReq|Appliance|1.5.0|T1048|dlp_alert|10 tenantId=...` — the space after the 7th header field separates header from extensions.
- **TCP connection management:** QRadar TCP sink attempts connection on `start()`, with lazy reconnect in `_send_tcp` if connection is lost. Start failure is logged but non-fatal (sink retries on first send).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed CEF severity mapping mismatch (informational→3, not 1)**
- **Found during:** Task 3 (QRadar CEF sink TDD)
- **Issue:** Initial implementation used linear 1-10 mapping (informational=1, low=2, medium=5, high=8). Plan spec requires non-linear: informational=3, low=4, medium=6. Tests initially matched implementation, not the plan spec.
- **Fix:** Corrected `_SEVERITY_MAP` and tests to match plan spec exactly
- **Files modified:** `src/anonreq/soc/sinks/qradar_cef.py`, `tests/test_soc_sink_qradar_cef.py`
- **Verification:** Severity mapping test passes with plan-correct values
- **Committed in:** `dac98bd` (fix: align CEF severity mapping with plan spec)

**2. [Rule 1 - Bug] Fixed `SeverityLevel.INFO` → `SeverityLevel.INFORMATIONAL` enum mismatch**
- **Found during:** Task 3 (QRadar CEF sink TDD, GREEN phase)
- **Issue:** SOC `SeverityLevel` enum uses `INFORMATIONAL` not `INFO`. The sink implementation and tests both referenced the non-existent `INFO` member, causing `AttributeError` on import.
- **Fix:** Changed enum references in both sink code and test assertions
- **Files modified:** `src/anonreq/soc/sinks/qradar_cef.py`, `tests/test_soc_sink_qradar_cef.py`
- **Verification:** Import succeeds, all 9 QRadar tests pass
- **Committed in:** `170e8d9` (feat: implement QRadar CEF sink with TDD)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered

- **CEF header parsing:** The `| ` separator between CEF header and extensions required careful parsing in tests — `cef_line.split("|")[6]` includes both the severity value and extensions. Fixed by extracting severity with `split(" ")[0]`.
- **`asyncio.start_server` timeout handling:** The TCP send test creates an actual asyncio server on a random port, which requires proper lifecycle management (close + wait_closed) to avoid dangling coroutines.
- **QRadar start() connection:** The sink attempts TCP connection on `start()`, which may fail if the remote endpoint isn't reachable. This is handled gracefully (logged warning, writer set to None) and reconnection happens on first send.

## Threat Surface

Per the plan's threat register:
- **T-20-02-01 (Information Disclosure):** Mitigated — TLS verification enabled by default on SplunkHECSink, token in Authorization header (not URL)
- **T-20-02-02 (Information Disclosure):** Accepted — syslog lacks native encryption; deployment responsible for network-level encryption
- **T-20-02-03 (Spoofing):** Mitigated — token resolved from env/file, never logged
- **T-20-02-04 (Tampering):** Mitigated — special characters escaped in CEF extension field values (`_sanitize_cef_value`)

## Next Phase Readiness

- SinkBase protocol established — Sentinel, Elastic, Datadog sinks (Plan 20-03) implement the same interface
- SinkRouter ready for fan-out — Plan 20-05 adds config-driven sink registration
- Per-sink Prometheus counters in place — operational metrics ready for dashboards

## Self-Check: PASSED

- [x] All 6 created files exist on disk
- [x] 4 commits for Plan 20-02 verified in git log
- [x] 17 tests pass (8 Splunk HEC + 9 QRadar CEF)
- [x] SinkBase protocol, SinkRouter, both sinks register and fan_out correctly

---

*Phase: 20-ai-soc-siem-integration*
*Completed: 2026-07-05*
