> translated from en/getting-started.md

# Aan de slag met AnonReq

## Vereisten

- Docker Engine 24+
- Docker Compose v2+
- Een OpenAI, Anthropic of Gemini API-sleutel

## Snelstart

Voer de volgende scripts uit vanaf de hoofdmap van de repository:

```bash
# Stap 1: Start de gateway
./examples/quickstart/01-start-gateway.sh

# Stap 2: Stuur een testverzoek met PII
./examples/quickstart/02-basic-anonymization.sh

# Stap 3: Opschonen
./examples/quickstart/03-cleanup.sh
```

De snelstartscripts regelen automatisch alle installatie, verificatie en opschonen. Elk script sluit af met code 0 bij succes of code 1 bij een fout met diagnostische output.

## Volgende stappen

- Zie `docs/en/installation.md` voor gedetailleerde installatie-instructies
- Zie `examples/curl/`, `examples/python/`, `examples/typescript/` en `examples/go/` voor SDK-voorbeelden in uw taal
- Zie `docs/en/deployment.md` voor richtlijnen voor productie-implementatie
- Zie `docs/en/compliance.md` voor het configureren van compliance presets
- Zie de project README voor een compleet overzicht

---
*Dit document is een vertaling of bewerking van het Engelse origineel. In geval de vertaling afwijkt, is het Engelse origineel leidend.*
