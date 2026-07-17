# Security Vulnerability Scan Report

**Date:** 2026-07-17  
**Project:** AnonReq AI Security Gateway  
**Scanner:** Manual security review + automated checks

---

## Executive Summary

This scan identified **1 critical**, **2 high**, **3 medium**, and **4 low/info** findings. The critical finding involves hardcoded API keys in the `.env` file. The project demonstrates strong security practices in several areas (logging allowlist, fail-secure error handling, YAML safe loading, path traversal protection), but has configuration issues that need remediation.

---

## Findings

### CRITICAL

| # | Severity | File | Line | Finding | Recommendation |
|---|----------|------|------|---------|----------------|
| 1 | **CRITICAL** | `.env` | 6, 8, 12 | **Hardcoded API keys in environment file** — The `.env` file contains actual OpenAI API keys (`sk-proj-...`) and placeholder API keys. If this file is ever committed to version control or exposed, all credentials are compromised. | Never store real credentials in `.env`. Use `.env.example` with placeholder values only. Rotate the exposed OpenAI API keys immediately. Consider using a secrets manager (Vault, AWS Secrets Manager) for production deployments. |

### HIGH

| # | Severity | File | Line | Finding | Recommendation |
|---|----------|------|------|---------|----------------|
| 2 | **HIGH** | `docker-compose.yml` | 91-95, 170-171 | **Hardcoded default credentials in Docker Compose** — MinIO defaults to `minioadmin`/`minioadmin` credentials. PostgreSQL uses `anonreq`/`anonreq` for user/password. These are well-known defaults. | Use strong, unique passwords for all services. Load credentials from environment variables or a secrets manager. Document the requirement to change defaults in production. |
| 3 | **HIGH** | `docker-compose.yml` | 72 | **Container runs as root initially** — The `anonreq` service starts as `root` (line 72: `user: root`) before switching to the `anonreq` user via `su`. While it does drop privileges, the initial root execution could be exploited if a vulnerability exists in the startup commands. | Use Docker's `USER` directive directly or run `chown` in a build step. Avoid runtime privilege escalation patterns. |

### MEDIUM

| # | Severity | File | Line | Finding | Recommendation |
|---|----------|------|------|---------|----------------|
| 4 | **MEDIUM** | `docker-compose.yml` | 49, 166 | **Docker images use `latest` tag** — `mcr.microsoft.com/presidio-analyzer:latest` and `minio/minio:latest` pull unversioned images. This can introduce breaking changes or vulnerabilities from upstream updates. | Pin images to specific version tags (e.g., `presidio-analyzer:2.0.47`, `minio/minio:RELEASE.2024-06-13T22-53-53Z`). Use Dependabot or Renovate for automated updates. |
| 5 | **MEDIUM** | `src/anonreq/pipeline/provider.py` | 58 | **HTTP client without explicit timeout configuration** — While timeout is passed to `httpx.AsyncClient`, there's no explicit `follow_redirects=False` setting. By default, httpx follows redirects, which could be used for SSRF if an attacker can influence the upstream URL. | Explicitly set `follow_redirects=False` on the httpx client to prevent redirect-based SSRF attacks. Validate upstream URLs against an allowlist. |
| 6 | **MEDIUM** | `src/anonreq/cache/manager.py` | 68 | **Non-cryptographic random for retry jitter** — Uses `random.uniform()` for retry jitter calculation. While this is not security-sensitive (jitter only), the `random` module uses a predictable PRNG. | Low risk for this use case, but consider using `secrets.randbelow()` or `random.SystemRandom()` for consistency with security best practices. |

### LOW / INFO

| # | Severity | File | Line | Finding | Recommendation |
|---|----------|------|------|---------|----------------|
| 7 | **LOW** | `.env.example` | 25-29 | **Example credentials in template** — `.env.example` contains `minioadmin`/`minioadmin` defaults. While this is a template, it normalizes weak default usage. | Add comments indicating these must be changed in production. Consider removing defaults and requiring explicit configuration. |
| 8 | **INFO** | Multiple | — | **Strong security practices observed** — The project implements several security best practices: (1) Logging field allowlist prevents PII leakage (`logging_config.py:36`), (2) Secret redaction in logs (`logging_config.py:80`), (3) YAML safe loading prevents code execution (`classification/loader.py:48`), (4) Path traversal protection for secret files (`soc/sink_config.py:205`), (5) Fail-secure error handling (`exceptions.py:222`), (6) API key minimum length validation (`config/__init__.py:184`), (7) Non-root Docker user (`Dockerfile:69`). | Maintain these practices. Consider adding automated security linting (e.g., Bandit, Safety) to CI/CD. |
| 9 | **INFO** | `src/anonreq/proxy/tls.py` | 36-40 | **Strong TLS configuration** — Uses secure cipher suites (TLS_AES_256_GCM_SHA384, TLS_CHACHA20_POLY1305_SHA256, ECDHE-ECDSA-AES128-GCM-SHA256). Certificate pinning detection implemented. | No action needed. Continue monitoring for deprecated cipher suites. |
| 10 | **INFO** | `src/anonreq/dependencies.py` | 67 | **Simple API key comparison** — Authentication uses direct string comparison (`token != settings.API_KEY`). While functional, this is susceptible to timing attacks. | Consider using `hmac.compare_digest()` for constant-time comparison to prevent timing-based side-channel attacks. |

---

## Dependency Check

- **pip-audit**: Not installed in the environment. Install and run `pip-audit` to check for known vulnerabilities in dependencies.
- **Outdated packages**: Unable to check (pip not in PATH). Run `pip list --outdated` to identify packages needing updates.

**Recommended dependency security measures:**
1. Install `pip-audit` and run it regularly
2. Use `pip-compile` or `uv lock` for reproducible builds
3. Add `safety` or `trivy` to CI/CD pipeline
4. Monitor Dependabot/Renovate alerts

---

## Network Security

- **TLS verification**: No instances of `verify=False` found in httpx calls (good)
- **Internal service communication**: Uses HTTP for internal services (Presidio, Valkey) on isolated Docker network (acceptable for internal traffic)
- **Port exposure**: Only port 8080 exposed to host (good)

---

## Input Validation

- **FastAPI endpoints**: Use Pydantic models for request validation
- **SQL queries**: Parameterized queries used in `ediscovery/export.py` (good)
- **YAML loading**: Uses `yaml.safe_load()` throughout (good)
- **No eval/exec**: No instances of `eval()` or `exec()` found in application code

---

## Recommendations Summary

1. **Immediate**: Rotate the exposed OpenAI API keys in `.env`
2. **Immediate**: Remove hardcoded credentials from `docker-compose.yml`
3. **Short-term**: Pin Docker image versions
4. **Short-term**: Add `follow_redirects=False` to httpx clients
5. **Medium-term**: Implement automated security scanning in CI/CD
6. **Medium-term**: Add `hmac.compare_digest()` for API key comparison
7. **Long-term**: Implement comprehensive dependency vulnerability scanning

---

*Report generated by security scan on 2026-07-17*
