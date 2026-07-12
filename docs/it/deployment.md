> translated from en/deployment.md

# Distribuzione

## Considerazioni per la produzione

### Allocazione delle risorse

Assicurarsi che l'host soddisfi i requisiti minimi di risorse per tutti e tre i container. Per le distribuzioni in produzione, aggiungere un margine di sicurezza del 50% rispetto al picco di utilizzo osservato.

### Configurazione dei log

I log vengono scritti su stdout in formato JSON strutturato. Configurare l'aggregazione dei log tramite lo strumento preferito (driver di log Docker, syslog o un log shipper come Fluentd o Vector).

### Sicurezza di rete

Il gateway ascolta sulla porta 8000. Presidio Analyzer e Valkey sono isolati su una rete Docker interna e non sono direttamente accessibili dall'esterno.

### Terminazione TLS

Terminare TLS sul proxy inverso (nginx, Caddy o un bilanciatore di carico cloud) e inoltrare le richieste al gateway tramite HTTP sulla rete interna.

## Variabili d'ambiente

| Variabile | Tipo | Predefinito | Richiesto | Descrizione |
|-----------|------|-------------|-----------|-------------|
| `ANONREQ_API_KEY` | string | — | Sì | Bearer token per l'autenticazione API (≥ 32 caratteri) |
| `ANONREQ_LOG_LEVEL` | string | `INFO` | No | Livello di log: DEBUG, INFO, WARNING, ERROR |
| `ANONREQ_CACHE_URL` | string | `valkey://localhost:6379` | No | URL del server Valkey |
| `ANONREQ_CACHE_PASSWORD` | string | — | No | Password Valkey |
| `ANONREQ_CACHE_TTL` | int | `600` | No | TTL della sessione in secondi (60–3600) |
| `ANONREQ_OPENAI_API_KEY` | string | — | Condizionale | Chiave API OpenAI |
| `ANONREQ_ANTHROPIC_API_KEY` | string | — | Condizionale | Chiave API Anthropic |
| `ANONREQ_GEMINI_API_KEY` | string | — | Condizionale | Chiave API Google Gemini |
| `ANONREQ_OLLAMA_BASE_URL` | string | — | No | URL del server Ollama |
| `ANONREQ_LOCALE` | string | `en-US` | No | Locale predefinito per il rilevamento |
| `ANONREQ_COMPLIANCE_PRESET` | string | — | No | Nome del preset di conformità |
| `ANONREQ_CONFIDENCE_THRESHOLD` | float | `0.7` | No | Soglia di confidenza del rilevamento (0.0–1.0) |
| `PRESIDIO_ANALYZER_URL` | string | `http://presidio-analyzer:5001` | No | URL di Presidio Analyzer |

## Configurazione di produzione Docker Compose

Personalizzare il file `docker-compose.yml` predefinito con un file `docker-compose.override.yml`:

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

### Configurazione dell'Health Check

Ogni servizio dispone di un controllo di integrità integrato. Monitorare tutti e tre tramite l'endpoint `/health` del gateway. Configurare il monitoraggio esterno per avvisare in caso di risposte non-200.

### Criteri di riavvio

Tutti i servizi utilizzano `restart: unless-stopped`. Per distribuzioni senza tempi di inattività, eseguire più repliche del gateway dietro un bilanciatore di carico.

## Log

I log JSON strutturati vengono emessi su stdout. Campi chiave: `timestamp`, `level`, `event`, `session_id`, `latency_ms`, `entity_count`, `provider`. Utilizzare lo strumento di aggregazione dei log preferito per consumarli.

## Aggiornamento

1. Scaricare l'immagine più recente: `docker compose pull anonreq`
2. Ricreare i servizi: `docker compose up -d --force-recreate anonreq`
3. Verificare lo stato di integrità: `curl http://localhost:8000/health`

## Sicurezza

- Il gateway è fail-secure: qualsiasi errore di rilevamento o cache restituisce HTTP 5xx e non inoltra mai dati non sanitizzati a monte.
- La rotazione delle chiavi API è supportata tramite riavvio: aggiornare `ANONREQ_API_KEY` in `.env` e riavviare il servizio: `docker compose restart anonreq`.
- Tutti i dati della cache sono effimeri — nessun dato viene scritto su disco

---
*Questo documento è una traduzione dell'originale in inglese. In caso di discrepanza, prevale la versione inglese.*
