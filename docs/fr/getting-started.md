> translated from en/getting-started.md

# Pour commencer avec AnonReq

## Prérequis

- Docker Engine 24+
- Docker Compose v2+
- Une clé API OpenAI, Anthropic ou Gemini

## Démarrage rapide

Exécutez les scripts suivants depuis la racine du dépôt :

```bash
# Étape 1 : Démarrer la passerelle
./examples/quickstart/01-start-gateway.sh

# Étape 2 : Envoyer une requête de test avec PII
./examples/quickstart/02-basic-anonymization.sh

# Étape 3 : Nettoyer
./examples/quickstart/03-cleanup.sh
```

Les scripts de démarrage rapide gèrent automatiquement toute la configuration, la vérification et le nettoyage. Chaque script se termine avec le code 0 en cas de succès ou 1 en cas d'échec avec des informations de diagnostic.

## Étapes suivantes

- Consultez `docs/en/installation.md` pour des instructions d'installation détaillées
- Consultez `examples/curl/`, `examples/python/`, `examples/typescript/` et `examples/go/` pour des exemples de SDK dans votre langage
- Consultez `docs/en/deployment.md` pour des conseils de déploiement en production
- Consultez `docs/en/compliance.md` pour la configuration des presets de conformité
- Consultez le fichier README du projet pour un aperçu complet

---
*Ce document est une traduction de l'original en anglais. En cas de divergence, la version anglaise prévaut.*
