> translated from en/faq.md

# Domande frequenti

## Cosa succede se il rilevamento PII fallisce?

Il gateway è fail-secure. Se si verificano errori di rilevamento, cache o timeout del provider, la richiesta restituisce un codice HTTP 5xx e nessun dato viene inoltrato a monte. Per i dettagli, vedere l'architettura fail-secure nel file README del progetto.

## I miei dati vengono memorizzati da qualche parte?

No. Tutte le mappature da PII a token sono memorizzate in Valkey senza persistenza (`save ""`). Le mappature vengono eliminate dopo l'invio della risposta. I log contengono solo metadati, nessun valore PII non elaborato.

## Quali provider LLM sono supportati?

OpenAI, Azure OpenAI, Anthropic (Claude), Google Gemini e Ollama (modelli locali). Il gateway traduce il formato di richiesta compatibile con OpenAI nel protocollo nativo di ciascun provider.

## Come funziona lo streaming?

Il gateway utilizza una FSM di tipo Tail_Buffer per gestire i token divisi tra i blocchi SSE. I token vengono ripristinati in tempo reale all'arrivo dei blocchi. La risposta è identica byte per byte alla modalità non streaming.

## Qual è il formato del token?

Il PII rilevato viene sostituito con segnaposto `[TYPE_N]`, dove `TYPE` è il tipo di entità (ad esempio, `EMAIL`, `PHONE`) e `N` è un indice univoco. La corrispondenza dei token non distingue tra maiuscole e minuscole e le parentesi quadre sono opzionali durante il ripristino.

## Come vengono gestiti i locali?

Impostare l'intestazione `X-AnonReq-Locale` per attivare il rilevamento specifico del locale. Più locali possono essere combinati (separati da virgole). I locali non supportati restituiscono HTTP 400.

## Posso aggiungere modelli di rilevamento personalizzati?

Sì, è possibile aggiungere rilevatori regex personalizzati tramite un file di configurazione YAML e ricaricarli a caldo senza riavviare. Vedere la documentazione di configurazione per il formato della regola.

## Come posso contribuire?

I contributi sono benvenuti sotto la licenza Apache 2.0. Vedere la guida per i contributori nel repository per le linee guida sulle pull request e le istruzioni per la configurazione dello sviluppo.

---
*Questo documento è una traduzione dell'originale in inglese. In caso di discrepanza, prevale la versione inglese.*
