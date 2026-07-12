> translated from en/installation.md

# Installazione

## Prerequisiti

- Python 3.12+
- Docker Engine 24+ con Docker Compose v2+
- Minimo 4 GB di RAM (8 GB raccomandati)

## Clonare il repository

```bash
git clone https://github.com/anonreq/anonreq.git
cd anonreq
```

## Configurazione dell'ambiente

Copiare il file di ambiente di esempio e configurare le variabili richieste:

```bash
cp .env.example .env
```

| Variabile | Richiesta | Predefinita | Descrizione |
|-----------|-----------|-------------|-------------|
| `ANONREQ_API_KEY` | Sì | — | Bearer token statico per l'autenticazione API (≥ 32 caratteri) |
| `ANONREQ_LOG_LEVEL` | No | `INFO` | Livello di log |
| `ANONREQ_CACHE_TTL` | No | `600` | TTL della cache di sessione in secondi |
| `ANONREQ_PRESIDIO_URL` | No | `http://presidio-analyzer:5001` | URL di Presidio Analyzer |
| `ANONREQ_VALKEY_URL` | No | `valkey://localhost:6379` | Stringa di connessione Valkey |

Almeno una chiave API del provider (`ANONREQ_OPENAI_API_KEY`, `ANONREQ_ANTHROPIC_API_KEY` o `ANONREQ_GEMINI_API_KEY`) deve essere impostata.

## Configurazione Docker Compose

```bash
docker compose up -d --wait
```

Questo avvia tutti e tre i servizi: `anonreq` (gateway), `presidio-analyzer` (rilevamento PII) e `valkey` (cache effimera).

## Verificare l'installazione

```bash
curl http://localhost:8000/health
```

Risposta attesa: HTTP 200 con `{"status":"pass","checks":{"presidio":"pass","valkey":"pass"}}`.

## Risoluzione dei problemi

| Problema | Causa probabile | Soluzione |
|----------|-----------------|-----------|
| L'health check restituisce 503 | Il modello Presidio si sta ancora caricando | Attendere 60 secondi per il download del modello, quindi riprovare |
| `docker compose up` fallisce | Porta 8000 già in uso | Arrestare altri servizi o modificare la mappatura delle porte |
| `curl: connection refused` | Il gateway non è pronto | Eseguire `docker compose ps` per controllare lo stato |

---
*Questo documento è una traduzione dell'originale in inglese. In caso di discrepanza, prevale la versione inglese.*
