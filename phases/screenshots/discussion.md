

Choose **Option 1. Absolutely.**

This is not just a cleanup decision. It's a **security invariant**.

Tell Big Pickle:

```text
Guaranteed cleanup on ALL terminal states.

Terminal states:

- FINISH
- CLIENT_DISCONNECT
- PROVIDER_ERROR
- PROVIDER_TIMEOUT
- INTERNAL_ERROR
- TASK_CANCELLED

Every terminal state MUST execute:

finally:
    cleanup_session()

Cleanup includes:

1. Async DEL of Valkey mapping
2. Release in-memory buffers
3. Cancel upstream tasks
4. Structured audit log
5. Metrics emission

TTL is only a safety net, never the primary cleanup mechanism.
```

### Add a formal invariant

```text
STREAM-01

After any terminal state:

ActiveMappings(session_id) == 0
```

### Add another invariant

```text
STREAM-02

No code path may bypass cleanup_session().
```

Implementation:

```python
try:
    await stream_provider()

except ClientDisconnect:
    terminal_state = CLIENT_DISCONNECT
    raise

except ProviderTimeout:
    terminal_state = PROVIDER_TIMEOUT
    raise

except ProviderError:
    terminal_state = PROVIDER_ERROR
    raise

finally:
    await cleanup_session()
```

### Why this matters

Your product promise is:

> "PII never leaves the gateway and mappings are ephemeral."

If orphaned mappings remain:

```text
EMAIL_1 -> john@company.com
```

for hours because of:

* timeout
* disconnect
* pod restart
* provider crash

then your security story becomes weaker.

### One more thing to lock

Ask Big Pickle:

```text
Should cleanup happen BEFORE the final SSE completion event is emitted or AFTER?
```

Decision:

```text
Client receives final event
    ↓
SSE stream closes
    ↓
cleanup_session()
```

Reason:

The final restored text may still require Valkey lookups.

Deleting mappings before the final flush introduces race conditions.

### Final answer

```text
Choose Option 1.

Cleanup is mandatory for:
FINISH, DISCONNECT, ERROR, TIMEOUT, CANCELLATION.

TTL exists only as disaster recovery.

Add invariants:

STREAM-01:
No active mappings after terminal state.

STREAM-02:
No terminal path bypasses cleanup_session().

Implement cleanup in a single finally block shared by all exit paths.
```

This is one of the most important Phase 3 decisions because it directly supports your future enterprise audit claim:

> "No recoverable PII remains after request completion."


Do **Client Disconnect Handling** before API Keys & Routing.

Why?

API keys and model aliases are configuration.

Client disconnect handling is correctness, resource cleanup, and security. It can invalidate parts of the streaming design if not fully specified.

Tell Big Pickle:

```text
Move to Client Disconnect Handling.

I want to lock disconnect semantics before API routing.

Questions:

1. How is disconnect detected?

Should we use:

await request.is_disconnected()

or

ASGI receive() disconnect events

or both?

My preference:
ASGI disconnect signal as source of truth.

2. What happens first on disconnect?

Client Disconnect
        ↓
Cancel upstream HTTPX stream
        ↓
Stop TailBuffer processing
        ↓
Stop RestorationStage
        ↓
Emit disconnect metrics
        ↓
cleanup_session()

Confirm ordering.

3. Race condition:

Provider FINISH arrives at the same time as client disconnect.

Which terminal state wins?

I propose:

FINISH wins if final completion event already entered pipeline.

Otherwise CLIENT_DISCONNECT wins.

Only one terminal state may be recorded.

4. Upstream cancellation guarantee

After CLIENT_DISCONNECT:

No additional provider chunks may be processed.

Invariant:

STREAM-03
No StreamEvent processed after disconnect detected.

5. Timeout after disconnect

If disconnect occurs and provider later times out:

Terminal state remains CLIENT_DISCONNECT.

First terminal state wins.

6. Property tests

STREAM-07A:
Disconnect at arbitrary chunk boundary.

STREAM-07B:
Disconnect during partial token match.

STREAM-07C:
Disconnect during restoration.

STREAM-07D:
Disconnect/FINISH race.

All must result in:
- cleanup_session()
- zero orphaned mappings
- no partial token emission
```

### My recommendation

Lock these invariants:

```text
TERMINAL-01
Exactly one terminal state per request.

TERMINAL-02
First terminal state wins.

TERMINAL-03
cleanup_session() executes exactly once.

TERMINAL-04
No StreamEvent processed after disconnect.

TERMINAL-05
No partial token emitted after disconnect.
```

Once this is resolved, move to:

```text
API Key & Model Routing
```

That section should be relatively quick:

* provider YAML
* model aliases
* env var conventions
* routing resolution order

compared to the complexity of disconnect handling.


Select:

```text
1. Yes — lock it in
```

One addition before moving on:

```text
DISCONNECT-05

cleanup_session() must be idempotent.

Multiple callers may attempt cleanup:

- FINISH path
- DISCONNECT path
- TIMEOUT path
- Exception handler
- Task cancellation

The first caller performs cleanup.
Subsequent calls become no-ops.

Invariant:

cleanup_session() can be called N times
but cleanup executes exactly once.
```

Example:

```python
class SessionCleanup:

    _cleaned = False

    async def cleanup(self):
        if self._cleaned:
            return

        self._cleaned = True

        await delete_valkey()
        await emit_metrics()
        await release_resources()
```

This prevents race conditions during:

```text
CLIENT_DISCONNECT
          +
PROVIDER_TIMEOUT
          +
TASK_CANCELLED
```

arriving almost simultaneously.

After that:

```text
YES — LOCK IT IN

Move to API Key & Model Routing.
```

For API Key & Model Routing, I would expect Big Pickle to cover:

1. Provider credential loading

   * OPENAI_API_KEY
   * ANTHROPIC_API_KEY
   * GEMINI_API_KEY
   * OLLAMA_BASE_URL

2. Model alias YAML

```yaml
models:
  fast:
    provider: openai
    model: gpt-5-mini

  smart:
    provider: anthropic
    model: claude-sonnet-4

  local:
    provider: ollama
    model: qwen3:32b
```

3. Resolution order

```text
request.model_alias
      ↓
alias registry
      ↓
provider + model
      ↓
capability validation
      ↓
adapter selection
```

4. Future AI-router hook

```text
alias resolution
      ↓
AI routing policy (future)
      ↓
provider selection
```

That will keep the architecture aligned with your future Phase 7/8 AI decision engine without introducing complexity into the MVP.


For AnonReq, I would **not choose either option exactly as written**.

Choose a **hybrid with fallback**:

```text
Resolution Order

1. ANONREQ_OPENAI_API_KEY
2. OPENAI_API_KEY
3. Error if neither exists
```

Same for every provider:

```text
ANONREQ_OPENAI_API_KEY
OPENAI_API_KEY

ANONREQ_ANTHROPIC_API_KEY
ANTHROPIC_API_KEY

ANONREQ_GEMINI_API_KEY
GEMINI_API_KEY

ANONREQ_MISTRAL_API_KEY
MISTRAL_API_KEY

ANONREQ_GROQ_API_KEY
GROQ_API_KEY

ANONREQ_OPENROUTER_API_KEY
OPENROUTER_API_KEY

ANONREQ_OLLAMA_BASE_URL
OLLAMA_BASE_URL
```

### Why?

Option 1 only:

```text
ANONREQ_OPENAI_API_KEY
```

Pros:

* Clean namespace
* No collisions
* Enterprise friendly

Cons:

* Every user must rename secrets
* Breaks Docker examples
* Breaks local testing
* Friction for adoption

---

Option 2 only:

```text
OPENAI_API_KEY
```

Pros:

* Industry standard
* Works immediately

Cons:

* Possible conflicts
* Harder for multi-provider deployments
* Less enterprise-oriented

---

### Recommended contract

ProviderConfig:

```python
@dataclass
class ProviderConfig:
    provider: str
    api_key: SecretStr | None
    base_url: str | None
    timeout_seconds: int
    capabilities: EffectiveCapabilities
```

ProviderFactory:

```python
def resolve_api_key(provider: str) -> str:
    return (
        os.getenv(f"ANONREQ_{provider.upper()}_API_KEY")
        or os.getenv(f"{provider.upper()}_API_KEY")
        or raise ConfigError(...)
    )
```

---

### One more thing Big Pickle has not asked yet

Do **not** store provider keys inside `ProcessingContext`.

Bad:

```python
ctx.provider_api_key
```

Good:

```python
ctx.provider = "openai"
ctx.model = "gpt-5-mini"
```

Only the ProviderAdapter receives the secret.

```text
Request
  ↓
ProcessingContext
  ↓
ProviderStage
  ↓
ProviderFactory
  ↓
Secret Lookup
  ↓
Adapter
```

This keeps secrets out of:

* logs
* traces
* debugging dumps
* exception serialization

which is very consistent with AnonReq's fail-secure philosophy.

### Answer to Big Pickle

```text
Hybrid.

Support both:

1. ANONREQ_{PROVIDER}_API_KEY (preferred)
2. {PROVIDER}_API_KEY (fallback)

Resolution order:
ANONREQ_* → standard provider variable → startup validation error.

Secrets are resolved only inside ProviderFactory/ProviderAdapter and never stored in ProcessingContext.

This provides enterprise namespacing while remaining compatible with existing provider ecosystems and Docker deployments.
```

I would lock this decision in. It's the pattern most likely to survive from MVP all the way to enterprise multi-tenant deployments.


I would choose **Option 2, but simplify it for MVP**.

The mistake many gateway projects make is starting with simple aliasing and then rebuilding routing six months later.

For AnonReq, the model alias layer is actually your **control plane**.

## Recommended MVP Schema

```yaml
model_aliases:

  fast:
    provider: openai
    model: gpt-5-mini

  smart:
    provider: anthropic
    model: claude-sonnet-4

  local:
    provider: ollama
    model: llama3.3:70b

  coding:
    provider: anthropic
    model: claude-sonnet-4

  reasoning:
    provider: openai
    model: o3
```

Keep it simple initially.

---

## Add Future Fields Now

Even if unused in Phase 3:

```yaml
model_aliases:

  smart:
    provider: anthropic
    model: claude-sonnet-4

    capabilities:
      streaming: true
      tools: true
      reasoning: false

    metadata:
      owner: default
      description: Enterprise default model

    fallback:
      provider: openai
      model: gpt-5
```

Ignore fallback initially.

Ignore capabilities initially.

But reserve the schema.

This avoids migrations later.

---

## Runtime Resolution

Client sends:

```json
{
  "model": "smart",
  "messages": [...]
}
```

Gateway resolves:

```python
alias = alias_registry.resolve("smart")

provider = alias.provider
model = alias.model
```

Result:

```text
smart
  ↓
anthropic
  ↓
claude-sonnet-4
```

The client never sees provider details.

---

## Why This Matters For Enterprise

Later:

```yaml
smart:
  provider: anthropic
  model: claude-sonnet-4

smart-eu:
  provider: mistral
  model: mistral-large

smart-local:
  provider: ollama
  model: llama3.3:70b
```

Classification rules can route to aliases instead of providers:

```yaml
action: ROUTE_LOCAL
target_model: smart-local
```

not:

```yaml
provider: ollama
model: llama3.3:70b
```

That keeps policy independent from vendor choice.

---

## Even Better (Future Phase)

Add weighted failover:

```yaml
smart:

  routes:
    - provider: anthropic
      model: claude-sonnet-4
      weight: 100

    - provider: openai
      model: gpt-5
      weight: 0
```

