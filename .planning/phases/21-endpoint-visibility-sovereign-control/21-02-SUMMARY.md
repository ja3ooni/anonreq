---
phase: 21-endpoint-visibility-sovereign-control
plan: 02
subsystem: voice
tags: [voice, stt, whisper, connectors, transcript-buffer, content-type-dispatcher]
requires:
  - phase: 21-01
    provides: proxy foundation and content dispatcher integration point
provides:
  - Voice package configuration for STT model, device, audio windows, latency, and connector limits
  - SIP, WebRTC, WebSocket, and gRPC voice channel connector primitives
  - Local-only Whisper-compatible STT engine with injectable model loading and GPU/CPU selection
  - In-memory transcript ring buffer with sliding-window queries and overlap-aware assembly
  - Content-Type Dispatcher recognition for voice_stream audio content types
affects: [phase-21, voice, multimodal-dispatcher]
tech-stack:
  added: []
  patterns: [local-only-stt, injectable-model-factory, in-memory-audio-processing, connector-callback-delivery]
key-files:
  created:
    - src/anonreq/voice/__init__.py
    - src/anonreq/voice/config.py
    - src/anonreq/voice/connectors.py
    - src/anonreq/voice/stt_engine.py
    - src/anonreq/voice/transcript_buffer.py
    - tests/test_voice_connectors.py
    - tests/test_voice_stt.py
    - tests/test_voice_transcript.py
  modified:
    - src/anonreq/multimodal/models.py
    - src/anonreq/multimodal/dispatcher.py
key-decisions:
  - "STTEngine loads Whisper-compatible models lazily and accepts an injectable model factory so tests do not download or call external services."
  - "Voice audio and transcripts stay in process memory; no temp files or disk-backed audio conversion are used in the new STT path."
  - "voice_stream dispatcher support is represented by ContentType.VOICE_STREAM and audio/pcm, audio/wav, audio/opus MIME mappings."
requirements-completed:
  - APPL-01/Req50
  - APPL-01/Req58
duration: 20 min
completed: 2026-07-05
status: complete
---

# Phase 21 Plan 02: Voice Connectors and Local STT Summary

**Voice ingestion connectors with local-only Whisper-compatible transcription and in-memory transcript buffering**

## Performance

- **Started:** 2026-07-05T14:46:53Z
- **Completed:** 2026-07-05T15:06:53Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Added `VoiceConfig` with model size/device validation, supported audio formats, 500ms sliding windows, 125ms overlap, 150ms latency budget, timeout, and connection-limit settings.
- Added `AudioChunk`, `BaseConnector`, `SIPConnector`, `WebRTCConnector`, `WebSocketConnector`, and `GRPCConnector`.
- Implemented SIP INVITE/SDP inspection, RTP/Opus payload extraction, WebRTC SDP/audio track inspection, WebSocket fragmentation assembly, and gRPC-style bidirectional stream handling.
- Added `STTEngine` with local Whisper-compatible model loading, GPU/CPU auto-detection, streaming transcription, in-memory PCM conversion, and model unload/ CUDA cache cleanup.
- Added `TranscriptBuffer` with bounded in-memory storage, timestamp-ordered sliding windows, contiguous transcript assembly, and pruning.
- Extended the existing Content-Type Dispatcher to recognize `voice_stream` via `audio/pcm`, `audio/wav`, `audio/opus`, and `application/x-anonreq-voice-stream`.

## Task Commits

Commit creation was attempted after implementation. The workspace already contained substantial pre-existing dirty and untracked Wave 1 files, so task-by-task commits were not created during execution. If a final scoped commit succeeds, the hash is reported in the executor response.

## Files Created/Modified

