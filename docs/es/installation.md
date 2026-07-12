> translated from en/installation.md

# Instalación

## Requisitos previos

- Python 3.12+
- Docker Engine 24+ con Docker Compose v2+
- Mínimo 4 GB de RAM (8 GB recomendados)

## Clonar el repositorio

```bash
git clone https://github.com/anonreq/anonreq.git
cd anonreq
```

## Configuración del entorno

Copie el archivo de entorno de ejemplo y configure las variables requeridas:

```bash
cp .env.example .env
```

| Variable | Requerido | Por defecto | Descripción |
|----------|-----------|-------------|-------------|
| `ANONREQ_API_KEY` | Sí | — | Token estático para la autenticación de la API (≥ 32 caracteres) |
| `ANONREQ_LOG_LEVEL` | No | `INFO` | Nivel de registro |
| `ANONREQ_CACHE_TTL` | No | `600` | TTL del caché de sesión en segundos |
| `ANONREQ_PRESIDIO_URL` | No | `http://presidio-analyzer:5001` | URL de Presidio Analyzer |
| `ANONREQ_VALKEY_URL` | No | `valkey://localhost:6379` | Cadena de conexión de Valkey |

Debe configurarse al menos una clave de API de proveedor (`ANONREQ_OPENAI_API_KEY`, `ANONREQ_ANTHROPIC_API_KEY` o `ANONREQ_GEMINI_API_KEY`).

## Configuración de Docker Compose

```bash
docker compose up -d --wait
```

Esto inicia los tres servicios: `anonreq` (pasarela), `presidio-analyzer` (detección de PII) y `valkey` (caché efímero).

## Verificar instalación

```bash
curl http://localhost:8000/health
```

Respuesta esperada: HTTP 200 con `{"status":"pass","checks":{"presidio":"pass","valkey":"pass"}}`.

## Resolución de problemas

| Problema | Causa probable | Solución |
|----------|----------------|----------|
| El control de salud devuelve 503 | El modelo Presidio aún se está cargando | Espere 60 segundos para descargar el modelo e inténtelo de nuevo |
| `docker compose up` falla | El puerto 8000 está en uso | Detenga otros servicios o cambie el mapeo de puertos |
| `curl: connection refused` | La pasarela no está lista | Ejecute `docker compose ps` para comprobar el estado |

---
*Este documento es una traducción del original en inglés. En caso de discrepancia, prevalecerá la versión en inglés.*