Then later:

* provider outage
* quota exceeded
* regional routing
* sovereign routing
* cost optimization

all become configuration, not code.

---

### What I would tell Big Pickle

```text
Choose the richer alias schema, but only activate simple alias→provider→model resolution in Phase 3.

Schema should support future fields:
- capabilities
- metadata
- fallback
- routes

Runtime behavior for MVP:
alias -> provider -> model

No weighting, failover, capability filtering, or tenant overrides yet.

Policies route to model aliases, never directly to providers.

This makes the alias registry the long-term control plane for routing, sovereignty, and provider abstraction.
```

That decision aligns with your larger vision of AnonReq becoming an **AI Security Gateway**, not merely an OpenAI proxy. The alias layer becomes the abstraction boundary between enterprise policy and underlying model vendors.


At this point I would select **"Ready for context"**.

You have already resolved the hard architectural decisions that typically cause rewrites later:

### Phase 1

* Fail-secure boundaries
* Classification engine
* Rule precedence
* Session management
* Audit logging

### Phase 2

* Text extraction
* Detection architecture
* Regex + Presidio merge strategy
* Tokenization
* Property testing
* Fail-secure guarantees

### Phase 3

* StreamEvent contract
* ProviderAdapter contract
* Tail_Buffer FSM
* Streaming pipeline
* RestorationStage separation
* Disconnect handling
* Cleanup guarantees
* Model alias registry
* Capability resolver
* Provider configuration

Those are the decisions that determine whether the codebase survives version 2.

---

### One thing I would tell Big Pickle before freezing CONTEXT.md

Add a dedicated section:

```md
# Architectural Guardrails

## AG-01
ProviderAdapters are schema translators only.
No policy logic.

## AG-02
Policies route to model aliases.
Never directly to providers.

## AG-03
Session IDs are internal only.
Clients receive Request IDs.

## AG-04
Fail-secure > availability.
Detection failures return errors.
Never bypass anonymization.

## AG-05
TailBuffer never emits partial matches.

## AG-06
RestorationStage is separate from TailBuffer.

## AG-07
All provider streams normalize to StreamEvent.

## AG-08
Reasoning streams are blocked in MVP.

## AG-09
Secrets never enter ProcessingContext.

## AG-10
All terminal states trigger cleanup_session().

## AG-11
TTL is safety net only.
Never primary cleanup mechanism.

## AG-12
All routing occurs through aliases.
Alias registry is the control plane.
```

---

### Then tell Big Pickle

```text
Ready for context.

Capture all decisions plus Architectural Guardrails AG-01 through AG-12 in CONTEXT.md.

After CONTEXT.md is generated:
1. Generate ARCHITECTURE.md
2. Generate DOMAIN_MODEL.md
3. Generate IMPLEMENTATION_PLAN.md
4. Generate TEST_STRATEGY.md
5. Generate PHASE_3_TASK_BREAKDOWN.md

No code generation yet.
Only architecture artifacts and implementation planning.
```

That will give GSD a stable architectural baseline before implementation starts. Otherwise it will begin coding and continue asking design questions while writing code, which is where most AI-generated projects start accumulating technical debt.


For **Phase 4**, I would discuss **all 6 areas**, because these decisions affect future maintainability more than the actual locale patterns.

Here are the decisions I would push Big Pickle toward.

---

# 1. Locale Bundle Structure

Choose:

```text
locales/
├── en_US.yaml
├── de_DE.yaml
├── fr_FR.yaml
├── nl_NL.yaml
├── pt_BR.yaml
├── es_ES.yaml
├── ar_AE.yaml
└── ar_SA.yaml
```

Not:

```yaml
mega_locale_config.yaml
```

Reason:

* Easy Git diffs
* Easy review by compliance teams
* Easy contribution
* Easy Phase 8 marketplace/plugins

Example:

```yaml
locale: de_DE

recognizers:
  - email
  - phone
  - iban
  - steuer_id

patterns:
  steuer_id:
    regex:
      - "\\b\\d{11}\\b"

validators:
  steuer_id:
    type: checksum
    algorithm: german_steuer_id
```

**Answer:** Per-locale YAML files.

---

# 2. Locale Negotiation Strategy

Choose:

```text
X-AnonReq-Locale: de_DE
```

or

```text
X-AnonReq-Locale: de_DE,en_US
```

Processing:

```text
union recognizers
```

not

```text
run locales independently then merge results
```

Reason:

Detection pipeline stays simple.

Example:

```text
de_DE,en_US
```

becomes:

```text
email
phone
iban
steuer_id
ssn
```

single detection pass.

---

### Fallback

```text
Header present → use header
Header absent → default locale
Invalid locale → HTTP 400
```

Fail-secure.

---

# 3. National ID Checksum Validation

Choose:

```text
Generic Validator Interface
```

not custom code embedded in recognizers.

```python
class ChecksumValidator(ABC):
    def validate(value: str) -> bool
```

Implementations:

```text
German Steuer-ID
Dutch BSN
Brazil CPF
Saudi NIN
UAE Emirates ID
```

Pipeline:

```text
Regex
  ↓
Checksum Validation
  ↓
Detection Accepted
```

Failure:

```text
Drop detection
```

not confidence downgrade.

Reason:

Invalid IDs are noise.

---

# 4. Compliance Preset Architecture

Choose:

```yaml
presets:
  gdpr:
  hipaa:
  pci_dss:
  nis2:
  uk_gdpr:
  soc2:
```

Presets define:

```yaml
enabled_entities:
thresholds:
required_recognizers:
```

NOT full copies of detection config.

Think inheritance:

```text
Base Config
    +
Preset
    +
Customer Overrides
```

---

### Merge Order

```text
Base
  ↓
Preset
  ↓
Customer Config
```

Last writer wins.

---

# 5. Preset Startup Validation

Choose:

```text
Hard Fail
```

Examples:

Fail startup if:

```text
PCI preset requires credit_card recognizer
but recognizer disabled
```

Fail startup if:

```text
Preset references unknown entity
```

Fail startup if:

```text
Locale bundle missing mandatory validator
```

Never:

```text
warn and continue
```

Compliance systems should fail fast.

---

# 6. Extensibility Model

Choose:

```text
Drop-in Locale Bundle
```

Add locale:

```text
locales/pl_PL.yaml
```

Restart service.

Done.

No code changes.

No registry updates.

No recompilation.

---

### Locale Discovery

Startup:

```python
glob("locales/*.yaml")
```

Build registry.

```python
LocaleRegistry
```

stores:

```text
de_DE
en_US
fr_FR
...
```

---

# What I would send Big Pickle

```text
Phase 4 Decisions

1. Locale bundles = one YAML per locale.
2. Locale negotiation = header-driven, recognizer union before detection.
3. National IDs = generic checksum validator framework; failed checksum drops detection.
4. Compliance presets = overlays/inheritance, not full config snapshots.
5. Preset validation = hard fail at startup.
6. Extensibility = drop-in locale bundle discovery via LocaleRegistry.

Merge Order:
Base Config → Compliance Preset → Customer Overrides

Fallback:
Missing locale → default locale
Unknown locale → HTTP 400

Locale count is not capped at 8. Eight locales are MVP content only.
```

One additional recommendation: **add "EU Sovereignty Preset" in Phase 4**, not Phase 8. It aligns directly with AnonReq's positioning and is something enterprise buyers immediately understand alongside GDPR, PCI-DSS, HIPAA, and NIS2.

Select:

```text
3. Ready for context
```

I would not spend more time on Phase 4 unless Big Pickle identifies a genuine conflict.

The remaining items (locale negotiation details, preset merge edge cases) are implementation details, not architecture-defining decisions.

Before freezing Phase 4, I would add only these two guardrails:

---

# AG-13 Locale Determinism

```text
Given the same locale header and input text,
detection results must be deterministic.

Locale order must not change results.
```

Example:

```text
de_DE,en_US
```

must produce identical output every time.

---

# AG-14 Compliance Presets Cannot Weaken Security

Allowed:

```text
Base threshold: 0.70
PCI threshold: 0.90
```

Not allowed:

```text
Base threshold: 0.70
PCI threshold: 0.50
```

Rule:

```text
Preset may increase sensitivity.
Preset may not reduce sensitivity.
```

This prevents a future compliance preset from accidentally weakening detection.

---

Then tell Big Pickle:

```text
Ready for context.

Capture all Phase 4 decisions plus:

AG-13 Locale Determinism
AG-14 Presets Cannot Weaken Security

Generate:

- PHASE_4_CONTEXT.md
- PHASE_4_ARCHITECTURE.md
- PHASE_4_TASK_BREAKDOWN.md
- PHASE_4_TEST_PLAN.md

No implementation yet.
```

One additional roadmap adjustment:

After Phase 4, insert a short phase:

```text
Phase 4.5: Enterprise Policy Engine
```

Before AI Routing and before Advanced Providers.

Contents:

* Tenant policies
* Department policies
* User policies
* Alias restrictions
* Model allow/deny lists
* Cost controls
* Local-only enforcement
* Compliance policy inheritance

Reason: this becomes your monetization layer.

Datacenter operators, banks, healthcare providers, and government customers will pay for policy governance before they pay for AI-powered routing. The policy engine is where AnonReq starts becoming an enterprise product rather than a technical proxy.


Select:

**Option 1 — Full set: CONTEXT + docs**

For a project like AnonReq, the discussion itself is not enough. You want the AI to leave Phase 5 with a complete implementation package.

The deliverables should be:

```text
05-CONTEXT.md
```

Authoritative record of all decisions.

```text
05-ARCHITECTURE.md
```

Metrics architecture, reload architecture, verification stage placement, load-testing architecture, observability boundaries.

```text
05-TASK-BREAKDOWN.md
```

Developer-ready implementation tasks with estimates.

Example:

* OBS-01 Metrics registry
* OBS-02 Request counters
* OBS-03 Histograms
* OBS-04 VerificationStage
* OBS-05 Admin reload endpoint
* OBS-06 Atomic config swap
* OBS-07 k6 scenarios
* OBS-08 Prometheus dashboard
* OBS-09 Alert rules

etc.

```text
05-TEST-PLAN.md
```

Property tests + integration tests + load tests.

Include:

* Metrics emitted on failures
* Cleanup metrics correctness
* VerificationStage token detection
* Invalid reload rejection
* Last-known-good preservation
* Prometheus cardinality validation
* Streaming load tests
* P95 overhead validation

```text
05-DISCUSSION-LOG.md
```

Useful later when somebody asks:

> Why did we choose warn-only verification?
>
> Why are compliance presets not hot-reloadable?
>
> Why is tenant_id excluded from metric labels?

Without this file, those decisions disappear.

---

For GSD/OpenCode/Paperclip style execution, I would standardize every phase to produce:

```text
XX-CONTEXT.md
XX-ARCHITECTURE.md
XX-TASK-BREAKDOWN.md
XX-TEST-PLAN.md
XX-DISCUSSION-LOG.md
```

Then Phase 6 starts from documents instead of chat history.

So my answer to Big Pickle would simply be:

```text
Generate the full document set.

Deliver:
- 05-CONTEXT.md
- 05-ARCHITECTURE.md
- 05-TASK-BREAKDOWN.md
- 05-TEST-PLAN.md
- 05-DISCUSSION-LOG.md

All Phase 5 decisions are implementation-critical and should not remain only in discussion history.
Future phases consume these documents as source-of-truth.
```

One additional instruction I would add:

