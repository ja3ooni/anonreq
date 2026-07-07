# Feature Landscape — AnonReq v1.5 Enterprise Hardening

**Domain:** Self-hosted AI security & anonymization gateway
**Researched:** 2026-07-07
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Enterprise Expects These)

Features that enterprise customers assume exist. Missing these = product feels incomplete or risky.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| CI/CD pipeline | Every enterprise project requires automated testing in CI before merge | Low | GitHub Actions — pytest, ruff, mypy. Specified in HYG-01, HYG-02. |
| Code quality enforcement (ruff/mypy) | Enterprise security audits scan for code quality. Unchecked projects get flagged. | Low | Configured in Phase 1. Must pass before subsequent phases. |
| Docker security hardening | Security teams scan exposed ports. Default config must not expose internal services. | Low | Phase 1.3 — remove host ports from non-gateway services. |
| Public compliance evidence | Enterprise prospects check Trust Center before evaluation (Vanta baseline). | Medium | Phase 2 — Trust Center portal. SLO, compliance frameworks, metrics, security posture. |
| Multi-language documentation | Global enterprises need documentation in local languages. English-only limits TAM. | Low-Med | Phase 3 — 6 new languages (FR, ES, PT, IT, AR, NL). Content work, not code. |
| Commercial licensing | Legal/procurement requires license terms. Apache 2.0 alone insufficient for enterprise add-ons. | Medium | Phase 4.3 — HMAC-SHA256 license validation. Core remains free. |
| Secret detection (API keys, tokens) | DLP requirements include detecting leaked credentials, not just PII. | Medium | Phase 4.1 — Custom recognizers for API keys, AWS keys, GitHub tokens, internal hostnames. |
| Continuous compliance monitoring | SOC 2 / ISO 27001 require ongoing evidence collection, not just point-in-time audits. | Medium | Phase 4.2 — Evidence endpoint, automated snapshots. |

### Differentiators (Competitive Advantage)

Features that set AnonReq apart from alternatives (e.g., NodeShift, open-source proxies).

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| HMAC-based licensing without phone-home | Air-gapped and sovereign deployments don't need internet to validate licenses. Competitors often require SaaS phone-home. | Low | `hmac` from stdlib. Zero external calls. |
| Public Trust Center as part of open-source gateway | Most open-source AI gateways lack a dedicated compliance evidence portal. Having one builds trust. | Medium | Config-gated, public endpoints. Reads from existing SLO engine. |
| Custom recognizer gating by license tier | Enterprise pays for advanced detection; free tier gets basic PII. Clean monetization without bifurcating the codebase. | Medium | License gate on recognizer loading. Same code path for both tiers. |
| Integrated translation manifest | Most projects have ad-hoc translation. A manifest creates accountability and audit trail for enterprise compliance. | Low | `docs/TRANSLATION_MANIFEST.md` with per-file status. |

### Anti-Features (Avoid These)

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Phone-home license validation | Breaks air-gapped deployments. Adds latency. Creates dependency on external service availability. | HMAC-SHA256 with local key. Zero network calls. |
| Modifying Presidio sidecar for custom recognizers | Forking the upstream docker image creates maintenance burden. Presidio updates become merge headaches. | Route custom recognizers through existing `RegexDetector` pipeline. Only use Presidio for NER-based entities. |
| Trust Center with auth | Defeats the purpose — compliance evidence is for public consumption. Auth reduces trust. | Public endpoints with IP-based rate limiting only. |
| Gating the core anonymization pipeline | Kills adoption. Core PII detection/tokenization must remain free. Only Appliance tier additions are gated. | License check only on `trust_center`, `ai_firewall`, `soc_integration`, `advanced_detection`, `compliance_monitoring` features. |
| Real-time metrics in Trust Center | Each `/v1/trust/status` call to Prometheus `REGISTRY.get_sample_value()` is O(1) but could become a bottleneck. | Snapshot metrics to a pre-computed cache key at a configurable interval. Not needed for MVP (low traffic portal). |

## Feature Dependencies

```
Phase 1 (CI/CD, ruff/mypy, Docker security)
  ├── No dependencies
  └── Required by: Phase 2, Phase 4

Phase 2 (Trust Center)
  └── Requires: Phase 1 (CI for automated testing)
  └── Data sources: SLOEngine, PresetEngine, prometheus_client REGISTRY
      (all available via app.state — no new infrastructure)

Phase 3 (Documentation)
  └── No code dependencies
  └── Content mirroring only

Phase 4 (Guardrails)
  ├── Requires: Phase 1 (CI for automated testing)
  ├── Requires: Phase 2 (licensing gates the Trust Center)
  └── Internal dependency chain:
      4.1 (Custom recognizers) → DetectonStage pipeline
      4.2 (Compliance evidence) → AuditChainService, SLOEngine, governance records
      4.3 (License module) → Used by 4.1 (gates recognizer loading) and Phase 2
```

