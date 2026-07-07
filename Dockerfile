# =============================================================================
# AnonReq — Multi-stage Dockerfile
# =============================================================================
# Builder stage: install production dependencies and build the package.
# Runtime stage: minimal image with only what is needed at runtime.
#
# Base: python:3.12-slim (official, verified in RESEARCH.md)
# HEALTHCHECK: configured on port 8080
# CMD: --no-server-header prevents Uvicorn version leak (Pitfall 2)
# =============================================================================

# ---------------------------------------------------------------------------
# STAGE 1 — Builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system build dependencies (setuptools, wheel)
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        gcc \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest first for layer caching
COPY requirements.txt .

# Install pinned production dependencies.
# openai-whisper's sdist imports pkg_resources during setup; recent isolated
# setuptools builds no longer expose it. Build without isolation after pinning a
# setuptools version that still provides pkg_resources.
RUN pip install --no-cache-dir "setuptools<81" wheel && \
    pip install --no-cache-dir --no-build-isolation -r requirements.txt

# Copy the rest of the source tree
COPY pyproject.toml .
COPY src/ src/
COPY config/ config/

# Install the package itself (editable install not needed in Docker)
RUN pip install --no-cache-dir .

# ---------------------------------------------------------------------------
# STAGE 2 — Runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ARG VERSION=unknown
LABEL org.opencontainers.image.source="https://github.com/yourorg/anonreq"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.description="AnonReq AI Security Gateway"

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages/ \
    /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy application source and configuration
COPY --from=builder /app/src/ src/
COPY --from=builder /app/config/ config/

# Create a non-root user for runtime security
RUN addgroup --system --gid 1001 anonreq && \
    adduser --system --uid 1001 --gid 1001 anonreq && \
    chown -R anonreq:anonreq /app
USER anonreq

# Service port
EXPOSE 8080

# Healthcheck — /health is authenticated, so use the configured gateway key.
# Use Python stdlib instead of curl; python:3.12-slim does not include curl.
HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=5s \
    CMD python -c "import os, urllib.request; req = urllib.request.Request('http://localhost:8080/health', headers={'Authorization': 'Bearer ' + os.environ['ANONREQ_API_KEY']}); urllib.request.urlopen(req, timeout=5).read()"

# --no-server-header per RESEARCH Pitfall 2 (prevents Uvicorn version leak)
CMD ["uvicorn", "anonreq.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-server-header"]
