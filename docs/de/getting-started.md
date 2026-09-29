> translated from en/getting-started.md

# Erste Schritte mit AnonReq

## Voraussetzungen

- Docker Engine 24+
- Docker Compose v2+
- Ein API-Schlüssel für OpenAI, Anthropic oder Gemini

## Schnellstart

Führen Sie die folgenden Skripte aus dem Repository-Wurzelverzeichnis aus:

```bash
# Schritt 1: Gateway starten
./examples/quickstart/01-start-gateway.sh

# Schritt 2: Testanfrage mit PII senden
./examples/quickstart/02-basic-anonymization.sh

# Schritt 3: Bereinigen
./examples/quickstart/03-cleanup.sh
```

Die Schnellstart-Skripte übernehmen die gesamte Einrichtung, Verifizierung und Bereinigung automatisch. Jedes Skript wird bei Erfolg mit Exit-Code 0 oder bei Fehlern mit diagnostischen Ausgaben beendet.

## Nächste Schritte

- Siehe [installation.md](installation.md) für detaillierte Installationsanweisungen
- Siehe `examples/curl/`, `examples/python/`, `examples/typescript/` und `examples/go/` für SDK-Beispiele in Ihrer Programmiersprache
- Siehe [deployment.md](deployment.md) für Hinweise zum Produktivbetrieb
- Siehe [compliance.md](compliance.md) für die Konfiguration von Compliance-Vorgaben
- Siehe die Projekt-README für eine vollständige Übersicht
