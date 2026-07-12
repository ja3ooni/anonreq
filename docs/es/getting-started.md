> translated from en/getting-started.md

# Primeros pasos con AnonReq

## Requisitos previos

- Docker Engine 24+
- Docker Compose v2+
- Una clave de API de OpenAI, Anthropic o Gemini

## Inicio rápido

Ejecute los siguientes scripts desde la raíz del repositorio:

```bash
# Paso 1: Iniciar la pasarela
./examples/quickstart/01-start-gateway.sh

# Paso 2: Enviar una solicitud de prueba con PII
./examples/quickstart/02-basic-anonymization.sh

# Paso 3: Limpiar
./examples/quickstart/03-cleanup.sh
```

Los scripts de inicio rápido manejan toda la configuración, verificación y limpieza automáticamente. Cada script finaliza con el código 0 en caso de éxito o 1 en caso de fallo con salida de diagnóstico.

## Próximos pasos

- Consulte `docs/en/installation.md` para obtener instrucciones detalladas de instalación
- Consulte `examples/curl/`, `examples/python/`, `examples/typescript/` y `examples/go/` para obtener ejemplos de SDK en su lenguaje
- Consulte `docs/en/deployment.md` para obtener una guía de despliegue en producción
- Consulte `docs/en/compliance.md` para configurar los presets de cumplimiento
- Consulte el archivo README del proyecto para obtener una visión general completa

---
*Este documento es una traducción del original en inglés. En caso de discrepancia, prevalecerá la versión en inglés.*
