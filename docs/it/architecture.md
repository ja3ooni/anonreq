> translated from en/architecture.md

# Architettura del gateway AnonReq

Questo documento fornisce un riepilogo dell'architettura del gateway AnonReq. Dettaglia la topologia dei componenti, il ciclo di vita delle richieste e le invarianti di sicurezza principali.

## Panoramica del sistema

AnonReq è un gateway di sicurezza e anonymisation AI auto-ospitato progettato per fungere da intermediario tra le applicazioni aziendali e i provider LLM (Large Language Model) esterni o locali. Agendo come un proxy di intercettazione, garantisce che i dati sensibili (come PII, PHI, PCI o segreti aziendali) vengano classificati, tokenizzati e sanitizzati prima di superare il limite di fiducia della rete aziendale.

```
┌─────────────────┐       ┌─────────────────┐       ┌───────────────────┐
│                 │       │                 │       │                   │
│   Applicazione  │──────>│ Gateway         │──────>│ Provider LLM      │
│   Aziendale     │<──────│ AnonReq         │<──────│ (OpenAI, Gemini)  │
│                 │       │ (Auto-ospitato) │       │                   │
└─────────────────┘       └─────────────────┘       └───────────────────┘
```

## Ciclo di vita delle richieste

Ogni richiesta inviata a un provider esterno tramite AnonReq passa attraverso una pipeline di elaborazione strutturata:

1. **Ricezione e smistamento dei contenuti:** La richiesta entra nel gateway. Il dispatcher del tipo di contenuto esamina le intestazioni e instrada il payload all'analizzatore appropriato (Text, JSON o Multipart).
2. **Classificazione:** Il motore di classificazione valuta la richiesta rispetto ai livelli di sicurezza configurati. Se un payload contiene dati limitati che non possono procedere, il motore blocca la richiesta o determina se è necessario il routing locale, l'anonymisation o il passaggio diretto.
3. **Rilevamento:** Il motore di rilevamento combina rilevatori regex/checksum, integrazione con Presidio e algoritmi di ottimizzazione del contesto per individuare entità sensibili (es. e-mail, numeri di telefono, carte di credito).
4. **Tokenizzazione:** I valori sensibili rilevati vengono estratti e sostituiti con token anonimi (es. `[EMAIL_0]`, `[PERSON_1]`). I mapping sono memorizzati in Valkey/Redis Cache Manager con un ciclo di vita associato alla sessione.
5. **Adattatore del provider:** La richiesta sanitizzata viene tradotta dall'adattatore nel formato API del LLM di destinazione (es. da OpenAI ad Anthropic/Gemini) e inoltrata.
6. **Risposta LLM:** Il LLM esterno restituisce la sua risposta contenente i riferimenti tokenizzati.
7. **Ripristino:** Il motore di ripristino recupera le mappature dal Cache Manager e sostituisce i token con i loro valori originali nella risposta (supporta lo streaming SSE).
8. **In uscita:** La risposta ripristinata viene restituita all'applicazione client.

## Componenti principali

- **Proxy/Gateway:** Applicazione FastAPI che esegue un ciclo di rete ASGI.
- **Motore di classificazione:** PDP (Policy Decision Point) e PEP (Policy Enforcement Point) che valutano le policy di governance e di rischio.
- **Motore di rilevamento:** Scanner multi-locale con rilevatori regex e Microsoft Presidio.
- **Motori di tokenizzazione e ripristino:** Codice responsabile della sostituzione e del ripristino dei token.
- **Gestore cache:** Istanza Valkey/Redis in memoria che mantiene i mapping di sessione con un TTL rigido.
- **Adattatori dei provider:** Strato di compatibilità che traduce le chiamate API in tempo real.

## Invarianti di sicurezza principali

- **Zero esposizione delle PII:** Le PII non elaborate non devono mai superare il limite della rete aziendale verso provider esterni.
- **Comportamento fail-secure:** Qualsiasi eccezione, timeout, errore di cache o ambiguità di classificazione deve bloccare immediatamente il traffico in uscita e restituire HTTP 503 o 403.
- **Telemetria senza PII:** Log di controllo e metriche di Prometheus contengono solo metadati. Nessun valore PII o chiave token viene registrato.
- **Archiviazione effimera:** Le mappature dei token sono memorizzate solo nella cache con TTL rigidi e rimosse subito dopo la risposta.

---
*Questo documento è una traduzione dell'originale in inglese. In caso di discrepanza, prevale la versione inglese.*
