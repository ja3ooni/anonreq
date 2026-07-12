> translated from en/deployment.md

# Productie-implementatie

## Productie-overwegingen

### Resourcedistributie

Zorg ervoor dat uw host voldoet aan de minimale resourcevereisten voor alle drie de containers. Voeg voor productie-implementaties 50% extra capaciteit toe bovenop het piekverbruik.

### Logboekconfiguratie

Logboeken worden naar stdout geschreven in gestructureerd JSON-formaat. Configureer logboekaggregatie via uw voorkeurstool (Docker logging driver, syslog, of een logshipper zoals Fluentd of Vector).

### Netwerkbeveiliging

De gateway luistert op poort 8000. Presidio Analyzer en Valkey zijn geïsoleerd op een intern Docker-netwerk en zijn niet rechtstreeks van buitenaf toegankelijk.

### TLS-terminatie

Beëindig TLS op uw reverse proxy (nginx, Caddy, of een cloud load balancer) en stuur het verkeer via HTTP door naar de gateway op het interne netwerk.

## Omgevingsvariabelen

| Variabele | Type | Standaard | Vereist | Beschrijving |
|----------|------|---------|----------|-------------|
| `ANONREQ_API_KEY` | string | — | Ja | Bearer token voor API-authenticatie (≥ 32 tekens) |
| `ANONREQ_LOG_LEVEL` | string | `INFO` | Nee | Logniveau: DEBUG, INFO, WARNING, ERROR |
| `ANONREQ_CACHE_URL` | string | `valkey://localhost:6379` | Nee | URL van de Valkey-server |
| `ANONREQ_CACHE_PASSWORD` | string | — | Nee | Valkey-wachtwoord |
| `ANONREQ_CACHE_TTL` | int | `600` | Nee | TTL van de sessie in seconden (60–3600) |
| `ANONREQ_OPENAI_API_KEY` | string | — | Conditioneel | OpenAI API-sleutel |
| `ANONREQ_ANTHROPIC_API_KEY` | string | — | Conditioneel | Anthropic API-sleutel |
| `ANONREQ_GEMINI_API_KEY` | string | — | Conditioneel | Google Gemini API-sleutel |
| `ANONREQ_OLLAMA_BASE_URL` | string | — | Nee | URL van de Ollama-server |
| `ANONREQ_LOCALE` | string | `en-US` | Nee | Standaard detectielocale |
| `ANONREQ_COMPLIANCE_PRESET` | string | — | Nee | Naam van compliance preset |
| `ANONREQ_CONFIDENCE_THRESHOLD` | float | `0.7` | Nee | Minimale betrouwbaarheidsscore voor detectie (0.0–1.0) |
| `PRESIDIO_ANALYZER_URL` | string | `http://presidio-analyzer:5001` | Nee | URL van de Presidio Analyzer |

## Docker Compose Productieconfiguratie

Pas de standaard `docker-compose.yml` aan met een `docker-compose.override.yml`-bestand:

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

### Configureren van gezondheidscontrole

Elke service heeft een ingebouwde gezondheidscontrole. Monitor ze alle drie via het `/health`-endpoint van de gateway. Configureer externe monitoring om te waarschuwen bij niet-200 antwoorden.

### Restart-beleid

Alle services gebruiken `restart: unless-stopped`. Voer voor implementaties zonder downtime meerdere gateway-replica's uit achter een load balancer.

## Logbestanden

Gestructureerde JSON-logboeken worden naar stdout gestuurd. Belangrijke velden: `timestamp`, `level`, `event`, `session_id`, `latency_ms`, `entity_count`, `provider`. Verwerk deze met uw favoriete logaggregatietool.

## Upgraden

1. Haal de nieuwste image op: `docker compose pull anonreq`
2. Recreëer de services: `docker compose up -d --force-recreate anonreq`
3. Controleer de gezondheid: `curl http://localhost:8000/health`

## Beveiliging

- De gateway is fail-secure: elke detectie- of cachefout retourneert HTTP 5xx en stuurt nooit ongezuiverde gegevens door.
- Rotatie van API-sleutels wordt ondersteund via herstart: werk `ANONREQ_API_KEY` bij in `.env` en voer `docker compose restart anonreq` uit.
- Alle cachegegevens zijn vluchtig — er worden geen gegevens naar de schijf geschreven

---
*Dit document is een vertaling of bewerking van het Engelse origineel. In geval de vertaling afwijkt, is het Engelse origineel leidend.*
