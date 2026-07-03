# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Current mainline | ✓ |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it via **security@anonreq.dev**. Do NOT file a public GitHub issue.

**Response SLA:**
- We acknowledge receipt within 24 hours
- We provide an initial assessment within 72 hours
- Critical vulnerabilities receive a fix or mitigation within 5 business days of confirmation

## Disclosure Policy

We follow a coordinated disclosure process:
- Reporters receive advance notice of patches
- Users are granted a 90-day grace period to apply patches before public disclosure
- Security advisories are published via GitHub Security Advisories

## Security Practices

- **Fail-Secure Architecture**: Any error returns HTTP 5xx; zero data forwarded upstream
- **No PII in Logs**: Metadata-only structured logging with field allowlist
- **Ephemeral Cache**: Valkey with persistence disabled (`save ""`)
- **Dependency Scanning**: Automated vulnerability scanning in CI