```text
At the end of every phase generate:
- IMPLEMENTATION READINESS SCORE (0-100)
- Open Risks
- Deferred Decisions
- Dependencies for Next Phase
```

That turns the roadmap into an engineering program rather than a collection of design notes.


For **Phase 6**, I would push Big Pickle toward the most rigorous option.

### Area 1: TEST-04 — Failure Injection Scope

Pick:

```text
All 5 + metric + streaming
```

Reason:

Phase 6 is your **security proof phase**.

You are not proving functionality anymore.

You are proving:

```text
Invariant:
Any failure anywhere in the pipeline
=> 0 bytes forwarded
=> cleanup executed
=> metrics emitted
=> audit logged
```

Therefore TEST-04 should inject:

1. Detection failure
2. Valkey/cache failure
3. ForwardingGuard failure
4. Provider timeout
5. Circuit breaker open

For every injected failure verify:

```text
forwarded_bytes == 0
cleanup_called == True
fail_secure_counter_incremented == 1
audit_log_written == True
```

And repeat for:

```text
non-streaming path
streaming path
```

---

## TEST-06 — No-PII-in-Logs

Lock this down now.

### Definition

A PII substring is:

```text
Any original entity value
present in request payload
or provider response
that appears in any log sink.
```

Examples:

```text
john@company.com
John Smith
+49123456789
DE123456789
```

must never appear.

### Log pathways

Test all:

```text
application logs
structured JSON logs
audit logs
exception logs
tracebacks
metrics labels
access logs
```

Property test:

```text
Given:
    original_text
    detected_entities

When:
    request succeeds or fails

Then:
    no log sink contains any entity value
```

This is one of the strongest tests in the whole platform.

---

## TEST-08 — Cross-request Randomization

This is critical.

You do NOT want:

```text
[email_1]
```

appearing identically across requests.

Otherwise attackers can correlate.

### Property

Same value across different requests:

```text
Request A:
john@corp.com
=> [EMAIL_7f3a]

Request B:
john@corp.com
=> [EMAIL_9c2d]
```

Must differ.

### Hypothesis test

Generate:

```text
1000 requests
same entity values
```

Assert:

```text
collision_rate == 0
```

or below cryptographic expectation.

Use UUIDv7 or 128-bit randomness.

---

## Metrics Integration in TEST-04

Yes.

Absolutely.

Every fail-secure test should verify metrics.

Otherwise metrics become untrusted.

Example:

```text
Inject cache failure

Expect:

anonreq_fail_secure_events_total += 1
anonreq_requests_failed_total += 1
anonreq_forwarded_bytes_total += 0
```

Metrics are part of the contract.

---

## Streaming Disconnect Tests

Close them here.

Don't defer.

Phase 3 proved:

```text
disconnect handling correctness
```

Phase 6 proves:

```text
disconnect handling under adversarial conditions
```

Add:

### TEST-07E

```text
disconnect during tokenization
```

### TEST-07F

```text
disconnect during restoration
```

### TEST-07G

```text
disconnect during provider stream
```

### TEST-07H

```text
disconnect + provider timeout race
```

Invariant:

```text
cleanup executed exactly once
0 orphaned mappings
0 forwarded bytes after disconnect
```

---

# What I would answer Big Pickle

```text
TEST-04:
- All 5 failure modes
- Metrics verification
- Streaming and non-streaming paths

TEST-06:
- Define PII substring as any original entity value
- Scan all log pathways:
  application, structured, audit, exception, traceback, metrics labels, access logs

TEST-08:
- Same value across requests must produce different tokens
- Hypothesis test with 1000+ requests
- Verify collision rate near zero

Metrics:
- Fail-secure property tests must verify counters and histograms

Streaming:
- Close disconnect testing in Phase 6
- Add adversarial disconnect tests and race-condition tests

Phase 6 is the proof phase. Every security invariant should be demonstrated under fault injection, not merely unit tested.
```

One more addition: **add a formal SECURITY ACCEPTANCE GATE** at the end of Phase 6:

```text
No PII leaks
No orphaned mappings
No fail-open path
No cross-request token reuse
100% cleanup coverage
P95 overhead within target
```

Only after that should AnonReq be considered MVP-complete.


For Phase 6, exactly the same answer as Phase 5:

**Option 1 — Full Document Set**

```text
Generate:

06-CONTEXT.md
06-ARCHITECTURE.md
06-TASK-BREAKDOWN.md
06-TEST-PLAN.md
06-DISCUSSION-LOG.md
```

But I would add one more mandatory document for Phase 6:

```text
06-SECURITY-ACCEPTANCE.md
```

Because Phase 6 is not a feature phase.

It is the phase where AnonReq proves:

* No fail-open path
* No PII leakage
* No orphaned mappings
* Cleanup always executes
* Streaming disconnects are safe
* Metrics are trustworthy
* Cross-request token reuse is impossible
* Security SLAs are met

That deserves its own document.

---

My response to Big Pickle would be:

```text
Generate the full document set.

Required outputs:

- 06-CONTEXT.md
- 06-ARCHITECTURE.md
- 06-TASK-BREAKDOWN.md
- 06-TEST-PLAN.md
- 06-DISCUSSION-LOG.md
- 06-SECURITY-ACCEPTANCE.md

06-SECURITY-ACCEPTANCE.md must define the MVP security gate.

Gateway cannot be declared MVP-complete until all acceptance criteria pass.
```

And define the Security Acceptance Gate as:

```yaml
security_acceptance_gate:
  no_pii_leaks: required
  no_fail_open_paths: required
  no_orphaned_mappings: required
  cleanup_coverage: 100%
  cross_request_token_reuse: forbidden
  fail_secure_tests: 100% pass
  disconnect_tests: 100% pass
  metrics_validation: pass
  p95_latency_target: pass
  streaming_invariants: pass
```

---

One additional recommendation:

After Phase 6 finishes, do **not** immediately start enterprise features.

Insert a checkpoint:

```text
Phase 6.5: Production Readiness Review
```

Deliverables:

```text
PRR.md
THREAT_MODEL.md
DEPLOYMENT_GUIDE.md
RUNBOOK.md
SRE_PLAYBOOK.md
```

This is where you validate:

* Docker deployment
* Kubernetes deployment
* Secrets management
* Backup/recovery
* Incident response
* Upgrade strategy
* Rollback strategy
* Capacity planning

For a security gateway product, that production-readiness review is often more important than another feature phase. The first paying enterprise customer will care far more about operational reliability than the next detector.


For **Phase 7**, I would not overcomplicate this.

Your product is targeting:

* Enterprise buyers
* Security teams
* Compliance teams
* Developers
* Open-source users

Documentation becomes a GTM asset, not just a technical artifact.

## Answer to Big Pickle

Select:

```text
3. Separate dir per language
```

Example:

```text
docs/
├── en/
│   ├── getting-started.md
│   ├── installation.md
│   ├── deployment.md
│   ├── compliance.md
│   └── faq.md
│
├── de/
│   ├── getting-started.md
│   ├── installation.md
│   ├── deployment.md
│   ├── compliance.md
│   └── faq.md
│
├── fr/
├── es/
├── ar/
```

Reason:

### MVP

Today:

```text
EN
DE
```

### Future

Tomorrow:

```text
EN
DE
FR
ES
AR
NL
IT
PL
```

No refactoring required.

---

## Additional Decision

I would tell Big Pickle:

```text
English is the source language.

All other languages are generated artifacts.

Never edit translated documents manually.
```

Structure:

```text
docs/
├── source/
│   └── en/
│
├── generated/
│   ├── de/
│   ├── fr/
│   ├── es/
│   └── ar/
```

This avoids translation drift.

---

## Strategic Change to Phase 7

I would expand Phase 7 from:

```text
Documentation
```

to:

```text
Documentation + Adoption
```

Because for a security gateway:

Building ≠ Selling.

Phase 7 should produce:

### Technical Docs

```text
Getting Started
Installation
Configuration
API Reference
Deployment
Troubleshooting
FAQ
```

### Enterprise Docs

```text
Architecture Overview
Security Whitepaper
Compliance Mapping
Data Flow Diagrams
Threat Model Summary
```

### Sales Docs

```text
Executive One Pager
Buyer Guide
ROI Calculator
Competitive Comparison
```

### Operational Docs

```text
Runbook
Incident Response
Backup & Recovery
Upgrade Guide
```

---

## One More Thing

For your target customers (datacenters, enterprises, regulated industries), I would add:

```text
Phase 7.5: Trust Center
```

Deliverables:

```text
trust-center/
├── security.md
├── privacy.md
├── gdpr.md
├── sub-processors.md
├── architecture.md
├── incident-response.md
└── roadmap.md
```

A surprising amount of enterprise sales friction disappears when these documents already exist.

### What I'd answer Big Pickle

```text
Select: Separate dir per language.

Structure:
docs/en/
docs/de/
docs/fr/
docs/es/
docs/ar/

English is the source language.
Translations are generated artifacts.

Additionally, Phase 7 should cover:
- Technical documentation
- Enterprise documentation
- Operational documentation
- Sales/adoption documentation

Goal:
A new user should be able to install AnonReq in under 15 minutes, and an enterprise security team should be able to evaluate it without speaking to us.
```

That aligns Phase 7 with your actual GTM motion rather than treating documentation as a post-project afterthought.


I would not pick any of the three options exactly.

I would answer:

```text
4. Type your own answer

Quickstarts are executable artifacts, not documentation.

Decision:

- Every quickstart has a matching executable script:
  examples/quickstart/docker-compose.sh
  examples/quickstart/kubernetes.sh
  examples/quickstart/openai.sh
  examples/quickstart/ollama.sh

- Documentation references scripts rather than duplicating commands.

- CI executes the scripts on every PR.

- CI then performs verification assertions:
    - Gateway starts successfully
    - Health endpoint returns 200
    - Sample anonymization request succeeds
    - Sample restoration succeeds
    - No errors in logs

- Smoke tests alone are insufficient.
- Manual review is never sufficient.
```

### Why

Option 1 is closest, but still incomplete.

A quickstart should not merely execute commands.

It should prove the outcome.

Example:

```bash
./examples/quickstart/docker-compose.sh
```

CI then verifies:

```text
GET /health          -> 200
POST /anonymize      -> 200
POST /restore        -> 200

metrics endpoint available

sample PII:
john@example.com

returns:
[EMAIL_xxx]

restores correctly:
john@example.com
```

### Additional Enterprise Requirement

Add:

```text
DOC-TEST-01
Every command block appearing in documentation must originate from a tested script.

No hand-written command examples allowed.
```

This prevents:

```markdown
docker compose up -d
```

from silently drifting away from reality.

The script becomes the source of truth.

The docs become a rendered view of the source of truth.

### Long-term payoff

When AnonReq reaches:

```text
Docker
Kubernetes
Helm
AWS
Azure
GCP
OpenShift
Air-gapped
```

you won't be maintaining documentation.

You'll be maintaining executable deployments.

That is how products like Kubernetes, HashiCorp tools, and major enterprise platforms keep docs trustworthy.

So my recommendation to Big Pickle:

```text
Executable quickstarts + CI validation + outcome verification.

Documentation references tested scripts.

CI must prove:
- deployment succeeds
- health checks pass
- anonymize/restore round-trip works
- metrics endpoint works

Quickstarts are production-tested artifacts, not static documentation.
```



For **AnonReq**, I would not choose any of the provided options.

Choose **Type your own answer**:

