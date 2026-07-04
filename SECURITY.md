# Security Policy

## Supported Versions

Only the latest active major version is supported for security patches.

| Version | Supported |
|---------|-----------|
| >= 1.0.0 | ✅ |
| < 1.0.0  | ❌ |

## Reporting a Vulnerability

We take the security of the AnonReq gateway seriously. If you find a vulnerability (such as a bypass of the PII sanitization pipeline or a leakage of sensitive logs), please follow our coordinated disclosure policy.

- **Email**: Send vulnerability details to [security@anonreq.io](mailto:security@anonreq.io).
- **PGP Key**: Encrypt your report using the PGP key available at `https://anonreq.io/security.key`.
- **Response SLA**: We will acknowledge and triage your report within **5 business days**.
- **Coordinated Disclosure Policy**: We ask that you give us **90 days** to patch and verify the vulnerability before public disclosure.

## Scope

### In Scope
- Plaintext PII leakage to external API endpoints.
- Vulnerabilities in the core FastAPI routing, Presidio pipeline matching, or Valkey caching layers.
- Integrity bypasses of the SHA-384 audit trail hash chain.

### Out of Scope
- Upstream vulnerabilities in Microsoft Presidio Analyzer or base Python runtime library packages (these should be reported to their respective maintainers).
- Theoretical vulnerabilities that require access to the physical host machine or direct administrative database access.
- Denial of Service (DoS) attacks that can be mitigated by network firewalls.
