> translated from en/installation.md

# Installatie

## Vereisten

- Python 3.12+
- Docker Engine 24+ met Docker Compose v2+
- Minimaal 4 GB RAM (8 GB aanbevolen)

## Clone de repository

```bash
git clone https://github.com/anonreq/anonreq.git
cd anonreq
```

## Omgevingsconfiguratie

Kopieer het voorbeeld-omgevingsbestand en configureer de vereiste variabelen:

```bash
cp .env.example .env
```

| Variabele | Vereist | Standaard | Beschrijving |
|----------|----------|---------|-------------|
| `ANONREQ_API_KEY` | Ja | — | Statische bearer token voor API-authenticatie (≥ 32 tekens) |
| `ANONREQ_LOG_LEVEL` | Nee | `INFO` | Logniveau |
| `ANONREQ_CACHE_TTL` | Nee | `600` | TTL van de sessiecache in seconden |
| `ANONREQ_PRESIDIO_URL` | Nee | `http://presidio-analyzer:5001` | URL van de Presidio Analyzer |
| `ANONREQ_VALKEY_URL` | Nee | `valkey://localhost:6379` | Valkey-verbindingsreeks |

Er moet ten minste één API-sleutel van een provider (`ANONREQ_OPENAI_API_KEY`, `ANONREQ_ANTHROPIC_API_KEY` of `ANONREQ_GEMINI_API_KEY`) worden ingesteld.

## Docker Compose Installatie

```bash
docker compose up -d --wait
```

Hiermee worden alle drie de services gestart: `anonreq` (gateway), `presidio-analyzer` (PII-detectie) en `valkey` (tijdelijke cache).

## Installatie controleren

```bash
curl http://localhost:8000/health
```

Verwacht antwoord: HTTP 200 met `{"status":"pass","checks":{"presidio":"pass","valkey":"pass"}}`.

## Probleemoplossing

| Probleem | Waarschijnlijke oorzaak | Oplossing |
|----------|-------------------------|-----------|
| Gezondheidscontrole retourneert 503 | Presidio-model laadt nog | Wacht 60 seconden tot het model is gedownload en probeer het opnieuw |
| `docker compose up` mislukt | Poort 8000 is in gebruik | Stop andere services of wijzig de poorttoewijzing |
| `curl: connection refused` | Gateway is niet gereed | Voer `docker compose ps` uit om de status te controleren |

---
*Dit document is een vertaling of bewerking van het Engelse origineel. In geval de vertaling afwijkt, is het Engelse origineel leidend.*
