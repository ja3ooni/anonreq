> translated from en/installation.md

# Installation

## Prérequis

- Python 3.12+
- Docker Engine 24+ avec Docker Compose v2+
- Minimum 4 Go de RAM (8 Go recommandés)

## Cloner le dépôt

```bash
git clone https://github.com/anonreq/anonreq.git
cd anonreq
```

## Configuration de l'environnement

Copiez le fichier d'environnement d'exemple et configurez les variables requises :

```bash
cp .env.example .env
```

| Variable | Requis | Par défaut | Description |
|----------|--------|------------|-------------|
| `ANONREQ_API_KEY` | Oui | — | Jeton porteur statique pour l'authentification API (≥ 32 caractères) |
| `ANONREQ_LOG_LEVEL` | Non | `INFO` | Niveau de journalisation |
| `ANONREQ_CACHE_TTL` | Non | `600` | Durée de vie (TTL) du cache de session en secondes |
| `ANONREQ_PRESIDIO_URL` | Non | `http://presidio-analyzer:5001` | URL de l'analyseur Presidio |
| `ANONREQ_VALKEY_URL` | Non | `valkey://localhost:6379` | Chaîne de connexion Valkey |

Au moins une clé API de fournisseur (`ANONREQ_OPENAI_API_KEY`, `ANONREQ_ANTHROPIC_API_KEY` ou `ANONREQ_GEMINI_API_KEY`) doit être configurée.

## Configuration Docker Compose

```bash
docker compose up -d --wait
```

Cela démarre les trois services : `anonreq` (la passerelle), `presidio-analyzer` (la détection de PII) et `valkey` (le cache éphémère).

## Vérifier l'installation

```bash
curl http://localhost:8000/health
```

Réponse attendue : HTTP 200 avec `{"status":"pass","checks":{"presidio":"pass","valkey":"pass"}}`.

## Dépannage

| Problème | Cause probable | Solution |
|----------|----------------|----------|
| Le test de santé retourne 503 | Le modèle Presidio est encore en cours de chargement | Attendre 60 secondes pour le téléchargement du modèle, puis réessayer |
| `docker compose up` échoue | Le port 8000 est en cours d'utilisation | Arrêter les autres services ou modifier le mappage des ports |
| `curl: connection refused` | La passerelle n'est pas prête | Exécuter `docker compose ps` pour vérifier l'état |

---
*Ce document est une traduction de l'original en anglais. En cas de divergence, la version anglaise prévaut.*
