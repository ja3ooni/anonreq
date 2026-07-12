> translated from en/compliance.md

# Presets de cumplimiento

## Descripción general

AnonReq proporciona presets de cumplimiento que imponen la detección de entidades obligatorias para marcos regulatorios específicos. Cada preset activa un conjunto de reconocedores requeridos por la regulación correspondiente.

| Preset | Regulación | Región | Entidades obligatorias |
|--------|------------|--------|------------------------|
| `gdpr` | Reglamento General de Protección de Datos | UE | Correo, teléfono, nombre, dirección, IP, ID nacional |
| `lgpd` | Lei Geral de Proteção de Dados | Brasil | CPF, CNPJ, correo, teléfono, nombre, dirección |
| `pdpa` | Personal Data Protection Act | Tailandia | Correo, teléfono, nombre, dirección, ID nacional |
| `popia` | Protection of Personal Information Act | Sudáfrica | Correo, teléfono, nombre, dirección, número de ID |
| `privacy-act` | Privacy Act 1988 | Australia | Correo, teléfono, nombre, dirección, Medicare, TFN |
| `pipeda` | Personal Information Protection and Electronic Documents Act | Canadá | Correo, teléfono, nombre, dirección, SIN |

## Configuración por preset

Cada preset define:

- **Tipos de entidades obligatorios**: reglas de detección que no se pueden deshabilitar mientras el preset está activo
- **Umbral de confianza**: puntuación de confianza mínima para la detección basada en NER (por defecto por preset)
- **Configuración regional (Locale)**: configuración regional asociada para reconocedores específicos de lenguaje

## Configuración de presets

Establezca el preset mediante la cabecera `X-AnonReq-Compliance-Preset` en las solicitudes:

```bash
curl -H "X-AnonReq-Compliance-Preset: gdpr"   -H "Authorization: Bearer $ANONREQ_API_KEY"   ...
```

Consulte los presets disponibles y sus configuraciones:

```bash
curl http://localhost:8000/v1/compliance/presets
```

## Múltiples presets

Cuando se especifican múltiples presets (separados por comas), la configuración efectiva es una unión de todos los tipos de entidades obligatorios con el umbral de confianza más alto entre los presets seleccionados.

## Validación al inicio

Si se configura un preset de cumplimiento al inicio, la pasarela valida que todos los tipos de entidades impuestos por el preset tengan reconocedores activos. La configuración que deshabilita un tipo obligatorio se rechaza al inicio.

---
*Este documento es una traducción del original en inglés. En caso de discrepancia, prevalecerá la versión en inglés.*