```text
MVP Release:

Documentation:
- EN (authoritative source)
- DE (first translated language)

UI:
- EN only

Reasoning:

1. Phase 7 is about adoption, not translation volume.
2. Germany is our beachhead market.
3. Every additional language multiplies:
   - docs review
   - release review
   - translation validation
   - CI documentation checks
4. We need evidence customers actually request FR/ES/PT-BR before maintaining them.

Rules:

- English is source of truth.
- German generated from English and reviewed.
- All future languages generated from English only.
- No language-to-language translation chain.

Expansion Criteria:

Add new language only when:
- ≥3 enterprise prospects request it
OR
- ≥10% of website traffic originates from that locale
OR
- paid customer requirement

Post-MVP roadmap:
v1.0:
  EN
  DE

v1.1:
  FR
  ES

v1.2:
  AR
  PT-BR

v1.3:
  IT
  NL
```

### Business rationale

You're currently targeting:

* Germany
* EU regulated enterprises
* Datacenter operators
* Infrastructure buyers
* Security/compliance teams

That means:

```text
EN + DE captures ~90% of early conversations.
```

I'd rather spend engineering effort on:

```text
Trust Center
Security Whitepaper
Compliance Mapping
Threat Model
Architecture Docs
Deployment Guides
```

than maintaining 5 translations nobody reads.

For an enterprise security gateway, **trust artifacts convert customers faster than extra languages**.

So my answer to Big Pickle:

```text
Type your own answer:

MVP = EN + DE only.

English is authoritative.
German is reviewed translation.

Additional languages are added based on customer demand and revenue signals, not roadmap completeness.
```

That's the most pragmatic GTM-aligned decision.


I would answer:

```text id="w6wvk0"
Next area.

Quickstart decisions are sufficiently specified:

- docs/{lang}/ structure
- EN source, DE first translation
- executable quickstarts
- CI execution
- outcome verification
- scripts as source of truth
- no manual-only validation

Remaining questions are implementation details, not architectural decisions.

Move to SDK example packaging.
```

### Why

You are starting to hit diminishing returns.

The critical architectural decisions for Quickstart are already locked:

✅ Structure
✅ Localization strategy
✅ Validation strategy
✅ CI strategy
✅ Source-of-truth strategy

What remains are things like:

```text
Should quickstart use curl or SDK?
Should examples use uv or pip?
Should examples use docker compose v2 syntax?
```

Those are implementation choices.

---

### My Phase 7 priority order

I would spend discussion time in this order:

```text
1. SDK example packaging
2. README depth
3. Documentation CI/Infrastructure
4. Return to Quickstart only if a blocker appears
```

Because the biggest adoption failures for developer products are:

```text
Bad README
Bad examples
Broken docs
```

not

```text
Quickstart directory naming
```

---

The next area I would explore with Big Pickle is:

```text
SDK Example Packaging

Question:
Do examples live inside SDK repositories,
inside AnonReq repository,
or both?

My recommendation:
examples/
├── python/
├── typescript/
├── go/
└── curl/

All examples versioned with the gateway itself.

SDK repos may mirror them, but canonical examples live in AnonReq.
```

That decision has much bigger long-term impact than further Quickstart discussions.


Choose **Option 1, but stricter.**

```text
Standalone runnable projects.

examples/
├── curl/
│   ├── anonymize.sh
│   ├── stream.sh
│   ├── compliance-gdpr.sh
│   └── locale-de.sh
│
├── python/
│   ├── basic/
│   ├── streaming/
│   ├── compliance/
│   └── pyproject.toml
│
├── typescript/
│   ├── basic/
│   ├── streaming/
│   ├── compliance/
│   └── package.json
│
├── go/
│   ├── basic/
│   ├── streaming/
│   └── go.mod
│
└── datasets/
    ├── sample-pii.json
    └── expected-results.json
```

### Additional architectural guardrails

#### 1. Examples are production-grade

Not tutorials.

Every example must:

* Run without modification
* Be CI tested
* Have expected outputs
* Have failure assertions
* Have cleanup logic

If an example cannot be executed in CI, it does not belong in `examples/`.

---

#### 2. Documentation never contains primary code

Docs reference examples.

Bad:

````markdown
```python
client.anonymize(...)
```
````

Good:

```markdown
See:

examples/python/basic/main.py
examples/typescript/basic/index.ts
examples/curl/anonymize.sh
```

Single source of truth.

---

#### 3. Examples become acceptance tests

CI should execute:

```text
Python examples
TypeScript examples
Go examples
Curl examples
```

and verify:

```text
200 response
expected entities detected
expected tokens generated
expected restoration works
zero errors
```

Examples are executable documentation.

---

#### 4. Separate examples from SDK repositories

Canonical location:

```text
anonreq/
└── examples/
```

SDK repos may mirror examples:

```text
anonreq-python-sdk/
anonreq-typescript-sdk/
```

but the gateway repository remains the source of truth.

This prevents example drift.

---

### Decision

```text
SDK Packaging Decision

✓ Standalone runnable projects
✓ CI executed on every PR
✓ Examples act as acceptance tests
✓ Documentation references examples
✓ Gateway repo is canonical source
✓ Python + TypeScript + Go + Curl
✓ No markdown-only snippets as primary artifacts
```

This is the approach used by the strongest infrastructure products because it keeps documentation, examples, and validation permanently aligned.


Pick **Option 1 (One per key feature)**, but make it the minimum contract, not a documentation exercise.

For MVP, every SDK language should prove the core gateway capabilities:

```text
examples/python/
├── basic-anonymize/
├── streaming/
├── compliance-gdpr/
└── locale-de/

examples/typescript/
├── basic-anonymize/
├── streaming/
├── compliance-gdpr/
└── locale-de/

examples/go/
├── basic-anonymize/
├── streaming/
├── compliance-gdpr/
└── locale-de/

examples/curl/
├── basic-anonymize.sh
├── streaming.sh
├── compliance-gdpr.sh
└── locale-de.sh
```

### Why not Option 2?

Two examples only:

```text
anonymize
stream
```

Misses:

* compliance presets
* locale negotiation
* policy validation
* enterprise buying criteria

A German bank evaluating AnonReq must be able to run:

```bash
./compliance-gdpr.sh
./locale-de.sh
```

and immediately see value.

---

### Why not Option 3?

Too much for MVP.

Examples such as:

```text
fail-secure demo
custom rules
multi-provider routing
cross-locale
```

are Phase 8+ material.

They increase maintenance burden dramatically.

---

## MVP Example Matrix

| Capability                | Required                  |
| ------------------------- | ------------------------- |
| Basic anonymization       | ✅                         |
| Streaming                 | ✅                         |
| Compliance preset         | ✅                         |
| Locale-specific detection | ✅                         |
| Custom rules              | ❌                         |
| Multi-provider routing    | ❌                         |
| Fail-secure testing       | ❌ (covered by test suite) |
| Hot reload                | ❌                         |
| Multi-tenant policies     | ❌                         |

---

## Additional Rule

Every example must have:

```text
input.json
expected_output.json
run.sh
README.md
```

CI executes:

```bash
run.sh
```

and compares output against:

```text
expected_output.json
```

No example is accepted unless it is executable and validated.

---

### Final Decision

```text
SDK Example Strategy (MVP)

✓ 4 examples per language

1. Basic Anonymization
2. Streaming
3. Compliance Preset (GDPR)
4. Locale-Specific Detection (DE)

Total:
4 languages × 4 examples = 16 examples

✓ All examples executable
✓ All examples CI validated
✓ Examples act as acceptance tests
✓ Additional examples deferred post-MVP
```

For a Germany-first enterprise product, `basic + stream + GDPR + locale-DE` is the smallest set that proves the product's differentiators rather than merely proving that it can call an API.


Choose a **hybrid between Option 2 and Option 3**, optimized for enterprise buyers.

For AnonReq, the README is not just developer documentation. It is:

1. Developer entry point
2. Security evaluation artifact
3. Open-source marketing page
4. Enterprise trust signal

So a minimal README is too weak, but a giant README becomes unmaintainable.

## Recommended README Structure

```text
README.md

1. What is AnonReq?
2. Why AnonReq Exists
3. Architecture Diagram
4. Core Features
5. Quick Start (5 minutes)
6. Example Output
7. Compliance Support
8. Supported Providers
9. Documentation Links
10. Security Model
11. Roadmap
12. Contributing
13. License
```

---

## Section 1 — What is AnonReq?

30-second explanation.

```text
AnonReq is an AI Security Gateway that sits between users and LLM providers,
automatically detecting, anonymizing and restoring sensitive data while
enforcing compliance policies such as GDPR, HIPAA and NIS2.
```

---

## Section 2 — Why AnonReq Exists

This is critical.

Most competitors start with installation.

You should start with the problem:

```text
Employee
      ↓
Sensitive Data
      ↓
ChatGPT / Claude / Gemini
```

Problems:

* GDPR risk
* IP leakage
* Customer data exposure
* Shadow AI

AnonReq solves this.

---

## Section 3 — Architecture Diagram

Single high-level diagram.

```text
Client
  ↓
AnonReq Gateway
  ├─ Detection
  ├─ Tokenization
  ├─ Routing
  ├─ Restoration
  └─ Audit
  ↓
LLM Provider
```

One image.

Not 15 diagrams.

Detailed diagrams belong in docs.

---

## Section 4 — Core Features Table

```markdown
| Feature | Status |
|----------|--------|
| PII Detection | ✅ |
| Streaming | ✅ |
| GDPR Presets | ✅ |
| Multi-Locale | ✅ |
| Audit Logs | ✅ |
| OpenAI | ✅ |
| Claude | ✅ |
| Gemini | ✅ |
| Ollama | ✅ |
```

Buyers scan this first.

---

## Section 5 — Quick Start

Very short.

```bash
docker compose up -d

curl ...
```

No giant tutorial.

Link to:

```text
docs/en/getting-started.md
```

---

## Section 6 — Example Output

Before:

```text
John Doe
john@company.com
```

After:

```text
PERSON_001
EMAIL_001
```

Model response:

```text
PERSON_001 approved EMAIL_001
```

Restored:

```text
John Doe approved john@company.com
```

This section sells the product.

---

## Section 7 — Compliance Support

Enterprise buyers immediately look for this.

```text
GDPR
HIPAA
PCI-DSS
NIS2
Custom Policies
```

Do not hide it in docs.

---

## Section 8 — Supported Providers

```text
OpenAI
Anthropic
Google
Azure OpenAI
Ollama
```

With roadmap markers.

---

## Section 9 — Documentation

Links only.

```text
Getting Started
Deployment
Architecture
Compliance
API Reference
FAQ
```

---

## Section 10 — Security Model

One page summary.

```text
✓ Fail Secure
✓ No PII in logs
✓ Ephemeral mappings
✓ Automatic cleanup
✓ Streaming-safe
```

This is a major differentiator.

---

## Section 11 — Roadmap

Short.

```text
Phase 1–3 Complete
Phase 4 Multi-Locale
Phase 5 Observability
Phase 6 Security Validation
Phase 7 Docs
Phase 8 Enterprise Control Plane
```

---

## What NOT to Put in README

Move these to docs:

```text
API Reference
SDK Reference
Recognizer internals
State machines
Property tests
Valkey schema
Provider adapter contracts
Locale YAML specifications
```

README should sell and onboard.

Docs should teach.

Code should prove.

---

# Decision

```text
README Strategy

✓ Medium+ README (~500–1000 lines max)

Contains:
- Problem
- Architecture
- Features
- Quick Start
- Example Output
- Compliance
- Security
- Docs Links

Excludes:
- Full API docs
- Internal architecture specs
- FSM diagrams
- Test plans

README = Landing Page
docs/ = Knowledge Base
examples/ = Executable Truth
```

