> translated from en/api-reference.md

# Référence de l'API

La spécification OpenAPI complète est disponible sur `docs/openapi.json` (générée automatiquement à partir de l'application FastAPI). Cette page fournit un résumé des points de terminaison (endpoints) disponibles.

## Points de terminaison (Endpoints)

| Méthode | Chemin | Description |
|---------|--------|-------------|
| POST | `/v1/chat/completions` | Envoyer une demande de chat completion (compatible OpenAI) |
| GET | `/health` | Test de santé agrégé pour toutes les dépendances |
| GET | `/v1/models` | Lister les alias de modèles disponibles |
| GET | `/v1/compliance/presets` | Lister les presets de conformité disponibles |
| GET | `/v1/config/rules` | Lister les règles de détection personnalisées actives |
| GET | `/metrics` | Point de terminaison des métriques Prometheus |

### POST /v1/chat/completions

Accepte un corps de requête de chat completion compatible OpenAI. Prend en charge les modes de diffusion en continu (`stream: true`) et standard. Voir la spécification OpenAPI pour le schéma complet.

### GET /health

Renvoie l'état de santé agrégé de la passerelle et de ses dépendances (analyseur Presidio, Valkey). Réponse :

```json
{"status":"pass","checks":{"presidio":"pass","valkey":"pass"}}
```

### GET /v1/models

Renvoie la liste des alias de modèles configurés et leurs fournisseurs cibles.

### GET /v1/compliance/presets

Renvoie les presets de conformité disponibles avec leurs types d'entités obligatoires et leurs seuils de confiance.

### GET /v1/config/rules

Renvoie les règles de détection personnalisées actives (analyseurs personnalisés et listes d'exclusion).

### GET /metrics

Renvoie les métriques au format Prometheus, y compris le nombre de requêtes, la latence de détection, le nombre d'entités et les compteurs d'événements de sécurisation (fail-secure).

## Authentification

Tous les points de terminaison de l'API (sauf `/health` et `/metrics`) nécessitent un jeton Bearer dans l'en-tête `Authorization` :

```bash
Authorization: Bearer <votre-cle-api-anonreq>
```

La clé API est configurée via la variable d'environnement `ANONREQ_API_KEY`.

---
*Ce document est une traduction de l'original en anglais. En cas de divergence, la version anglaise prévaut.*
