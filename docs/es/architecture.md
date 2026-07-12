> translated from en/architecture.md

# Arquitectura de la pasarela AnonReq

Este documento proporciona un resumen en prosa de la arquitectura de la pasarela AnonReq. Detalla la topología de los componentes, el ciclo de vida de las solicitudes y los invariantes de seguridad principales.

## Descripción general del sistema

AnonReq es una pasarela de seguridad y anonymisation de IA auto-hospedada diseñada para situarse entre las aplicaciones de la empresa y los proveedores de LLM (Large Language Model) externos o locales. Al actuar como un proxy de interceptación, garantiza que los datos sensibles (como PII, PHI, PCI o secretos comerciales) se clasifiquen, tokenicen y saneen antes de cruzar el límite de confianza de la red de la empresa.

```
┌─────────────────┐       ┌─────────────────┐       ┌───────────────────┐
│                 │       │                 │       │                   │
│   Aplicación    │──────>│ Pasarela        │──────>│ Proveedores LLM   │
│   de la Empresa │<──────│ AnonReq         │<──────│ (OpenAI, Gemini)  │
│                 │       │ (Auto-hospedada)│       │                   │
└─────────────────┘       └─────────────────┘       └───────────────────┘
```

## Ciclo de vida de la solicitud

Cada solicitud enviada a un proveedor externo a través de AnonReq fluye a través de un canal de procesamiento estructurado:

1. **Recepción y distribución de contenido:** La solicitud ingresa a la pasarela. El despachador de tipos de contenido inspecciona las cabeceras de la solicitud y dirige el flujo al analizador adecuado (Text, JSON o Multipart).
2. **Clasificación:** El motor de clasificación comprueba la solicitud con los niveles de seguridad configurados. Si una carga útil contiene datos restringidos no permitidos, el motor bloquea la solicitud antes o determina si necesita enrutamiento local, anonymisation o paso directo.
3. **Detección:** El motor de detección combina reconocedores regex/checksum, la integración de Presidio y algoritmos de optimización de contexto para localizar entidades sensibles (por ejemplo, correos electrónicos, números de teléfono, tarjetas de crédito).
4. **Tokenización:** Los valores sensibles detectados se extraen y se reemplazan con tokens anónimos (por ejemplo, `[EMAIL_0]`, `[PERSON_1]`). Los mapeos únicos y aleatorios se almacenan en el gestor de caché de Valkey/Redis bajo un ciclo de vida limitado a la sesión.
5. **Adaptador de proveedor:** El adaptador traduce la solicitud saneada al formato de la API del LLM de destino (por ejemplo, convirtiendo de OpenAI a Anthropic/Gemini) y la reenvía.
6. **Respuesta del LLM:** El LLM externo devuelve su respuesta con las referencias tokenizadas.
7. **Restauración:** El motor de restauración recupera las asignaciones desde el gestor de caché y reemplaza los tokens con sus valores originales en la respuesta (compatible con la transmisión SSE).
8. **Salida:** La respuesta restaurada se devuelve a la aplicación cliente.

## Componentes principales

- **Proxy/Pasarela:** Aplicación FastAPI que ejecuta un bucle de red ASGI.
- **Motor de clasificación:** PDP (Policy Decision Point) y PEP (Policy Enforcement Point) que evalúan las políticas de gobernanza y riesgo.
- **Motor de detección:** Escáner de entidades multi-locale con reconocedores regex y Microsoft Presidio.
- **Motores de tokenización y restauración:** Código responsable de la sustitución y el reemplazo de los tokens.
- **Gestor de caché:** Instancia de Valkey/Redis en memoria que conserva los mapas de sesión bajo un contrato de TTL estricto.
- **Adaptadores de proveedores:** Capa de compatibilidad que traduce las llamadas de la API en tiempo real.

## Invariantes de seguridad principales

- **Invariante de cero exposición:** La PII bruta nunca debe cruzar el límite de la red de la empresa hacia proveedores externos bajo ninguna circunstancia.
- **Comportamiento seguro en caso de fallo (fail-secure):** Cualquier excepción de ejecución, tiempo de espera, falta de caché o ambigüedad de clasificación debe bloquear inmediatamente el tráfico saliente y devolver HTTP 503 o 403.
- **Telemetría sin PII:** Los registros de auditoría y las métricas de Prometheus contienen solo metadatos. No se registran datos brutos ni valores de tokens.
- **Almacenamiento efímero:** Los mapeos se almacenan solo en la memoria caché con TTL configurados estrictamente, lo que garantiza su eliminación inmediata posterior a la transacción.

---
*Este documento es una traducción del original en inglés. En caso de discrepancia, prevalecerá la versión en inglés.*
