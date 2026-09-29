> translated from en/api-reference.md

# API-Referenz

Die vollständige OpenAPI-Spezifikation steht unter `docs/openapi.json` zur Verfügung (automatisch aus der FastAPI-Anwendung generiert). Diese Seite bietet eine Zusammenfassung der verfügbaren Endpunkte.

## Endpunkte

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| POST | `/v1/chat/completions` | Chat-Completion-Anfrage senden (OpenAI-kompatibel) |
| GET | `/health` | Aggregierter Health-Check für alle Abhängigkeiten |
| GET | `/v1/models` | Verfügbare Modell-Aliase auflisten |
| GET | `/v1/compliance/presets` | Verfügbare Compliance-Presets auflisten |
| GET | `/v1/config/rules` | Aktive benutzerdefinierte Erkennungsregeln auflisten |
| GET | `/metrics` | Prometheus-Metriken-Endpunkt |

### POST /v1/chat/completions

Akzeptiert einen OpenAI-kompatiblen Chat-Completion-Anfrage-Body. Unterstützt sowohl Streaming (`stream: true`) als auch Non-Streaming-Modi. Das vollständige Schema finden Sie in der OpenAPI-Spezifikation.

### GET /health

Gibt den aggregierten Zustandsstatus des Gateways und seiner Abhängigkeiten (Presidio Analyzer, Valkey) zurück. Antwort:

```json
{"status":"pass","checks":{"presidio":"pass","valkey":"pass"}}
```

### GET /v1/models

Gibt die Liste der konfigurierten Modell-Aliase und der zugehörigen Zielanbieter zurück.

### GET /v1/compliance/presets

Gibt verfügbare Compliance-Voreinstellungen mit den vorgeschriebenen Entitätstypen und Konfidenzschwellenwerten zurück.

### GET /v1/config/rules

Gibt aktive benutzerdefinierte Erkennungsregeln (Recognizers und Ausschlusslisten) zurück.

### GET /metrics

Gibt Metriken im Prometheus-Format zurück, einschließlich Anfrageanzahl, Erkennungslatenz, Entitätsanzahl und Zähler für Fail-Secure-Ereignisse.

## Authentifizierung

Alle API-Endpunkte (außer `/health` und `/metrics`) erfordern einen Bearer-Token im `Authorization`-Header:

```bash
Authorization: Bearer <your-anonreq-api-key>
```

Der API-Schlüssel wird über die Umgebungsvariable `ANONREQ_API_KEY` konfiguriert.
