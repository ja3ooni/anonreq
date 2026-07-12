> translated from en/operations.md

# Guía de operaciones de AnonReq

Esta guía proporciona manuales de operación, estructuras de configuración, especificaciones de monitoreo y pasos de resolución de problemas para los operadores del sistema que gestionan la pasarela AnonReq.

## Gestión de la configuración

Las configuraciones de la pasarela se gestionan a través de archivos YAML cargados al inicio del contenedor. Las configuraciones principales son:

- **Motor de políticas (`config/policy.yaml`):** Define las reglas del inquilino, los límites de velocidad, los presupuestos de gastos y los límites geográficos.
- **Configuración de SLO (`config/slo.yaml`):** Declara los objetivos operativos para la tasa de éxito, las latencias, los estados seguros y los registros de auditoría.
- **Trust Center (`config/trust_center.yaml`):** Controla el acceso a los portales públicos de cumplimiento.

Las configuraciones se vuelven a cargar automáticamente al recibir una señal `SIGHUP`.

### Ejemplo de configuración de políticas

```yaml
version: "1.0"
rules:
  - rule_id: "block_restricted_pii"
    name: "Block Restricted Data"
    action: "BLOCK"
    priority: 100
    enabled: true
    conditions:
      classification_level: "Restricted"
rate_limits:
  enabled: true
  rpm: 1000
```

## Monitoreo de Objetivos de Nivel de Servicio (SLOs)

AnonReq rastrea 4 SLO principales para garantizar la seguridad y el rendimiento del sistema:

1. **Tasa de éxito:** Al menos el 99,9% de las solicitudes de la pasarela deben tener éxito.
2. **Latencia P95:** El tiempo de procesamiento debe permanecer ≤100ms.
3. **Tasa de fallos seguros (Fail-Secure):** ≤0.1% de las transacciones deben activar bloqueos de seguridad.
4. **Tasa de escritura de auditoría:** ≥99.99% de las escrituras de registros de auditoría deben completarse con éxito.

### Infraestructura de monitoreo

- **Panel de Prometheus:** Recopila métricas desde `/metrics` en el puerto `8080`.
- **Panel de Grafana:** Visualiza el cumplimiento de los SLO y los presupuestos de errores.

## Operaciones de CLI administrativas

Los operadores del sistema utilizan solicitudes curl para consultar el estado, recopilar métricas y realizar actualizaciones.

### 1. Consultar políticas activas
```bash
curl -X GET http://localhost:8080/v1/admin/policies   -H "Authorization: Bearer <ADMIN_API_KEY>"   -H "X-AnonReq-Role: operator"   -H "X-AnonReq-Tenant-ID: default"
```

### 2. Consultar el cumplimiento de los SLO en tiempo real
```bash
curl -H "Authorization: Bearer <ADMIN_API_KEY>"      -H "X-AnonReq-Role: administrator"      http://localhost:8080/v1/governance/status
```

### 3. Verificar la integridad de la cadena de auditoría criptográfica
```bash
curl -X POST http://localhost:8080/v1/governance/audit/verify   -H "Authorization: Bearer <ADMIN_API_KEY>"   -H "X-AnonReq-Role: administrator"
```

## Resolución de problemas y recuperación

Cuando se infringe un SLO, la pasarela emite alertas. Los operadores deben comprobar los siguientes subsistemas:

- **Caída de la tasa de éxito:** Verifique la conectividad con los proveedores (OpenAI/Gemini) e inspeccione el consumo de recursos de Valkey.
- **Picos de latencia:** Compruebe el uso de CPU/memoria de los contenedores de la pasarela y escale las instancias según sea necesario.
- **Aumento de la tasa de fallos seguros:** Inspeccione los registros para verificar si el contenedor Presidio Analyzer responde o si los patrones regex fallan al compilar.
- **Fallos en la escritura de auditoría:** Inspeccione la conectividad de Valkey o la capacidad del pool de la base de datos SQL. Compruebe el espacio en disco.

---
*Este documento es una traducción del original en inglés. En caso de discrepancia, prevalecerá la versión en inglés.*
