---
title: Security Best Practices
inclusion: always
---

# Security Best Practices

## Code Security
- **Secrets Management:** Never hardcode secrets. Use HashiCorp Vault for dynamic DB credentials and per-tenant encryption keys. For PSD2, use eIDAS-qualified certificates (QWACs/QSealCs) for mTLS and digital signatures.
- **Input Validation:** Strictly validate all inputs against OpenAPI/XSD schemas. For ISO 20022, enforce XSD validation at the ingestion boundary.
- **Database Security:** Use Row-Level Security (RLS) in PostgreSQL to enforce tenant isolation. Revoke `UPDATE`/`DELETE` on audit tables.
- **AuthN/AuthZ:** Use OAuth 2.0 + PKCE. Enforce MFA (TOTP/WebAuthn) for Compliance Officer roles.

## Multi-Tenancy & Sovereignty
- **Data Isolation:** Ensure zero data leakage between tenants via scoped JWT claims (`tenant_id`).
- **Residency:** Block any storage operation that targets a region outside the tenant's sovereignty boundary. Implement sidecar enforcers for real-time validation.
- **Encryption:** Use AES-256 with per-tenant keys for data at rest. Enforce TLS 1.3 for all data in transit.

## Operational Resilience (DORA)
- **Circuit Breakers:** All external API calls (Regulators, Sanctions Providers) must use circuit breakers.
- **Incident Reporting:** Services must emit `ICT_INCIDENT` events for any failure affecting critical functions.
- **RTO/RPO:** Maintain a 4-hour RTO and 1-hour RPO for the core Transaction Processing pipeline.
- **Automated Reporting:** Generate DORA-compliant incident reports automatically and submit to competent authorities.

## Cloud-Native Security (EU Regions)
- **IaC Security:** Enforce security policies via Infrastructure as Code (IaC) and integrate IaC scanning into CI/CD.
- **Network Segmentation:** Implement strict VPC and Kubernetes Network Policies for service isolation.
- **KMS Integration:** Leverage cloud Key Management Services (KMS) for all encryption key management.
- **Centralized Logging:** Aggregate all cloud logs into a secure, centralized logging solution for SIEM integration.

## Dependency Management
- **Scanning:** Use `pnpm audit` and `uv lock` (or `uv pip compile`) to monitor vulnerabilities.
- **Supply Chain:** Implement Trivy and Semgrep in CI/CD. Review all new dependencies for active maintenance.
- Use lock files (package-lock.json, poetry.lock)
- Remove unused dependencies

## Data Protection
- Encrypt sensitive data at rest and in transit
- Use HTTPS for all web communications
- Implement proper session management
- Use secure headers (HSTS, CSP, etc.)
- Follow OWASP guidelines

## Infrastructure Security
- Use least privilege principle for IAM
- Enable logging and monitoring
- Use network segmentation
- Implement proper backup strategies
- Regular security audits and penetration testing

## Development Practices
- Use static code analysis tools
- Implement security testing in CI/CD
- Code reviews for security issues
- Security training for developers
- Incident response procedures