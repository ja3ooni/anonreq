> translated from en/deployment.md

# Déploiement

## Considérations pour la production

### Allocation des ressources

Assurez-vous que votre hôte dispose des ressources minimales requises pour les trois conteneurs. Pour les déploiements en production, ajoutez une marge de sécurité de 50 % au-dessus de l'utilisation maximale observée.

### Configuration des journaux

Les journaux sont écrits sur la sortie standard au format JSON structuré. Configurez l'agrégation des journaux via votre outil préféré (pilote de journalisation Docker, syslog ou un expéditeur de journaux comme Fluentd ou Vector).

### Sécurité du réseau

La passerelle écoute sur le port 8000. L'analyseur Presidio et Valkey sont isolés sur un réseau Docker interne et ne sont pas directement accessibles de l'extérieur.

### Terminaison TLS

Terminez TLS au niveau de votre proxy inverse (nginx, Caddy ou un équilibreur de charge cloud) et transmettez les requêtes à la passerelle via HTTP sur le réseau interne.

## Variables d'environnement

| Variable | Type | Par défaut | Requis | Description |
|----------|------|------------|--------|-------------|
| `ANONREQ_API_KEY` | string | — | Oui | Jeton porteur pour l'authentification API (≥ 32 caractères) |
| `ANONREQ_LOG_LEVEL` | string | `INFO` | Non | Niveau de journalisation : DEBUG, INFO, WARNING, ERROR |
| `ANONREQ_CACHE_URL` | string | `valkey://localhost:6379` | Non | URL du serveur Valkey |
| `ANONREQ_CACHE_PASSWORD` | string | — | Non | Mot de passe requis pour Valkey |
| `ANONREQ_CACHE_TTL` | int | `600` | Non | Durée de vie de session (TTL) en secondes (60–3600) |
| `ANONREQ_OPENAI_API_KEY` | string | — | Conditionnel | Clé API OpenAI |
| `ANONREQ_ANTHROPIC_API_KEY` | string | — | Conditionnel | Clé API Anthropic |
| `ANONREQ_GEMINI_API_KEY` | string | — | Conditionnel | Clé API Google Gemini |
| `ANONREQ_OLLAMA_BASE_URL` | string | — | Non | URL du serveur Ollama |
| `ANONREQ_LOCALE` | string | `en-US` | Non | Paramètre linguistique par défaut pour la détection |
| `ANONREQ_COMPLIANCE_PRESET` | string | — | Non | Nom du preset de conformité |
| `ANONREQ_CONFIDENCE_THRESHOLD` | float | `0.7` | Non | Seuil de confiance de détection (0.0–1.0) |
| `PRESIDIO_ANALYZER_URL` | string | `http://presidio-analyzer:5001` | Non | URL de l'analyseur Presidio |

## Configuration de production Docker Compose

Personnalisez le fichier `docker-compose.yml` par défaut à l'aide d'un fichier `docker-compose.override.yml` :

```yaml
services:
  anonreq:
    deploy:
      resources:
        limits:
          cpus: "4"
          memory: "4G"
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"
```

### Configuration du test de santé

Chaque service dispose d'un test de santé intégré. Surveillez les trois services via l'endpoint `/health` de la passerelle. Configurez une surveillance externe pour générer des alertes en cas de réponses non-200.

### Politiques de redémarrage

Tous les services utilisent la directive `restart: unless-stopped`. Pour les déploiements sans interruption, exécutez plusieurs répliques de la passerelle derrière un équilibreur de charge.

## Journalisation

Des journaux JSON structurés sont émis sur stdout. Champs clés : `timestamp`, `level`, `event`, `session_id`, `latency_ms`, `entity_count`, `provider`. Utilisez votre outil d'agrégation de journaux préféré pour les consommer.

## Mise à niveau

1. Récupérer la dernière image : `docker compose pull anonreq`
2. Recréer les services : `docker compose up -d --force-recreate anonreq`
3. Vérifier la santé de l'application : `curl http://localhost:8000/health`

## Sécurité

- La passerelle est sécurisée par défaut en cas de défaillance (fail-secure) : toute erreur de détection ou de cache renvoie HTTP 5xx et ne transmet jamais de données non anonymisées en amont.
- La rotation des clés API est prise en charge par redémarrage : mettez à jour `ANONREQ_API_KEY` dans le fichier `.env` et exécutez `docker compose restart anonreq`.
- Toutes les données du cache sont éphémères — aucune donnée n'est écrite sur le disque.

---
*Ce document est une traduction de l'original en anglais. En cas de divergence, la version anglaise prévaut.*
