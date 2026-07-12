> translated from en/deployment.md

# Despliegue

## Consideraciones de producción

### Asignación de recursos

Asegúrese de que su host cumpla con los requisitos mínimos de recursos para los tres contenedores. Para despliegues de producción, añada un 50% de margen por encima del uso pico observado.

### Configuración de registros

Los registros se escriben en la salida estándar en formato JSON estructurado. Configure la agregación de registros a través de su herramienta preferida (controlador de registro de Docker, syslog o un remitente de registros como Fluentd o Vector).

### Seguridad de red

La pasarela se conecta al puerto 8000. Presidio Analyzer y Valkey están aislados en una red interna de Docker y no son accesibles directamente desde el exterior.

### Terminación TLS

Termine TLS en su proxy inverso (nginx, Caddy o un equilibrador de carga en la nube) y reenvíe a la pasarela a través de HTTP en la red interna.

## Variables de entorno

| Variable | Tipo | Por defecto | Requerido | Descripción |
|----------|------|-------------|-----------|-------------|
| `ANONREQ_API_KEY` | string | — | Sí | Token para la autenticación de la API (≥ 32 caracteres) |
| `ANONREQ_LOG_LEVEL` | string | `INFO` | No | Nivel de registro: DEBUG, INFO, WARNING, ERROR |
| `ANONREQ_CACHE_URL` | string | `valkey://localhost:6379` | No | URL del servidor Valkey |
| `ANONREQ_CACHE_PASSWORD` | string | — | No | Contraseña de Valkey |
| `ANONREQ_CACHE_TTL` | int | `600` | No | TTL de sesión en segundos (60–3600) |
| `ANONREQ_OPENAI_API_KEY` | string | — | Condicional | Clave de API de OpenAI |
| `ANONREQ_ANTHROPIC_API_KEY` | string | — | Condicional | Clave de API de Anthropic |
| `ANONREQ_GEMINI_API_KEY` | string | — | Condicional | Clave de API de Google Gemini |
| `ANONREQ_OLLAMA_BASE_URL` | string | — | No | URL del servidor de Ollama |
| `ANONREQ_LOCALE` | string | `en-US` | No | Configuración regional por defecto para la detección |
| `ANONREQ_COMPLIANCE_PRESET` | string | — | No | Nombre del preset de cumplimiento |
| `ANONREQ_CONFIDENCE_THRESHOLD` | float | `0.7` | No | Seuil de confianza de detección (0.0–1.0) |
| `PRESIDIO_ANALYZER_URL` | string | `http://presidio-analyzer:5001` | No | URL de Presidio Analyzer |

## Configuración de producción de Docker Compose

Personalice el archivo `docker-compose.yml` predeterminado con un archivo `docker-compose.override.yml`:

```yaml
services:
  anonreq:
    deploy:
      resources:
        limits:
          cpus: "4"
          memory: "4G"
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"
```

### Configuración del control de salud

Cada servicio tiene un control de salud incorporado. Monitoree los tres a través del endpoint `/health` de la pasarela. Configure el monitoreo externo para alertar sobre respuestas que no sean 200.

### Políticas de reinicio

Todos los servicios utilizan `restart: unless-stopped`. Para despliegues sin tiempo de inactividad, ejecute múltiples réplicas de la pasarela detrás de un equilibrador de carga.

## Registro

Los registros JSON estructurados se emiten en stdout. Campos clave: `timestamp`, `level`, `event`, `session_id`, `latency_ms`, `entity_count`, `provider`. Consúmalos con su herramienta de agregación de registros preferida.

## Actualización

1. Descargue la última imagen: `docker compose pull anonreq`
2. Recree los servicios: `docker compose up -d --force-recreate anonreq`
3. Verifique el estado de salud: `curl http://localhost:8000/health`

## Seguridad

- La pasarela es segura por defecto en caso de fallo (fail-secure): cualquier error de detección o caché devuelve HTTP 5xx y nunca reenvía datos no saneados río arriba
- La rotación de claves API se admite mediante reinicio: actualice `ANONREQ_API_KEY` en `.env` y ejecute `docker compose restart anonreq`
- Todos los datos de caché son efímeros — no se escriben datos en el disco

---
*Este documento es una traducción del original en inglés. En caso de discrepancia, prevalecerá la versión en inglés.*