### Dependency Notes

- **Custom recognizers (4.1) require DetectionStage modification:** Pipeline manager must accept new `custom_recognizers` parameter. This is a small change following the existing MNPI recognizer pattern.
- **License module (4.3) is a prerequisite for Trust Center gating:** Even though SPEC says Trust Center is "core" tier, the license module must exist for the gate to function. Phase 4 depends on Phase 2 because the Trust Center needs a license gate.
- **Compliance evidence (4.2) requires governance record persistence:** Needs PostgreSQL (for `AuditChainService`) and MinIO (for evidence archive). These are optional in the observability profile — evidence collection should warn if dependencies are missing, not crash.

## Phase-by-Phase Feature Breakdown

### Phase 1 — Engineering Hygiene (3 features)

| Feature | Type | Complexity | Verification |
|---------|------|------------|-------------|
| CI/CD workflow (`.github/workflows/test.yml`) | Table stake | Low | Workflow passes on PR |
| ruff + mypy enforcement | Table stake | Low | `ruff check src/ tests/`, `mypy src/` pass |
| Secure Docker defaults | Table stake | Low | `docker compose up` exposes only port 8080 on host |

### Phase 2 — Trust Center (1 feature, 4 endpoints)

| Endpoint | Type | Sources | Notes |
|----------|------|---------|-------|
| `GET /v1/trust/status` | Table stake | `SLOEngine.get_all_compliance("*")` | Aggregated SLO compliance summary |
| `GET /v1/trust/compliance` | Table stake | `PresetEngine.list_presets()` | Supported frameworks + presets list |
| `GET /v1/trust/metrics` | Differentiator | `prometheus_client.REGISTRY` | Aggregate throughput, entity counts, uptime |
| `GET /v1/trust/security` | Differentiator | `config/trust_center.yaml` | Security posture summary |

### Phase 3 — Documentation Parity (1 feature)

| Item | Type | Languages | Notes |
|------|------|-----------|-------|
| 6 new language directories | Table stake | FR, ES, PT, IT, AR, NL | Mirror `docs/en/` structure |
| Translation manifest | Differentiator | All | Tracks review state per file |
| Glossary | Differentiator | All | Technical term translations |

### Phase 4 — Enterprise Guardrails (3 features)

| Feature | Type | Sub-components | Complexity |
|---------|------|----------------|------------|
| License module | Table stake | `models.py`, `validator.py`, `deps.py`, `router.py` | Medium |
| Custom secret detection recognizers | Table stake | 4 recognizer modules, config YAML, DetectionStage integration | Medium |
| Compliance evidence collection | Differentiator | Evidence endpoint, scheduled snapshots, archive storage | Medium |

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| CI/CD pipeline (Phase 1) | HIGH — prerequisite for all enterprise adoption | LOW — standard GitHub Actions YAML | P1 |
| Code quality enforcement (Phase 1) | HIGH — security audit requirement | LOW — ruff + mypy config | P1 |
| Docker security (Phase 1) | HIGH — security team gate | LOW — remove port bindings | P1 |
| Trust Center (Phase 2) | HIGH — Vanta baseline for enterprise sales | MEDIUM — new module with 3 data sources | P1 |
| License module (Phase 4.3) | HIGH — commercial gating requirement | MEDIUM — HMAC + deps + admin endpoint | P1 |
| Custom recognizers (Phase 4.1) | MEDIUM — DLP requirement | MEDIUM — 4 modules + config + integration | P2 |
| Compliance evidence (Phase 4.2) | MEDIUM — compliance automation | MEDIUM — evidence schema + scheduled collection | P2 |
| Documentation translation (Phase 3) | MEDIUM — global enterprise requirement | LOW-MED — content work, no code | P2 |

## Sources

- `.planning/v1.5-SPEC.md` — Canonical feature specification for all four phases
- `.planning/PROJECT.md` — Project context and validated features
- `src/anonreq/services/slo_engine.py` — SLOEngine interface (Trust Center data source)
- `src/anonreq/compliance/engine.py` — PresetEngine interface (compliance framework data source)
- `src/anonreq/detection/recognizers/mnpi.py` — Existing custom recognizer pattern
- `src/anonreq/admin/config.py` — AtomicConfigRegistry hot-reload pattern
- `docs/en/` — Source documentation structure for translation mirroring

---
*Feature research for: AnonReq v1.5 Enterprise Hardening*
*Researched: 2026-07-07*
