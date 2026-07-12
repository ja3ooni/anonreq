> translated from en/api-reference.md

# Riferimento API

La specifica OpenAPI completa è disponibile all'indirizzo `docs/openapi.json` (generata automaticamente dall'applicazione FastAPI). Questa pagina fornisce un riepilogo degli endpoint disponibili.

## Endpoint

| Metodo | Percorso | Descrizione |
|--------|----------|-------------|
| POST | `/v1/chat/completions` | Invia una richiesta di chat completion (compatibile con OpenAI) |
| GET | `/health` | Controllo di integrità aggregato per tutte le dipendenze |
| GET | `/v1/models` | Elenca gli alias del modello configurati |
| GET | `/v1/compliance/presets` | Elenca i preset di conformità disponibili |
| GET | `/v1/config/rules` | Elenca le regole di rilevamento personalizzate attive |
| GET | `/metrics` | Endpoint delle metriche di Prometheus |

### POST /v1/chat/completions

Accetta un corpo di richiesta di chat completion compatibile con OpenAI. Supporta sia la modalità di streaming (`stream: true`) che quella non in streaming. Vedere la specifica OpenAPI per lo schema completo.

### GET /health

Restituisce lo stato di salute aggregato del gateway e delle sue dipendenze (Presidio Analyzer, Valkey). Risposta:

```json
{"status":"pass","checks":{"presidio":"pass","valkey":"pass"}}
```

### GET /v1/models

Restituisce l'elenco degli alias di modelli configurati e i relativi provider di destinazione.

### GET /v1/compliance/presets

Restituisce i preset di conformità disponibili con i tipi di entità richiesti e le relative soglie di confidenza.

### GET /v1/config/rules

Restituisce le regole di rilevamento personalizzate attive (rilevatori regex e liste di esclusione).

### GET /metrics

Restituisce le metriche in formato Prometheus, inclusi il numero di richieste, la latenza di rilevamento, il numero di entità rilevate e i contatori degli eventi fail-secure.

## Autenticazione

Tutti gli endpoint API (eccetto `/health` e `/metrics`) richiedono un token Bearer nell'intestazione `Authorization`:

```bash
Authorization: Bearer <la-tua-chiave-api-anonreq>
```

La chiave API è configurata tramite la variabile d'ambiente `ANONREQ_API_KEY`.

---
*Questo documento è una traduzione dell'originale in inglese. In caso di discrepanza, prevale la versione inglese.*