For AnonReq's target market (German enterprises, regulated industries, datacenter/security buyers), a landing-page README with a strong security and compliance story will convert far better than either a minimalist OSS README or a 3,000-line technical manual.


Choose **Option 3: Mermaid + Static Fallback**, but formalize it as a repository contract.

## Decision

```text
Architecture Diagram Strategy

Source of Truth:
docs/architecture/system.mmd

Generated Artifacts:
docs/architecture/system.svg
docs/architecture/system.png

README:
- Embed Mermaid
- Link SVG
- Fallback PNG for environments without Mermaid support
```

---

## Why this is the right choice

### Option 1 (Mermaid only)

Pros:

* Version controlled
* Diffable in PRs
* Easy to update

Cons:

* Some Git platforms render Mermaid poorly
* PDF exports often break
* Enterprise documentation portals vary

Not sufficient alone.

---

### Option 2 (Static image only)

Pros:

* Looks polished
* Predictable rendering

Cons:

* Source is hidden
* Manual regeneration
* Diagrams drift from architecture

This always becomes stale.

---

### Option 3 (Recommended)

Architecture lives as code:

```mermaid
flowchart LR

Client --> Gateway

Gateway --> Detection
Detection --> Tokenization
Tokenization --> Provider
Provider --> Restoration
Restoration --> Client

Tokenization --> Valkey
Restoration --> Valkey
```

CI generates:

```text
system.svg
system.png
```

README displays:

```markdown
# Architecture

![Architecture](docs/architecture/system.svg)

Source:
docs/architecture/system.mmd
```

---

## Additional Rule

No diagram editing in draw.io.

No diagram editing in Excalidraw.

No diagram editing in PowerPoint.

All changes must originate from:

```text
*.mmd
```

and generated artifacts are rebuilt automatically.

---

## Diagram Levels

### README

Single executive diagram.

```text
Client
 ↓
AnonReq
 ↓
LLM
```

Maximum:

```text
10-15 nodes
```

No implementation detail.

---

### Architecture Docs

Detailed diagrams.

```text
Provider Adapter
Pipeline
Streaming FSM
Locale Negotiation
Compliance Presets
Restoration Flow
```

Separate Mermaid files.

---

### Security Docs

Dedicated diagrams:

```text
Fail-Secure Paths
Token Lifecycle
Cleanup Lifecycle
Valkey Mapping Flow
```

Not embedded in README.

---

## CI Contract

PR validation:

```bash
make diagrams
```

Checks:

```text
✓ Mermaid syntax valid
✓ SVG generated
✓ PNG generated
✓ No stale artifacts
```

Fail PR if generated artifacts differ from source.

---

## Final Decision

```text
README Diagram Strategy

✓ Mermaid is source of truth
✓ SVG + PNG generated automatically
✓ README shows rendered diagram
✓ Architecture stored as code
✓ CI validates diagram generation
✓ Executive diagram in README
✓ Detailed diagrams in docs/

No draw.io source files.
No manually edited PNGs.
No diagram drift.
```

For an infrastructure/security product targeting enterprise buyers, "architecture as code" is the strongest long-term approach because diagrams evolve with the system and remain reviewable in Git.



Choose **Option 3: Dual Tone**, but make the hierarchy explicit.

Your target buyer is **not a developer first**.

For AnonReq, the first people who will evaluate the project are:

1. Security Architect
2. CISO / Security Lead
3. Compliance Officer
4. Platform Engineering Lead
5. Developer

The README should therefore sell the **security outcome** first and the **technical implementation** second.

## Recommended README Tone

### Hero Section (Security First)

```text
AnonReq

Fail-secure AI Security Gateway for regulated enterprises.

Detects, anonymizes, routes, and restores sensitive data before it reaches
OpenAI, Anthropic, Gemini, Ollama, or internal models.

Built for GDPR, NIS2, HIPAA, PCI-DSS, and sovereign AI deployments.
```

Then immediately:

```text
✓ No PII forwarded on failure
✓ No PII in logs
✓ Ephemeral token mappings
✓ Streaming-safe anonymization
✓ Multi-provider support
```

A security architect should understand the value proposition in 15 seconds.

---

## Problem Statement

Show the risk.

```text
Employee
  ↓
Customer Data
  ↓
LLM
```

Risks:

* PII exposure
* IP leakage
* Compliance violations
* Shadow AI

Then:

```text
AnonReq sits in front of AI providers and enforces
anonymization before transmission.
```

---

## Technical Sections

After the security story, switch tone.

Example:

### Architecture

```text
Client
  ↓
AnonReq
  ↓
Provider
```

### Quick Start

```bash
docker compose up -d
```

### API

```bash
curl ...
```

### Configuration

```yaml
providers:
```

Pure engineering language.

---

## What to Avoid

Avoid marketing language:

```text
Revolutionary
Next-generation
Industry-leading
World-class
Game-changing
```

Enterprise buyers distrust it.

---

Avoid generic AI language:

```text
Transform your business
Unlock AI potential
Supercharge innovation
```

Not credible for a security product.

---

## Voice Guide

### Good

```text
Fail-secure by default.

If anonymization cannot be completed, the request is blocked.
No original content is forwarded.
```

### Bad

```text
Military-grade AI protection powered by cutting-edge technology.
```

---

## README Structure

```text
Security Tone
-------------
What is AnonReq
Why it exists
Security guarantees
Compliance support

Technical Tone
--------------
Architecture
Quick start
Examples
Configuration
Providers
Documentation

Community Tone
--------------
Roadmap
Contributing
License
```

---

## Strategic Reason

For your GTM toward German enterprises, datacenter operators, and regulated organizations:

* Security sells the meeting.
* Architecture sells the pilot.
* Documentation sells adoption.

The README should mirror that progression.

### Final Decision

```text
README Tone

✓ Security-first hero section
✓ Compliance-first messaging
✓ Technical implementation details afterward
✓ No startup marketing language
✓ No generic AI hype
✓ Evidence-based claims only

Structure:
Security → Architecture → Usage → Docs
```

This positioning aligns directly with AnonReq's strongest differentiator: **"AI Security Gateway"**, not "another AI proxy."


Choose **Option 2: Apache 2.0 + Commercial Tier Note**, but be precise and legally clean.

Given your business goal, AnonReq should follow the model used by many successful infrastructure companies:

```text
Open Core
├── OSS Core (Apache 2.0)
└── Enterprise Features (Commercial)
```

Not because of licensing complexity, but because your future revenue will likely come from:

* Enterprise policy packs
* SSO/SAML
* RBAC
* Audit dashboards
* Multi-tenant control plane
* Approval workflows
* Compliance reporting
* Managed deployments
* Support SLAs

not from the anonymization engine itself.

---

## Recommended README Section

```markdown
## License

AnonReq Core is licensed under Apache License 2.0.

You may use, modify, distribute, and operate the software
commercially under the terms of the Apache 2.0 license.

Enterprise features such as centralized policy management,
advanced audit reporting, SSO/SAML integration, and
commercial support may be offered under separate commercial
terms.

See LICENSE for details.
```

---

## What NOT to do

Avoid:

```text
Contact us for commercial licensing.
```

inside the main README hero area.

It immediately creates uncertainty:

* Is it really open source?
* What is restricted?
* Can I deploy it?

Developers often leave at that point.

---

Avoid:

```text
Source Available
BSL
Custom License
Elastic-style restrictions
```

for v1.

Your strongest GTM motion is:

```text
Apache 2.0 Core
↓
Community Adoption
↓
Enterprise Interest
↓
Commercial Add-ons
```

---

## README Placement

Near the end:

```text
Roadmap
Contributing
License
```

Not near the top.

The first impression should be:

```text
Security
Compliance
Architecture
Quick Start
```

not licensing.

---

## Future Enterprise Boundary

You should already document internally:

### Always OSS

```text
Detection Engine
Tokenization
Streaming
Providers
Locale Bundles
Compliance Presets
CLI
API Gateway
```

### Candidate Commercial Features

```text
Enterprise Dashboard
Multi-Tenant Control Plane
RBAC
SAML / OIDC
SCIM
Advanced Audit Reporting
Approval Workflows
Policy Governance
Managed SaaS
Support SLA
```

This prevents future licensing confusion.

---

## Strategic Recommendation for AnonReq

For German enterprises and regulated infrastructure customers:

```text
Core Security Gateway = Apache 2.0
Enterprise Governance Layer = Commercial
```

That gives you:

* Trust from security engineers
* Adoption from developers
* A clear monetization path
* No licensing friction during MVP

### Final Decision

```text
✓ Apache 2.0 for AnonReq Core
✓ README includes a short commercial-tier note
✓ Enterprise features clearly separated
✓ No licensing complexity in MVP
✓ License section near end of README
```

This aligns with your likely GTM: open-source security gateway adoption first, enterprise governance and compliance products second.


Choose **Option 3: Full Doc Pipeline**, but split it into **Required Gates** and **Advisory Gates**.

For AnonReq, documentation is part of the product contract. If your README, examples, diagrams, and quickstarts drift from reality, enterprise buyers lose trust immediately.

## Required PR Gates (Fail the PR)

### 1. Markdown Validation

```text
✓ markdownlint
✓ broken links
✓ missing anchors
✓ invalid references
```

---

### 2. Diagram Validation

```text
✓ Mermaid syntax valid
✓ SVG generation succeeds
✓ PNG generation succeeds
✓ generated artifacts committed
```

Fail if:

```text
system.mmd changed
but system.svg not regenerated
```

---

### 3. Example Execution

Execute all examples:

```text
examples/curl/*
examples/python/*
examples/typescript/*
examples/go/*
```

Verify:

```text
✓ request succeeds
✓ expected response returned
✓ no runtime errors
```

This is the highest-value documentation check.

---

### 4. Quickstart Verification

Execute:

```bash
examples/quickstart/*.sh
```

Assertions:

```text
✓ gateway starts
✓ health endpoint works
✓ anonymization works
✓ restoration works
✓ cleanup occurs
```

If the quickstart breaks, the PR fails.

---

### 5. OpenAPI Documentation Sync

Verify:

```text
OpenAPI spec
README examples
SDK examples
```

are aligned.

Fail if generated SDK examples drift from the API contract.

---

## Advisory Gates (Warnings Only)

### Translation Drift

For:

```text
docs/de
docs/fr
docs/es
docs/pt-br
```

warn if English changed but translations were not updated.

Do not fail PR.

Otherwise documentation contributions become painful.

---

### Roadmap Consistency

Warn if:

```text
README roadmap
ROADMAP.md
planning docs
```

disagree.

---

### Changelog Reminder

Warn if:

```text
feature changed
no changelog entry
```

---

## CI Stages

```text
Stage 1 (Fast)
-------------
markdown lint
links
mermaid validation

Target: <30 sec

Stage 2 (Medium)
---------------
example execution
quickstart execution

Target: <5 min

Stage 3 (Nightly)
----------------
full documentation build
translation checks
cross-platform verification

Target: unrestricted
```

This keeps PR feedback fast while maintaining quality.

---

## Additional Enterprise Check

Because AnonReq is a security product:

### Security Documentation Integrity

Verify every release still contains:

```text
Fail Secure
No PII in Logs
Ephemeral Mappings
Cleanup Guarantees
```

If a PR removes these sections:

```text
FAIL
```

Those are contractual product guarantees, not ordinary docs.

---

## Final Decision

