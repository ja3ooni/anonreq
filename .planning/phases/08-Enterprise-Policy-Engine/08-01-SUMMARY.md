# Phase 08, Plan 01 — Enterprise Policy Engine Foundation

## Result: All 102 tests passing

## Files Created

### Source (`src/anonreq/policy/`)
| File | Description | Lines |
|------|-------------|-------|
| `src/anonreq/policy/__init__.py` | Package init, re-exports all model types | 16 |
| `src/anonreq/policy/models.py` | Pydantic v2 models: PolicyAction enum, PolicyRule, PolicyDecision, RateLimitConfig, SpendBudget, UsageRecord, ResidencyRule | 127 |
| `src/anonreq/policy/config.py` | YAML policy loader: PolicyConfig model, load_policy_config(), validate_policy_bundle() | 73 |
| `src/anonreq/policy/store.py` | PolicyStore with Valkey-backed versioned policy cache | 104 |
| `src/anonreq/policy/usage_limiter.py` | UsageLimiter: atomic INCR-based RPM/TPM/concurrent counters, fail-closed 503 | 91 |
| `src/anonreq/policy/spend_controller.py` | SpendController: INCRBYFLOAT daily/monthly spend tracking, UTC boundary resets | 116 |
| `src/anonreq/policy/residency_router.py` | ResidencyRouter: allowed/blocked region checks with configurable fallback | 57 |

### Config
| File | Description | Lines |
|------|-------------|-------|
| `config/policy.yaml` | Default policy configuration with 2 sample rules | 26 |
| `config/policy.example.yaml` | Documented example with all fields explained | 63 |

### Tests
| File | Description | Tests |
|------|-------------|-------|
| `tests/policy/__init__.py` | Test helpers: `create_temp_policy_yaml()`, `sample_usage_record()` | — |
| `tests/policy/test_models.py` | Model validation tests: 7 test classes, parametrized checks | 45 |
| `tests/policy/test_config.py` | Config loading tests: YAML parse, validation, bundle checks | 14 |
| `tests/policy/test_store.py` | PolicyStore tests: caching, tenant scoping, invalidation, versioning | 13 |
| `tests/policy/test_usage_limiter.py` | UsageLimiter tests: RPM/TPM/concurrent limits, fail-closed, incr/decr | 12 |
| `tests/policy/test_spend_controller.py` | SpendController tests: daily/monthly budgets, record_spend, get_usage | 10 |
| `tests/policy/test_residency_router.py` | ResidencyRouter tests: allowed/blocked regions, fallback, unknown tenant | 8 |

## Files Modified

| File | Change |
|------|--------|
| `tests/conftest.py` | Added Phase 8 shared fixtures: policy_config, mock_cache_manager, policy_store, usage_limiter, spend_controller, residency_router, sample_policy_rules, tenant_id |

## Test Results

```
============================= 102 passed in 0.33s ==============================
```

## Requirements Covered
- **RATE-01**: Rate limit config with RPM/TPM/concurrent fields, strict validation
- **RATE-04**: Fail-closed on cache error returns BLOCK with 503
- **SOVR-01**: Tenant-scoped policy loading with global defaults inheritance
- **CLASS-01**: PolicyAction enum with BLOCK/ALLOW/ROUTE_LOCAL/FLAG_AND_FORWARD/MONITOR

## Architecture Highlights
- All Pydantic models use `model_config = {"extra": "forbid"}`
- YAML loading uses `yaml.safe_load()` exclusively
- PolicyStore uses key format `anonreq:policy:{tenant_id}:rules` with version hash
- UsageLimiter/SpendController use atomic Redis pipelines with 60s TTL windows
- All cache errors return BLOCK with enforcement="503" (fail-closed)
- Region codes validated against pattern `^[a-z]{2}(-[a-z0-9]+)+-\d+$`
