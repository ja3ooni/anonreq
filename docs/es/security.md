> translated from en/security.md

# Política de seguridad de AnonReq

Este documento describe la postura de seguridad, las garantías de manejo de datos y los procedimientos de respuesta a incidentes para la pasarela AnonReq.

## Postura de seguridad

AnonReq se basa en una arquitectura Zero-Trust. Asumimos que todos los endpoints de modelos externos y las redes públicas no son seguros, y aplicamos límites de seguridad estrictos:

- **Privilegio mínimo:** Todas las rutas administrativas y los cambios de configuración requieren una autorización validada mediante claves API de alta entropía.
- **Valores seguros por defecto (Fail-Secure):** Todos los parámetros de configuración tienen por defecto el estado más restrictivo (por ejemplo, Trust Center deshabilitado, presets de cumplimiento requeridos, acciones de bloqueo por defecto).
- **Aislamiento:** Los datos de los inquilinos (tenants), los almacenes de políticas y las cachés de sesión están estrictamente aislados en la memoria de Valkey mediante espacios de nombres prefijados.

## Garantías de anonymisation y manejo de datos

AnonReq garantiza que la información confidencial en texto plano nunca se exponga a redes externas:

1. **Protección de datos salientes:** La pasarela intercepta todas las solicitudes de texto, objetos JSON y formularios multipart. Las coincidencias en texto plano se tokenizan con variables que preservan el formato (por ejemplo, `[EMAIL_N]`) antes del tránsito por la red.
2. **Modelo de memoria efímera:** Los mapeos de tokens se almacenan exclusivamente en la caché de Valkey/Redis. Están sujetos a políticas estrictas de tiempo de vida (TTL) y se eliminan inmediatamente después de que se entrega la respuesta o expira el tiempo de espera.
3. **Sin PII en registros o telemetría:** Los registros de auditoría y las métricas de Prometheus contienen solo metadatos. Los datos brutos y los valores de los tokens nunca se registran en el almacenamiento persistente ni en stdout.

## Protocolo de respuesta a incidentes

AnonReq mantiene un flujo de trabajo activo de respuesta a incidentes para anomalías operativas o de sanitización. Los incidentes se clasifican en tres niveles de gravedad:

### Niveles de gravedad

- **Gravedad 1 (Crítica):** Fuga de PII en texto plano o violación de datos; fallo en la verificación de la firma del ancla criptográfica en la cadena de auditoría. Requiere contención en un plazo de 1 hora.
- **Gravedad 2 (Mayor):** Interrupción del servicio o degradación completa del canal de saneamiento. Requiere remediación en un plazo de 4 horas.
- **Gravedad 3 (Menor):** Advertencias operativas no críticas o degradación menor del rendimiento (por ejemplo, umbral de latencia superado). Requiere investigación en un plazo de 24 horas.

### Flujo de respuesta

1. **Detección:** Las alertas se generan a través de las métricas de Prometheus o la validación manual de la integridad de la cadena de auditoría.
2. **Triaje:** El SRE o el ingeniero de seguridad de guardia evalúa la alerta y asigna la gravedad.
3. **Contención:** Para incidentes críticos, la pasarela se puede suspender inmediatamente (suspensión de emergencia) o se pueden revocar las claves de los inquilinos.
4. **Remediación:** Los desarrolladores corrigen la causa raíz, compilan un parche y actualizan el contenedor.
5. **Recuperación:** Se restablece el tráfico normal y se verifica la integridad de la cadena de auditoría.

---
*Este documento es una traducción del original en inglés. En caso de discrepancia, prevalecerá la versión en inglés.*