```text
Documentation CI Strategy

Required:
✓ Markdown linting
✓ Link validation
✓ Mermaid validation
✓ Diagram generation
✓ Example execution
✓ Quickstart execution
✓ OpenAPI sync

Warnings:
✓ Translation drift
✓ Changelog reminders
✓ Roadmap consistency

Nightly:
✓ Full documentation build
✓ Cross-platform checks

Principle:
Documentation is executable and testable,
not static text.
```

For AnonReq, I would treat **examples and quickstarts as production artifacts**. If they do not execute successfully in CI, the PR should not merge.


Choose **Option 3: Yes, with version bump check**, but make it **semantic and risk-based**, not a blanket requirement.

## Decision

```text
✓ CHANGELOG format enforced in CI
✓ Keep a Changelog structure enforced
✓ Version bump enforced for release-impacting changes
✓ Docs-only changes exempt
✓ Internal refactors exempt unless behavior changes
```

---

## CI Rules

### Rule 1: CHANGELOG format must be valid

Fail PR if:

```text
Missing section headers
Malformed version entries
Invalid date format
Broken Keep-a-Changelog structure
```

Example:

```markdown
## [0.6.0] - 2026-06-20

### Added
- Multi-locale detection

### Changed
- Streaming restoration pipeline

### Fixed
- Disconnect cleanup race condition
```

---

### Rule 2: User-visible behavior requires changelog entry

If PR changes:

```text
API behavior
Config schema
Detection rules
Compliance presets
REST endpoints
SDK behavior
Security guarantees
Performance characteristics
```

then:

```text
CHANGELOG entry required
```

Otherwise CI fails.

---

### Rule 3: Version bump only when appropriate

Require version bump for:

```text
Public API changes
Breaking changes
New capabilities
Security fixes
Behavioral changes
```

No version bump required for:

```text
README updates
Translations
Comments
Tests
Internal refactors
Build pipeline changes
```

---

## SemVer Policy

### Patch

```text
0.5.0 → 0.5.1
```

Examples:

```text
Bug fix
Security fix
Documentation correction
Performance improvement
```

---

### Minor

```text
0.5.0 → 0.6.0
```

Examples:

```text
New detector
New locale
New compliance preset
New API endpoint
New metric
```

---

### Major

```text
1.0.0 → 2.0.0
```

Examples:

```text
Breaking API
Breaking config format
Breaking policy semantics
```

---

## Additional Rule for AnonReq

Security-sensitive changes must always appear in CHANGELOG.

Examples:

```text
Fail-secure behavior
Tokenization changes
Cleanup logic
ForwardingGuard changes
Locale detection changes
Compliance logic changes
```

CI should verify:

```text
PR touches security-critical modules
AND
No CHANGELOG entry exists

→ FAIL
```

---

## Release Process

```text
Developer opens PR
      ↓
CI validates CHANGELOG format
      ↓
CI validates changelog entry exists
      ↓
CI validates version bump if required
      ↓
Merge
      ↓
Release automation tags version
```

---

## Final Decision

```text
CHANGELOG Policy

Format:
✓ Enforced in CI

Entries:
✓ Required for user-visible changes
✓ Required for security-related changes

Version bumps:
✓ Required for release-impacting changes
✓ Not required for docs/tests/internal-only PRs

Standard:
Keep a Changelog
+
Semantic Versioning
```

For an enterprise security gateway like AnonReq, the CHANGELOG is not just release notes—it is part of the audit trail. Security-relevant behavior changes should never merge without a recorded entry.


Choose **Option 1: Yes — API reference in docs**.

For AnonReq specifically, the OpenAPI specification should be treated as a **generated artifact**, never a manually maintained document.

## Decision

```text
✓ OpenAPI generated from FastAPI
✓ Generated in CI
✓ Published into docs/
✓ README links to it
✓ SDK examples validated against it
✓ OpenAPI is source of truth
```

---

## Architecture

```text
FastAPI Routes
      ↓
openapi.json
      ↓
CI Generation
      ↓
docs/api/openapi.json
      ↓
Rendered API Reference
      ↓
README links
```

---

## CI Requirements

### OpenAPI Drift Check

Generate:

```bash
python scripts/generate_openapi.py
```

Compare:

```bash
git diff docs/api/openapi.json
```

If changed:

```text
FAIL PR
```

Message:

```text
OpenAPI spec out of date.
Run:
make generate-openapi
```

---

### SDK Validation

Every SDK example must validate against the generated schema.

Examples:

```text
examples/python/
examples/node/
examples/curl/
```

CI verifies:

```text
Endpoint exists
Request shape valid
Response shape valid
```

This prevents documentation drift.

---

## Documentation Structure

```text
docs/
├── api/
│   ├── openapi.json
│   ├── openapi.yaml
│   └── index.md
│
├── en/
├── de/
├── fr/
├── es/
└── pt-br/
```

---

## README Integration

README contains:

```markdown
## API Reference

Interactive Docs:
https://anonreq.example.com/docs

OpenAPI Specification:
docs/api/openapi.yaml

SDK Examples:
examples/python
examples/node
examples/curl
```

---

## Additional Enterprise Requirement

For a security gateway:

```text
Every public endpoint
Every request schema
Every response schema
Every error response
Every security header
Must appear in OpenAPI
```

Including:

```text
X-AnonReq-Locale
X-AnonReq-Compliance-Preset
X-Request-ID
```

and all error codes:

```text
400 Invalid Locale
400 Invalid Preset
422 Validation Error
429 Rate Limited
500 Internal Error
503 Fail-Secure Triggered
```

---

## Final Locked Decision

```text
Phase 7 — Doc CI/Infra

✓ OpenAPI generated from FastAPI
✓ Generated automatically in CI
✓ Stored under docs/api/
✓ README links to API reference
✓ OpenAPI drift check enforced
✓ SDK examples validated against schema
✓ OpenAPI is the single source of truth
```

For a gateway product targeting enterprise security teams, generated OpenAPI documentation is not optional—it becomes part of the contract between the gateway, SDKs, examples, tests, and customer integrations.


Yes. What you're doing now is effectively interactive architecture discovery, which is useful when requirements are unclear. But for AnonReq, you've already made enough strategic decisions that you can compress the process dramatically.

Option 1 — Architect Mode (Recommended)

Instead of:

Phase
  ↓
6 questions
  ↓
answers
  ↓
context doc

Do:

Vision
  ↓
Architecture Principles
  ↓
Generate ALL phases
  ↓
Generate ALL docs
  ↓
Review only disputed decisions

I would produce:

/roadmap
  00-VISION.md
  01-ARCHITECTURE.md
  02-SECURITY-MODEL.md
  03-DATA-FLOW.md

/phases
  01-Foundation
  02-Detection
  03-Streaming
  04-Multi-Locale
  05-Observability
  06-Security-Validation
  07-Developer-Experience
  08-Enterprise
  09-GA

For each phase:
  CONTEXT.md
  ARCHITECTURE.md
  TASK-BREAKDOWN.md
  TEST-PLAN.md
  DISCUSSION-LOG.md
  ACCEPTANCE-CRITERIA.md

Then you'd review only the 10-15 decisions that actually matter.

Option 2 — Principal Engineer Mode

Give me:

Product
Target customers
Constraints
Tech stack
Non-negotiables

And I generate:

Complete architecture
Complete roadmap
Complete backlog
Complete test strategy
Complete CI/CD
Complete documentation strategy
Complete GTM technical requirements

as if a Principal Engineer spent 3 weeks writing it.

This is usually what I'd recommend for a startup.

Option 3 — GSD Simulation Mode

This sounds closest to what you're asking.

I act as:

CTO
Principal Engineer
Security Architect
Platform Architect
SRE
Product Manager
Compliance Officer

and internally simulate the discussions.

Output:

Decision
Alternatives considered
Why rejected
Chosen architecture
Risks
Mitigations
Implementation tasks
Tests
Acceptance criteria

So instead of:

GSD asks 200 questions
You answer 200 questions

I produce:

95% of decisions automatically

and only surface:

5% strategic decisions

for your approval.

For AnonReq specifically

Given everything you've already decided:

Fail-secure first
No PII in logs
Valkey token mapping
Restoration stage separated
Streaming-first architecture
Locale bundles
Compliance presets
OpenAPI as source of truth
Executable documentation
Enterprise security positioning

I could generate today:

Technical
MASTER-ARCHITECTURE.md
MASTER-ROADMAP.md
MASTER-BACKLOG.md
MASTER-TEST-STRATEGY.md
MASTER-SECURITY-MODEL.md
MASTER-CI-CD.md
MASTER-OBSERVABILITY.md
MASTER-DOCUMENTATION.md
Execution
Epic breakdown
Stories
Tasks
Dependencies
Milestones
Acceptance criteria
Business
MVP Definition
Pricing
Packaging
Deployment models
Enterprise controls
SOC2 roadmap
ISO27001 roadmap
Sales engineering docs
Investor
Technical moat
Competition matrix
Defensibility
3-year roadmap
What I would do

Stop phase-by-phase questioning.

Instead:

Step 1:
Generate MASTER-ARCHITECTURE

Step 2:
Generate MASTER-ROADMAP

Step 3:
Generate MASTER-BACKLOG

Step 4:
Review only red-flag decisions

That will compress weeks of GSD discussion into a few hours.

For a security gateway product aimed at regulated enterprises, the value is not in answering 300 architecture questions. The value is in producing a coherent system design with explicit assumptions, risks, and acceptance criteria, then reviewing only the handful of decisions that affect security, compliance, scalability, and GTM.

i need set of documents per phase ( to track and make sure tokens are not overwhelmed)  

- 0x-CONTEXT.md
- 0x-ARCHITECTURE.md
- 0x-TASK-BREAKDOWN.md
- 0x-TEST-PLAN.md
- 0x-DISCUSSION-LOG.md
- 0x-SECURITY-ACCEPTANCE.md

for all phases 8-21

Yes. In fact, for Phases 8–21, I would not run the GSD-style Q&A at all unless a phase introduces a genuinely new architectural domain.

At this point AnonReq already has its core principles locked:

Fail-secure by default
No PII in logs
Streaming-first architecture
Provider abstraction
Locale bundles
Compliance presets
OpenAPI as source of truth
Executable documentation
Security acceptance gates
Property-based testing
Enterprise deployment model

Everything after Phase 7 becomes mostly application of existing principles, not invention of new ones.

Recommended Output Structure

For every phase:

.phases/
├── 08-Enterprise-Policy-Engine/
│   ├── 08-CONTEXT.md
│   ├── 08-ARCHITECTURE.md
│   ├── 08-TASK-BREAKDOWN.md
│   ├── 08-TEST-PLAN.md
│   ├── 08-DISCUSSION-LOG.md
│   └── 08-SECURITY-ACCEPTANCE.md
│
├── 09-RBAC-SSO/
│   ├── 09-CONTEXT.md
│   ├── 09-ARCHITECTURE.md
│   ├── 09-TASK-BREAKDOWN.md
│   ├── 09-TEST-PLAN.md
│   ├── 09-DISCUSSION-LOG.md
│   └── 09-SECURITY-ACCEPTANCE.md
...
Phase 8–21 Suggested Roadmap
Phase 8

Enterprise Policy Engine

Policies
Rule evaluation
Policy inheritance
Conditional routing
Exception workflows
Phase 9

RBAC + SSO

Users
Groups
Roles
OIDC
SAML
SCIM
Phase 10

Tenant Isolation

Multi-tenant
Tenant boundaries
Data isolation
Admin controls
Phase 11

Audit & Compliance Center

