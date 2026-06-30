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

# Install pinned production dependencies
RUN pip install --no-cache-dir -r requirements.txt

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

# Healthcheck — ensures the gateway is serving /health before dependants connect
# start-period gives the application time to initialise
HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=5s \
    CMD curl -f http://localhost:8080/health || exit 1

# --no-server-header per RESEARCH Pitfall 2 (prevents Uvicorn version leak)
CMD ["uvicorn", "anonreq.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-server-header"]
