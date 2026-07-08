# Phase 3 Test Strategy

## Test Tiers

### Tier 1: Unit Tests

| Test | Scope | Plan |
|------|-------|------|
| ADAPT-01 | Canonical request → provider request translation | 03-02 |
| ADAPT-02 | Provider response → canonical response | 03-02 |
| ADAPT-03 | Provider stream → StreamEvent normalization | 03-02 |
| ADAPT-04 | Error normalization across providers | 03-02 |
| TailBuffer FSM | State transitions, partial match, flush heuristics | 03-01 |
| RestorationStage | Token replacement, case-insensitive matching, bracket-optional | 03-01 |
| SessionCleanup | Idempotency, race condition, exactly-once | 03-01 |
| AliasRegistry | Resolution, startup validation, error on unknown alias | 03-03 |
| CapabilityResolver | Startup caching, provider lookup | 03-02 |

### Tier 2: Property-Based Tests (Hypothesis)

| Test | Invariant | Plan |
|------|-----------|------|
| TEST-07A | Same text split into N chunks → identical restored text | 03-04 |
| TEST-07B | Token split at every boundary → identical restored text | 03-04 |
| TEST-07C | Long streams never exceed MAX_BUFFER_CHARS | 03-04 |
| TEST-07D | Flush timing variations → identical final output | 03-04 |
| TEST-07E | Reasoning content never appears in final client stream | 03-04 |

### Tier 3: Disconnect Property Tests

| Test | Scenario | Verification |
|------|----------|-------------|
| STREAM-07A | Disconnect at arbitrary chunk boundary | cleanup_session(), zero orphaned mappings |
| STREAM-07B | Disconnect during partial token match | cleanup, no partial token emission |
| STREAM-07C | Disconnect during restoration | cleanup_session() |
| STREAM-07D | Disconnect/FINISH race | exactly one terminal state |

### Tier 4: Load Tests

| Test | Scenario | Verification |
|------|----------|-------------|
| Disconnect load | 100 concurrent client disconnects | Zero orphaned connections |
| Streaming throughput | Sustained streaming with 1000-word prompts | P95 within bounds |

## Coverage Targets

- Streaming module (tail_buffer, restoration, emitter): 95%+
- Provider adapters: 90%+
- Cleanup/logging: 90%+
- Overall Phase 3: 85%+

## Invariants (must pass Hypothesis before Phase 3 closes)

1. `TailBuffer(ProviderStream(text)).assemble() == text` for any arbitrary chunking of text
2. No StreamEvent processed after disconnect detected
3. cleanup_session() is idempotent — N calls = exactly 1 cleanup
4. Reasoning content never reaches client in MVP

## Test Fixtures

- Pre-recorded Anthropic/Gemini/Ollama stream chunks for adapter tests
- Token mapping fixture with known `[TYPE_N]` patterns
- Chunk-split generators for property tests
- ASGI disconnect simulator for disconnect tests