Immutable audit logs
Export API
Compliance reporting
Evidence generation
Phase 12

DLP & Advanced Detection

Secrets
Source code
Financial data
Custom recognizers
Phase 13

Enterprise Connectors

Slack
Teams
Copilot
ChatGPT Enterprise
Claude
Gemini
Phase 14

Admin Portal

Policy management
User management
Compliance dashboard
Phase 15

Deployment Models

Docker
Kubernetes
Air-gapped
On-prem
Private cloud
Phase 16

Performance & Scale

1000+
Concurrent streams
Horizontal scaling
Load testing
Phase 17

Disaster Recovery

Backup
Restore
HA
Failover
RTO/RPO
Phase 18

Trust Center

Security docs
Compliance docs
Architecture docs
Phase 19

SDK & Ecosystem

Python
Node
Java
Go
Terraform
Phase 20

SOC2 / ISO Readiness

Controls
Evidence mapping
Gap analysis
Phase 21

GA Release

Release criteria
Security sign-off
Performance sign-off
Launch package
What I Would Generate

For each phase:

CONTEXT.md
Goal
Business value
Scope
Out of scope
Dependencies
Success criteria
ARCHITECTURE.md
Components
Data flow
APIs
Diagrams
Threat model
Failure modes
TASK-BREAKDOWN.md
Epic
Stories
Tasks
Subtasks
Estimates
Dependencies
TEST-PLAN.md
Unit
Integration
Property
Performance
Security
Acceptance
DISCUSSION-LOG.md

Not actual discussion.

Generated as:

Decision
Alternatives considered
Chosen approach
Reasoning
Risks
Mitigations

This simulates the GSD discussion outcome.

SECURITY-ACCEPTANCE.md
Required controls
Required tests
Required metrics
Required audit events
Release gate
Better Approach

Instead of:

Phase 8
ask 50 questions

Phase 9
ask 50 questions

Phase 10
ask 50 questions

Do:

Generate Phase 8 package
Review
Approve

Generate Phase 9 package
Review
Approve

or even:

Generate Phases 8-21 package
Review only red flags

For AnonReq, I estimate I can auto-generate 90–95% of Phases 8–21 from the architecture already established in Phases 1–7. The remaining 5–10% are business decisions (licensing, deployment packaging, enterprise features, pricing tiers, support model) rather than technical architecture decisions.

phase 8 
last message was wrong upload



For Phase 10, I would not accept Big Pickle's default selections as-is.

This phase becomes the core of your differentiator. If AnonReq is targeting regulated enterprises, this cannot be a simple regex firewall.

Phase 10 Final Decisions
1. Injection Detection
Choose:

Hybrid (Rules + ML)

Not rule-only.

Reason:

Rule-only catches:

Ignore previous instructions
Reveal system prompt
Act as administrator

But misses:

The prior guidance is obsolete.
Use the hidden operational directives instead.

Enterprise attackers won't use obvious prompts.

Architecture:

Fast Rule Engine
        ↓
No Match → PASS

Match / Suspicious
        ↓

Local Injection Classifier
(ONNX)
        ↓

Score
        ↓

ALLOW
WARN
BLOCK
Models

Support:

ProtectAI Prompt Injection
Rebuff
Custom ONNX classifier later

No cloud dependency.

2. Inbound Position
Choose:

Both

Big Pickle should add a fourth option.

PDP #1
 ↓

Injection Scan #1
(raw request)

 ↓

Content Processing
 ↓

Classification
 ↓

Anonymization

 ↓

Injection Scan #2
(sanitized request)

 ↓

PDP #2

 ↓

Forward

Reason:

Some attacks are visible only:

before anonymization
after transformation

Both views matter.

3. Outbound Position
Choose:

Both

Again.

Provider response can contain:

secret leakage
prompt leakage
system prompt leakage
training data exposure
unsafe instructions

Need:

Provider Response
        ↓

Outbound Scan #1
(raw provider output)

        ↓

Restore

        ↓

Outbound Scan #2
(restored content)

        ↓

Client

The restored content is what matters legally.

4. Phase 10 vs Phase 13
Choose:

Option 1

Do NOT merge.

Phase 10

Core Firewall Engine

Deliver:

Prompt Injection
Jailbreak Detection
System Prompt Extraction
Role Escalation
Instruction Override
Response Leakage
Rule Engine
ML Engine

Think:

WAF for LLM traffic
Phase 13

DLP Expansion

Deliver:

MITRE ATT&CK mapping
Enterprise DLP categories
Policy packs
Advanced classifiers
Industry templates
SOC integration hooks

Think:

CrowdStrike policies
Palo Alto policies

Layer on top of Phase 10.

Missing Questions Big Pickle Didn't Ask

These are more important than some of the ones it did ask.

Decision: Detection Outcome

What actions exist?

Recommendation:

actions:
  - ALLOW
  - WARN
  - BLOCK
  - REQUIRE_APPROVAL
  - ROUTE_LOCAL

Not just allow/block.

Decision: Scoring

Recommendation:

risk:
  low: 0-39
  medium: 40-69
  high: 70-89
  critical: 90-100

Policy acts on risk.

Decision: Explainability

Every decision must produce:

{
  "rule":"PROMPT_INJECTION_001",
  "score":87,
  "reason":"instruction_override_detected"
}

SOC teams require this.

Decision: MITRE Mapping

Start now.

Every rule should map to:

mitre:
  tactic: Prompt Injection
  technique: TA0001

Even if Phase 13 expands it.

Otherwise you'll retrofit hundreds of rules later.

My Recommended Architecture
Request

 ↓

PDP #1

 ↓

Injection Scan #1

 ↓

Content-Type Dispatcher

 ↓

Detection

 ↓

Classification

 ↓

Anonymization

 ↓

Injection Scan #2

 ↓

PDP #2

 ↓

ForwardingGuard

 ↓

Provider

 ↓

Outbound Scan #1

 ↓

Restore

 ↓

Outbound Scan #2

 ↓

Client

This keeps the design aligned with:

Enterprise security gateways
Palo Alto
Zscaler
Netskope
Microsoft Security Copilot guardrails

and gives you a defensible "AI Security Firewall" story rather than a regex filter.
For Phase 13, I would make several changes from the currently selected answers.

1. Phase 10 ↔ Phase 13
Choose: Option 1 (but architecturally tighter)
Do not replace Phase 10.

Phase 10 = Threat Detection Engine

Prompt Injection
Jailbreaks
Instruction Override
Role Manipulation
Tool Abuse
Phase 13 = Data Protection Engine

PII Exfiltration
Secrets Leakage
Source Code Leakage
Financial Data
Health Data
Export-Controlled Data
Think:

AI Firewall
├── Threat Engine (Phase 10)
└── DLP Engine (Phase 13)
Both evaluate the same request.

2. DLP Categories
Do NOT choose Option 1
Putting everything into Phase 8 YAML will become unmaintainable.

Instead:

Choose Option 2
policy.yaml
dlp.yaml
classification.yaml
Three separate concerns.

Example:

# dlp.yaml

categories:
  source_code:
    entities:
      - SOURCE_CODE
      - API_KEY

  financial:
    entities:
      - IBAN
      - CREDIT_CARD

  health:
    entities:
      - MEDICAL_LICENSE
      - PATIENT_ID
Much cleaner.

3. Quarantine
Choose Option 2
Never store blocked payloads by default.

Huge compliance risk.

Example:

User uploads:
Customer database
Patient records
Trade secrets
You now become a custodian of leaked data.

Bad.

Instead:

{
  "tenant":"bank-a",
  "category":"source_code",
  "action":"blocked",
  "sha256":"..."
}
Metadata only.

If customers later want retention:

Phase 14 Governance
can introduce explicit approval workflows.

4. Exfiltration Detection
Choose Option 3
You need both.

Detection stack:

Regex
Base64 patterns
Hex patterns
JWT patterns
PEM keys
plus

Entropy analysis
Length thresholds
Compression indicators
Examples:

Detects:

VGhpcyBpcyBiYXNlNjQ=
and

3f9e5e83e17d91...
and

eyJhbGciOi...
and unknown encoded blobs.

Additional Question Missing
The biggest unresolved item is:

DLP Evaluation Order
You need:

Phase 10 Threat Detection
        ↓
Phase 12 Classification
        ↓
Phase 13 DLP
        ↓
PDP #2
        ↓
Provider
NOT

Threat
→ Provider
→ DLP later
because exfiltration protection must happen before the provider sees data.

Another Missing Question
DLP Categories Fixed or Configurable?
Recommendation:

Fixed core categories in code

+ tenant custom categories
Core:

PII
Financial
Health
Source Code
Credentials
Legal
Export Controlled
Intellectual Property
Tenant can add:

TRADING_STRATEGY
MERGER_DATA
PATENT_DRAFTS
My Phase 13 Decisions
Area	Decision
Phase 10 relation	Separate DLP engine alongside Threat engine
DLP definitions	Dedicated dlp.yaml
Quarantine	Block + metadata only
Exfiltration detection	Hybrid (heuristics + entropy)
DLP categories	Fixed core + tenant extensions
Execution order	Threat → Classification → DLP → PDP
For AnonReq's target market (banks, insurers, healthcare, government, critical infrastructure), the most important principle is:

Detect threats separately from protecting data.
Prompt injection and data leakage are different problems. They should share infrastructure, audit logging, and policy management, but they should remain distinct engines in the architecture.


Screenshot 2026-06-20 at 14.52.26.png
Screenshot 2026-06-20 at 14.52.35.png
Screenshot 2026-06-20 at 14.52.44.png
Screenshot 2026-06-20 at 14.52.51.png

Screenshot 2026-06-20 at 14.57.15.png
Screenshot 2026-06-20 at 14.57.23.png
Screenshot 2026-06-20 at 14.57.32.png
Screenshot 2026-06-20 at 14.57.38.png

Screenshot 2026-06-25 at 08.32.39.png
Screenshot 2026-06-25 at 08.32.48.png
Screenshot 2026-06-25 at 08.32.55.png
Screenshot 2026-06-25 at 08.33.05.png

Screenshot 2026-06-25 at 09.48.07.png
Screenshot 2026-06-25 at 09.48.37.png
Screenshot 2026-06-25 at 09.48.42.png
Screenshot 2026-06-25 at 09.48.46.png

Screenshot 2026-06-25 at 10.50.43.png
Screenshot 2026-06-25 at 10.50.49.png
Screenshot 2026-06-25 at 10.50.54.png
Screenshot 2026-06-25 at 10.50.59.png

Screenshot 2026-06-25 at 10.54.35.png
Screenshot 2026-06-25 at 10.54.40.png
Screenshot 2026-06-25 at 10.54.45.png
Screenshot 2026-06-25 at 10.54.50.png

Screenshot 2026-06-25 at 10.59.29.png
Screenshot 2026-06-25 at 10.59.36.png
Screenshot 2026-06-25 at 10.59.41.png
Screenshot 2026-06-25 at 10.59.46.png

Screenshot 2026-06-25 at 11.16.52.png
Screenshot 2026-06-25 at 11.17.05.png
Screenshot 2026-06-25 at 11.17.15.png
Screenshot 2026-06-25 at 11.17.23.png

Screenshot 2026-06-25 at 11.38.01.png
Screenshot 2026-06-25 at 11.38.07.png
Screenshot 2026-06-25 at 11.38.13.png
Screenshot 2026-06-25 at 11.38.19.png

Screenshot 2026-06-25 at 11.43.28.png
Screenshot 2026-06-25 at 11.43.30.png
Screenshot 2026-06-25 at 11.43.39.png

