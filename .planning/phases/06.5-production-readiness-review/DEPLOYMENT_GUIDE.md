# Deployment Guide — AnonReq v1.0

## Prerequisites

- Docker Engine 24+
- Docker Compose v2+
- Python 3.12+ (local development only)
- Minimum 8 GB RAM available for all 3 containers
- Provider API keys: OpenAI (`sk-...`), Anthropic (`sk-ant-...`), or Gemini (`AIza...`)

## Docker Compose Deployment (Primary)

### docker-compose.yml

```yaml
version: "3.9"

services:
  presidio-analyzer:
    image: mcr.microsoft.com/presidio-analyzer:0.4
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5001/health"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 60s
    networks:
      - anonreq-net
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: "4"
          memory: "4G"
        reservations:
          cpus: "2"
          memory: "2G"

  valkey:
    image: valkey/valkey:8-alpine
    command: >
      valkey-server
      --save ""
      --appendonly no
      --protected-mode yes
      --bind 0.0.0.0
      --requirepass ${ANONREQ_CACHE_PASSWORD:-}
      --rename-command FLUSHALL ""
      --rename-command FLUSHDB ""
      --rename-command CONFIG ""
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${ANONREQ_CACHE_PASSWORD}", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    networks:
      - anonreq-net
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: "1"
          memory: "512M"

  anonreq:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - PRESIDIO_ANALYZER_URL=http://presidio-analyzer:5001
      - ANONREQ_CACHE_URL=valkey://:${ANONREQ_CACHE_PASSWORD}@valkey:6379
    depends_on:
      presidio-analyzer:
        condition: service_healthy
      valkey:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 90s
    networks:
      - anonreq-net
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: "2G"
        reservations:
          cpus: "1"
          memory: "1G"

networks:
  anonreq-net:
    driver: bridge
    internal: false  # only anonreq:8000 is externally reachable
```

### Startup

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 2. Pull latest images (update presidio + valkey)
docker compose pull

# 3. Build and start
docker compose up -d --build

# 4. Wait for healthy
docker compose ps

# 5. Verify
curl http://localhost:8000/health
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANONREQ_API_KEY` | Yes | — | Static bearer token for API authentication (≥ 32 chars) |
| `ANONREQ_LOG_LEVEL` | No | `INFO` | Logging level: DEBUG, INFO, WARNING, ERROR |
| `ANONREQ_CACHE_URL` | No | `valkey://localhost:6379` | Valkey connection string |
| `ANONREQ_CACHE_TTL` | No | `600` | Session cache TTL in seconds (60–3600) |
| `ANONREQ_CACHE_PASSWORD` | No | — | Valkey AUTH password |
| `ANONREQ_LOCALE` | No | `en-US` | Default detection locale |
| `ANONREQ_COMPLIANCE_PRESET` | No | — | GDPR, HIPAA, PCI-DSS, etc. |
| `ANONREQ_CONFIDENCE_THRESHOLD` | No | `0.7` | NER confidence threshold (0.0–1.0) |
| `ANONREQ_OPENAI_API_KEY` | Conditional* | — | OpenAI API key |
| `ANONREQ_ANTHROPIC_API_KEY` | Conditional* | — | Anthropic API key |
| `ANONREQ_GEMINI_API_KEY` | Conditional* | — | Google Gemini API key |
| `ANONREQ_OLLAMA_BASE_URL` | No | — | Ollama server URL |
| `PRESIDIO_ANALYZER_URL` | No | `http://presidio-analyzer:5001` | Presilio Analyzer URL |

*\*At least one provider API key must be set.*

## Volume Mounts

No persistent volumes are required. All state is ephemeral:

- **Valkey**: `save ""` — no RDB/AOF. Data exists only in memory for session TTL.
- **Logs**: Handled by Docker log driver (`docker logs anonreq`). Configure via `logging:` in compose.
- **Config**: Environment variables only. No config files mounted.

## Network Policies

- **Internal bridge network**: `anonreq-net` isolates presidio and valkey from external access
- **Port mapping**: Only `anonreq:8000` is mapped to the host
- **Presidio**: Port 5001 is never exposed outside `anonreq-net`
- **Valkey**: Port 6379 is never exposed outside `anonreq-net`

## Kubernetes Deployment (Secondary)

### Namespace

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: anonreq
```

### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: anonreq-config
  namespace: anonreq
data:
  ANONREQ_LOG_LEVEL: "INFO"
  ANONREQ_CACHE_TTL: "600"
  ANONREQ_LOCALE: "en-US"
  ANONREQ_CONFIDENCE_THRESHOLD: "0.7"
  PRESIDIO_ANALYZER_URL: "http://presidio-service:5001"
  ANONREQ_CACHE_URL: "valkey://valkey-service:6379"
```

### Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: anonreq-secrets
  namespace: anonreq
type: Opaque
stringData:
  ANONREQ_API_KEY: "<your-32-char-key>"
  ANONREQ_CACHE_PASSWORD: "<cache-password>"
  ANONREQ_OPENAI_API_KEY: "<openai-key>"
```

### Deployments

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: anonreq
  namespace: anonreq
spec:
  replicas: 2
  selector:
    matchLabels:
      app: anonreq
  template:
    metadata:
      labels:
        app: anonreq
    spec:
      containers:
      - name: anonreq
        image: anonreq:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: anonreq-config
        - secretRef:
            name: anonreq-secrets
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 15
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
        resources:
          requests:
            cpu: "1"
            memory: "1G"
          limits:
            cpu: "2"
            memory: "2G"
---
apiVersion: v1
kind: Service
metadata:
  name: anonreq-service
  namespace: anonreq
spec:
  selector:
    app: anonreq
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
```

### NetworkPolicy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: anonreq-internal-isolation
  namespace: anonreq
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: anonreq
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: anonreq
  - to:
    - ipBlock:
        cidr: 0.0.0.0/0
    ports:
    - port: 443
      protocol: TCP
```

**Note:** Helm chart support is deferred to a follow-up phase. The manifests above provide a minimal deployable configuration.

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Presidio health check fails | Model download timeout on first start | Increase `start_period` in healthcheck config |
| Valkey auth mismatch | `ANONREQ_CACHE_PASSWORD` mismatch between valkey and anonreq | Verify .env has matching password values |
| Port conflict on 8000 | Another service using port 8000 | Change host port mapping: `"8001:8000"` |
| Docker Desktop OOM | Insufficient RAM allocated to Docker | Increase Docker Desktop memory to 8 GB |
| `curl: (56) Recv failure` | Gateway not ready yet | Wait for health check; check `docker compose logs anonreq` |
| Presidio returns 500 on analyze | spaCy model not loaded | Check presidio logs; verify `PRESIDIO_ANALYZER_URL` |
