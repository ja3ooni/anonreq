> translated from en/getting-started.md

# Per iniziare con AnonReq

## Prerequisiti

- Docker Engine 24+
- Docker Compose v2+
- Una chiave API OpenAI, Anthropic o Gemini

## Avvio rapido

Eseguire i seguenti script dalla radice del repository:

```bash
# Passaggio 1: Avvia il gateway
./examples/quickstart/01-start-gateway.sh

# Passaggio 2: Invia una richiesta di test con PII
./examples/quickstart/02-basic-anonymization.sh

# Passaggio 3: Pulisci
./examples/quickstart/03-cleanup.sh
```

Gli script di avvio rapido gestiscono automaticamente tutta la configurazione, la verifica e la pulizia. Ciascun script esce con codice 0 in caso di successo o 1 in caso di errore con output diagnostico.

## Passaggi successivi

- Vedere `docs/en/installation.md` per istruzioni dettagliate sull'installazione
- Vedere `examples/curl/`, `examples/python/`, `examples/typescript/` e `examples/go/` per esempi di SDK nel proprio linguaggio
- Vedere `docs/en/deployment.md` per una guida alla distribuzione in produzione
- Vedere `docs/en/compliance.md` per la configurazione dei preset di conformità
- Vedere il file README del progetto per una panoramica completa

---
*Questo documento è una traduzione dell'originale in inglese. In caso di discrepanza, prevale la versione inglese.*