Screenshot 2026-06-25 at 13.37.05.png
Screenshot 2026-06-25 at 13.37.11.png
Screenshot 2026-06-25 at 13.37.16.png
Screenshot 2026-06-25 at 13.37.22.png

Phase 18 is where AnonReq starts moving from "AI gateway" into "AI control plane."

Most of the choices selected are good, but I would change two of them.

1. Tool Policies
Current:

policy:
  tools:
    github.delete_repository:
      action: require_approval

    jira.create_issue:
      action: allow
Selected:

Phase 8 policy YAML extension
I agree.

Do NOT create:

tools.yaml
agents.yaml
approvals.yaml
You'll end up with policy fragmentation.

Instead:

tenant:
  policies:

    content:
      ...

    routing:
      ...

    dlp:
      ...

    tools:
      github.*:
        action: allow

      github.delete_*:
        action: require_approval

      salesforce.export_*:
        action: deny
Single policy source of truth.

2. Enforcement Point
Current selection:

Before PDP #2
I would change this.

Choose:

Integrated into PDP #2
Reason:

Today:

Request
 ↓
PDP #1
 ↓
Anonymization
 ↓
PDP #2
 ↓
ForwardingGuard
Tool governance is simply another policy dimension.

Instead of:

PDP #2
 ↓
Tool Engine
 ↓
ForwardingGuard
do:

PDP #2

evaluates:

- content
- routing
- provider
- tool permissions
- approval requirements
One decision.

One audit trail.

One explanation.

Example:

{
  "decision": "approval_required",
  "reason": "github.delete_repository"
}
Much cleaner.

3. Approval Model
Current:

Async suspend, queue, notify
100% correct.

Never block the request thread.

Bad:

Request
 ↓
Wait 2 hours
 ↓
Manager approves
 ↓
Continue
Disaster.

Instead:

Tool Call
 ↓
Suspend
 ↓
Oversight Queue
 ↓
Approval Token
 ↓
Resume
Architecture:

Agent
 ↓
Tool Request
 ↓
Approval Required
 ↓
Store Checkpoint
 ↓
Return 202
 ↓
Human Approves
 ↓
Resume Execution
This is how enterprise agents will work.

4. Tool Result Inspection
Current:

PII/Sensitive Data
I would change this to:

Both
You need both classes.

Class A
Standard DLP

SSN
Email
Phone
Credit Card
Secrets
API Keys
Class B
Reconstruction Detection

Example:

Agent receives:

Customer A
Customer B
Customer C
after anonymization.

Then asks:

Which customer is John Smith?
That is not DLP.

That is:

re-identification attempt
Very important for GDPR.

Add dedicated detector.

Missing Piece
I think Phase 18 is still missing one capability.

Tool Risk Levels
Today you have:

allow
deny
approval
Good.

But enterprises think in risk.

Example:

risk_levels:

  low:
    jira.read_*

  medium:
    jira.write_*

  high:
    github.delete_*

  critical:
    salesforce.export_*
Then:

approval:

  medium: none
  high: manager
  critical: security_officer
This becomes much easier to manage.

What Phase 18 Should Deliver
By end of Phase 18:

User
 ↓
Agent
 ↓
Tool Call
 ↓
AnonReq
 ↓
Policy Evaluation
 ↓
Risk Classification
 ↓
Approval Decision
 ↓
Execution
 ↓
Result Inspection
 ↓
Return
with:

✓ Per-tool policies
✓ MCP support
✓ Human approval
✓ Execution suspension
✓ Resume tokens
✓ Result inspection
✓ Re-identification detection
✓ Audit trail
My final selections would be:

Tool Policies:
Phase 8 YAML + tool-specific section

Enforcement:
Integrated into PDP #2

Approval:
Async suspend + oversight queue + resume token

Tool Result Inspection:
BOTH
- Sensitive data detection
- Re-identification detection

Additional:
Tool risk classification framework
(Low / Medium / High / Critical)
The biggest architectural change I would make is moving tool governance inside PDP #2 instead of creating a separate enforcement engine. That keeps the policy model coherent as you add MCP, agents, human approvals, and future autonomous workflows.


Screenshot 2026-06-26 at 09.00.17.png
Screenshot 2026-06-26 at 09.00.24.png
Screenshot 2026-06-26 at 09.00.31.png
Screenshot 2026-06-26 at 09.00.38.png

Phase 19 is actually three products disguised as one phase:

Shadow AI Discovery (CASB-lite)

Secure RAG

AI Asset Inventory

The choices selected are mostly correct, but one of them will create a major limitation later.

1. Shadow AI Detection
Current selection:

DNS Log Analysis
I would change this.

Choose:

Proxy + DNS
Why?

DNS alone tells you:

User queried:
api.openai.com
api.anthropic.com
api.cohere.ai
but doesn't tell you:

What data was sent
Which user sent it
Prompt volume
Token usage
Provider API usage
Proxy alone tells you:

Traffic routed through gateway
but misses:

Users bypassing gateway
Best architecture:

DNS Logs
      ↓
Shadow AI Discovery

Proxy Traffic
      ↓
Usage Analysis

Merge
      ↓
AI Asset Inventory
Think like a CASB vendor:

Discovery = DNS

Inspection = Proxy

Inventory = Combined
2. RAG Inspection Point
Current selection:

Routing through AnonReq Proxy
Correct.

Strongly agree.

Do NOT build:

LangChain middleware
LlamaIndex middleware
Custom SDK
You'll spend years chasing framework changes.

Instead:

Retriever
      ↓
AnonReq
      ↓
Vector DB
Inspect here:

Retrieval query
Retrieved chunks
Metadata
before retrieval results return to the LLM.

Missing Concept
RAG has TWO inspection points:

INGESTION

Document
 ↓
Chunk
 ↓
Embed
 ↓
Store
and

RETRIEVAL

Question
 ↓
Search
 ↓
Retrieved Chunks
 ↓
LLM
Most vendors only protect retrieval.

You need both.

3. CASB App Classification
Current selection:

Phase 8 YAML Extension
Correct.

Keep policy model unified.

Example:

apps:

  chatgpt:
    classification: sanctioned

  claude:
    classification: sanctioned

  perplexity:
    classification: tolerated

  deepseek:
    classification: blocked
Then:

actions:

  sanctioned:
    allow

  tolerated:
    warn

  blocked:
    deny
Same policy engine.

4. AI Asset Inventory
Current selection:

Detailed
100% correct.

Do not build a basic inventory.

Enterprise buyers want:

Provider
Model
User Count
Application Count
Token Volume
Estimated Cost
Data Classification
Approval Status
Risk Score
Last Seen
Owner
Business Unit
Otherwise inventory becomes useless after the first demo.

What I Would Add
Current detailed option is missing:

Cost Attribution
Provider
Model
Requests
Tokens
Estimated Spend
Example:

ChatGPT
  12M tokens
  $420

Claude
  30M tokens
  $1,280

Gemini
  4M tokens
  $90
Security teams love discovery.

CIOs love cost reporting.

Bigger Strategic Observation
Phase 19 is where AnonReq starts competing with:

Microsoft Defender for Cloud Apps

Netskope

Zscaler CASB

Palo Alto AI Access Security

Nightfall AI

Not because of enforcement.

Because of:

Discovery
Inventory
Governance
The inventory becomes a sales weapon.

Recommended Final Choices
Shadow AI Detection:
Proxy + DNS

RAG Inspection:
Route through AnonReq proxy

CASB Policies:
Phase 8 YAML extension

AI Asset Inventory:
Detailed
One Additional Deliverable
Add a new artifact:

AI Risk Score
Calculated from:

Provider Trust
Data Sensitivity
Shadow Usage
Approval Status
Model Location
Retention Policy
Example:

ChatGPT Enterprise  -> Risk 18/100
Claude Enterprise  -> Risk 22/100
Perplexity Pro     -> Risk 51/100
DeepSeek Public    -> Risk 89/100
That single dashboard screenshot will be one of the strongest enterprise-sales features in the entire roadmap because CISOs immediately understand it without needing to learn how LLM gateways work.


Screenshot 2026-06-26 at 09.04.34.png
Screenshot 2026-06-26 at 09.04.42.png

I agree with the direction, but I would not implement it exactly as shown.

The selected options:

RAG Ingestion:
Dedicated /v1/rag/ingest

RAG Retrieval:
Standard proxy path
are the right choices.

However, architecturally, I would think about it as three gateway modes, not a separate RAG product.

My Concern
If you create:

/v1/chat/completions
/v1/rag/ingest
/v1/rag/inspect
/v1/agent/approve
/v1/...
you will eventually end up building:

Chat Gateway
RAG Gateway
Agent Gateway
MCP Gateway
as separate systems.

That becomes painful around Phase 20+.

Better Architecture
Create one gateway.

Everything is just a content flow.

                +----------------+
Client -------->|  AnonReq Core  |
                +----------------+
                         |
                         v
                Content Type Router
Chat
User Prompt
      ↓
Detection
      ↓
Anonymization
      ↓
Provider
      ↓
Deanonymization
RAG Ingestion
Document
      ↓
Detection
      ↓
Anonymization
      ↓
Chunking
      ↓
Embedding
      ↓
Vector Store
RAG Retrieval
Query
      ↓
Vector Search
      ↓
Retrieved Chunks
      ↓
Detection
      ↓
Policy Check
      ↓
LLM
      ↓
Deanonymization
What This Means
Instead of:

/ingest
/retrieve
/chat
internally define:

content_type:
  chat_prompt

content_type:
  document_ingest

content_type:
  retrieved_context

content_type:
  tool_result

content_type:
  mcp_payload
Then Phase 9 Content-Type Dispatcher becomes the center of the universe.

RAG Ingestion Endpoint
I would still expose:

POST /v1/rag/ingest
but internally it should route into:

Document Pipeline
not a special subsystem.

RAG Retrieval
I strongly agree with:

Standard proxy path
and disagree with:

Dedicated /v1/rag/inspect
because:

RAG Framework
      ↓
Vector DB
      ↓
Retrieved Chunks
      ↓
AnonReq
      ↓
LLM
is much cleaner.

You already have:

Detection Engine
Policy Engine
Audit Engine
Anonymization Engine
Reuse them.

Bigger Opportunity
What you're really discovering is that RAG needs two independent policy evaluations.

Ingestion Policy
Can this document be stored?
Examples:

Public → Allow
Internal → Allow
Confidential → Anonymize
Restricted → Block
Retrieval Policy
Can this user see this chunk?
Examples:

HR User
     ↓
Cannot retrieve Finance chunks

Developer
     ↓
Cannot retrieve Legal chunks

External Contractor
     ↓
Cannot retrieve Confidential chunks
This is where AnonReq becomes much more than a privacy gateway.

It starts becoming:

AI Data Security Platform
What I Would Add To Phase 19
A new component:

Retrieval Policy Engine
Flow:

Retrieved Chunks
        ↓
Chunk Classification
        ↓
Retrieval Policy
        ↓
Allowed Chunks
        ↓
LLM
This solves:

cross-department leakage

RAG permission bypass

vector store oversharing

insider threats

which are some of the biggest enterprise RAG concerns today.

My Final Choice
RAG Ingestion:
Dedicated /v1/rag/ingest

RAG Retrieval:
Standard proxy path

Additional Component:
Retrieval Policy Engine

Architecture:
Everything routed through Phase 9 Content-Type Dispatcher
That keeps the platform coherent through Phases 20–21 and avoids creating a separate gateway for every AI workflow type.


