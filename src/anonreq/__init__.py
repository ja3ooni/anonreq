"""AnonReq — AI Security Gateway.

Self-hosted anonymization gateway that intercepts outbound LLM API calls,
detects and replaces sensitive data (PII, PHI, financial identifiers) with
context-preserving placeholder tokens, forwards sanitized requests to
supported external LLM providers, and restores original values in responses.
"""