- `src/anonreq/voice/__init__.py` - Voice package exports.
- `src/anonreq/voice/config.py` - Voice configuration model and validation.
- `src/anonreq/voice/connectors.py` - SIP, WebRTC, WebSocket, and gRPC connector primitives.
- `src/anonreq/voice/stt_engine.py` - Local-only Whisper-compatible STT engine.
- `src/anonreq/voice/transcript_buffer.py` - In-memory transcript ring buffer and assembly.
- `src/anonreq/multimodal/models.py` - Added `ContentType.VOICE_STREAM`.
- `src/anonreq/multimodal/dispatcher.py` - Added voice-stream MIME mappings and routing result.
- `tests/test_voice_connectors.py` - Connector, format detection, timeout/reconnect, and dispatcher voice routing tests.
- `tests/test_voice_stt.py` - STT model injection, streaming assembly, GPU/CPU selection, close, and no-disk-write tests.
- `tests/test_voice_transcript.py` - Transcript buffer bounds, windows, assembly, and pruning tests.

## Decisions Made

- STT model imports remain lazy in `stt_engine.py`; importing the voice package does not load Whisper or initialize GPU resources.
- `faster-whisper` is supported when installed, with fallback to existing `openai-whisper`; no new dependency was added for this plan.
- Connector implementations expose testable ingestion primitives rather than binding real SIP/WebRTC/gRPC servers in this wave; Wave 3 can attach sanitization and transport-specific serving around these primitives.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Dispatcher voice_stream integration added**
- **Found during:** Task 2/3 integration review
- **Issue:** The plan required Content-Type Dispatcher extension for `voice_stream`, but owned files listed only the voice package and tests.
- **Fix:** Added `ContentType.VOICE_STREAM`, voice MIME mappings, and a dispatcher result path for voice streams.
- **Files modified:** `src/anonreq/multimodal/models.py`, `src/anonreq/multimodal/dispatcher.py`, `tests/test_voice_connectors.py`
- **Verification:** Focused voice tests and dispatcher regression tests pass.

**2. [Rule 1 - Bug] Transcript window query corrected**
- **Found during:** `tests/test_voice_transcript.py`
- **Issue:** Initial `get_window()` subtracted overlap from the query window, excluding a segment exactly 500ms before the query timestamp.
- **Fix:** Changed `get_window()` to return segments in the full `[timestamp_ms - window_ms, timestamp_ms]` interval.
- **Files modified:** `src/anonreq/voice/transcript_buffer.py`
- **Verification:** Transcript and full voice suites pass.

## Verification

- `PYTHONPATH=src python3 -c "from anonreq.voice.config import VoiceConfig; cfg = VoiceConfig(); assert cfg.stt_model_size == 'base'; assert cfg.sliding_window_ms == 500; assert cfg.latency_budget_ms == 150; print('Voice config OK')"` -> passed.
- `ANONREQ_API_KEY=testkey1234567890123456789012345678 ANONREQ_VALKEY_URL=redis://localhost:6379 ANONREQ_PRESIDIO_URL=http://localhost:5001 pytest tests/test_voice_connectors.py tests/test_voice_stt.py tests/test_voice_transcript.py -q` -> 24 passed.
- `ANONREQ_API_KEY=testkey1234567890123456789012345678 ANONREQ_VALKEY_URL=redis://localhost:6379 ANONREQ_PRESIDIO_URL=http://localhost:5001 pytest tests/multimodal/test_dispatcher.py -q` -> 20 passed.
- `PYTHONPATH=src python3 -m compileall -q src/anonreq/voice` -> passed.
- Artifact line counts meet plan minimums: `connectors.py` 343 lines, `stt_engine.py` 166 lines, `transcript_buffer.py` 91 lines.

## Known Stubs

None. The connectors are transport primitives for this wave and intentionally do not start production SIP/WebRTC/gRPC servers yet; they implement the planned stream extraction and callback contract.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: voice_stream_ingress | `src/anonreq/voice/connectors.py` | New inbound audio stream handling for SIP, WebRTC, WebSocket, and gRPC; mitigated by callback-only in-memory delivery, connection limits, and timeouts. |
| threat_flag: local_stt_inference | `src/anonreq/voice/stt_engine.py` | New local model inference path for audio; mitigated by lazy local model loading and no disk-backed audio writes. |

## Self-Check: PASSED

- Created files exist.
- Focused voice tests pass.
- Dispatcher regression tests pass.
- Summary written to `.planning/phases/21-endpoint-visibility-sovereign-control/21-02-SUMMARY.md`.

---
*Phase: 21-endpoint-visibility-sovereign-control*
*Completed: 2026-07-05*
