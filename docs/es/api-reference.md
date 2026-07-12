> translated from en/api-reference.md

# Referencia de la API

La especificación OpenAPI completa está disponible en `docs/openapi.json` (generada automáticamente a partir de la aplicación FastAPI). Esta página proporciona un resumen de los endpoints disponibles.

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/v1/chat/completions` | Enviar una solicitud de chat completion (compatible con OpenAI) |
| GET | `/health` | Control de salud agregado para todas las dependencias |
| GET | `/v1/models` | Listar los alias de modelos disponibles |
| GET | `/v1/compliance/presets` | Listar los presets de cumplimiento disponibles |
| GET | `/v1/config/rules` | Listar las reglas de detección personalizadas activas |
| GET | `/metrics` | Endpoint de métricas de Prometheus |

### POST /v1/chat/completions

Acepta un cuerpo de solicitud de chat completion compatible con OpenAI. Admite tanto el modo de transmisión (`stream: true`) como el de no transmisión. Consulte la especificación OpenAPI para obtener el esquema completo.

### GET /health

Devuelve el estado de salud agregado de la pasarela y sus dependencias (Presidio Analyzer, Valkey). Respuesta:

```json
{"status":"pass","checks":{"presidio":"pass","valkey":"pass"}}
```

### GET /v1/models

Devuelve la lista de alias de modelos configurados y sus proveedores objetivo.

### GET /v1/compliance/presets

Devuelve los presets de cumplimiento disponibles con sus tipos de entidades obligatorios y umbrales de confianza.

### GET /v1/config/rules

Devuelve las reglas de detección personalizadas activas (reconocedores y listas de exclusión).

### GET /metrics

Devuelve las métricas en formato Prometheus, incluidos los recuentos de solicitudes, la latencia de detección, los recuentos de entidades y los contadores de eventos de seguridad (fail-secure).

## Autenticación

Todos los endpoints de la API (excepto `/health` y `/metrics`) requieren un token Bearer en la cabecera `Authorization`:

```bash
Authorization: Bearer <su-clave-api-anonreq>
```

La clave API se configura mediante la variable de entorno `ANONREQ_API_KEY`.

---
*Este documento es una traducción del original en inglés. En caso de discrepancia, prevalecerá la versión en inglés.*
