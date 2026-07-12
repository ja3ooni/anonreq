> translated from en/api-reference.md

# API-referentie

De volledige OpenAPI-specificatie is beschikbaar op `docs/openapi.json` (automatisch gegenereerd vanuit de FastAPI-applicatie). Deze pagina biedt een samenvatting van de beschikbare endpoints.

## Endpoints

| Methode | Pad | Beschrijving |
|---------|------|-------------|
| POST | `/v1/chat/completions` | Stuur een chat completion verzoek (compatibel met OpenAI) |
| GET | `/health` | Verzamelde gezondheidscontrole voor alle afhankelijkheden |
| GET | `/v1/models` | Lijst van beschikbare model-aliases |
| GET | `/v1/compliance/presets` | Lijst van beschikbare compliance presets |
| GET | `/v1/config/rules` | Lijst van actieve aangepaste detectieregels |
| GET | `/metrics` | Prometheus metrics endpoint |

### POST /v1/chat/completions

Accepteert een OpenAI-compatibele chat completion request body. Ondersteunt zowel streaming (`stream: true`) als niet-streaming modi. Zie de OpenAPI-specificatie voor het volledige schema.

### GET /health

Retourneert de totale gezondheidsstatus van de gateway en zijn afhankelijkheden (Presidio Analyzer, Valkey). Antwoord:

```json
{"status":"pass","checks":{"presidio":"pass","valkey":"pass"}}
```

### GET /v1/models

Retourneert de lijst met geconfigureerde model-aliases en hun doelproviders.

### GET /v1/compliance/presets

Retourneert beschikbare compliance presets met hun verplichte entiteitstypen en betrouwbaarheidsdrempels.

### GET /v1/config/rules

Retourneert actieve aangepaste detectieregels (aangepaste regex-analyzers en uitsluitingslijsten).

### GET /metrics

Retourneert statistieken in Prometheus-indeling, inclusief aantal verzoeken, detectievertraging, aantal entiteiten en tellers voor fail-secure gebeurtenissen.

## Authenticatie

Alle API-endpoints (behalve `/health` en `/metrics`) vereisen een Bearer-token in de `Authorization`-header:

```bash
Authorization: Bearer <uw-anonreq-api-sleutel>
```

De API-sleutel is geconfigureerd via de `ANONREQ_API_KEY` omgevingsvariabele.

---
*Dit document is een vertaling of bewerking van het Engelse origineel. In geval de vertaling afwijkt, is het Engelse origineel leidend.*
