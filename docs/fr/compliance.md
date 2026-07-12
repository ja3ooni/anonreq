> translated from en/compliance.md

# Presets de conformité

## Aperçu

AnonReq propose des presets de conformité qui imposent la détection de certaines entités pour des cadres réglementaires spécifiques. Chaque preset active un ensemble d'analyseurs requis par la réglementation correspondante.

| Preset | Réglementation | Région | Entités obligatoires |
|--------|----------------|--------|----------------------|
| `gdpr` | Règlement général sur la protection des données | UE | E-mail, téléphone, nom, adresse, IP, ID national |
| `lgpd` | Lei Geral de Proteção de Dados | Brésil | CPF, CNPJ, e-mail, téléphone, nom, adresse |
| `pdpa` | Personal Data Protection Act | Thaïlande | E-mail, téléphone, nom, adresse, ID national |
| `popia` | Protection of Personal Information Act | Afrique du Sud | E-mail, téléphone, nom, adresse, numéro d'identité |
| `privacy-act` | Privacy Act 1988 | Australie | E-mail, téléphone, nom, adresse, numéro Medicare, TFN |
| `pipeda` | Loi sur la protection des renseignements personnels et les documents électroniques | Canada | E-mail, téléphone, nom, adresse, NAS |

## Configuration par preset

Chaque preset définit :

- **Types d'entités obligatoires** : règles de détection qui ne peuvent pas être désactivées lorsque le preset est actif.
- **Seuil de confiance** : score de confiance minimal pour la détection basée sur le NER (par défaut par preset).
- **Locale** : paramètre linguistique associé pour les analyseurs spécifiques à une langue.

## Configuration des presets

Configurez le preset via l'en-tête `X-AnonReq-Compliance-Preset` lors des requêtes :

```bash
curl -H "X-AnonReq-Compliance-Preset: gdpr"   -H "Authorization: Bearer $ANONREQ_API_KEY"   ...
```

Interroger les presets disponibles et leurs configurations :

```bash
curl http://localhost:8000/v1/compliance/presets
```

## Presets multiples

Lorsque plusieurs presets sont spécifiés (séparés par des virgules), la configuration finale est l'union de tous les types d'entités obligatoires avec le seuil de confiance le plus élevé parmi les presets sélectionnés.

## Validation au démarrage

Si un preset de conformité est configuré au démarrage, la passerelle vérifie que tous les types d'entités requis par le preset disposent d'analyseurs actifs. Toute configuration désactivant un type obligatoire est rejetée au démarrage.

---
*Ce document est une traduction de l'original en anglais. En cas de divergence, la version anglaise prévaut.*
