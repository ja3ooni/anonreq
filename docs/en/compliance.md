# Compliance Presets

## Overview

AnonReq provides compliance presets that enforce mandated entity detection for specific regulatory frameworks. Each preset activates a bundle of recognizers required by the corresponding regulation.

| Preset | Regulation | Region | Mandated Entities |
|--------|------------|--------|-------------------|
| `gdpr` | General Data Protection Regulation | EU | Email, phone, name, address, IP, national ID |
| `lgpd` | Lei Geral de Proteção de Dados | Brazil | CPF, CNPJ, email, phone, name, address |
| `pdpa` | Personal Data Protection Act | Thailand | Email, phone, name, address, national ID |
| `popia` | Protection of Personal Information Act | South Africa | Email, phone, name, address, ID number |
| `privacy-act` | Privacy Act 1988 | Australia | Email, phone, name, address, Medicare, TFN |
| `pipeda` | Personal Information Protection and Electronic Documents Act | Canada | Email, phone, name, address, SIN |

## Per-Preset Configuration

Each preset defines:

- **Mandatory entity types**: detection rules that cannot be disabled while the preset is active
- **Confidence threshold**: minimum confidence score for NER-based detection (default per preset)
- **Locale**: associated locale for language-specific recognizers

## Configuring Presets

Set the preset via the `X-AnonReq-Compliance-Preset` header on requests:

```bash
curl -H "X-AnonReq-Compliance-Preset: gdpr" \
  -H "Authorization: Bearer $ANONREQ_API_KEY" \
  ...
```

Query available presets and their configurations:

```bash
curl http://localhost:8000/v1/compliance/presets
```

## Multiple Presets

When multiple presets are specified (comma-separated), the effective configuration is a union of all mandated entity types with the highest confidence threshold among the selected presets.

## Startup Validation

If a compliance preset is configured at startup, the gateway validates that all preset-mandated entity types have active recognizers. Configuration that disables a mandated type is rejected at startup.
