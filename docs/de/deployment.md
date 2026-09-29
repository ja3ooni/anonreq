> translated from en/deployment.md

# Bereitstellung (Deployment)

## Überlegungen für den Produktivbetrieb

### Ressourcenzuweisung

Stellen Sie sicher, dass Ihr Host die Mindestressourcenanforderungen für alle drei Container erfüllt. Für Produktionsbereitstellungen wird ein Puffer von 50 % über der beobachteten Spitzenauslastung empfohlen.

### Protokollierungskonfiguration

Protokolle werden im strukturierten JSON-Format auf stdout ausgegeben. Konfigurieren Sie die Protokollaggregation über Ihr bevorzugtes Werkzeug (Docker-Logging-Treiber, syslog oder Log-Shipper wie Fluentd oder Vector).

### Netzwerksicherheit

Das Gateway bindet an Port 8000. Presidio Analyzer und Valkey sind in einem internen Docker-Netzwerk isoliert und von außen nicht direkt erreichbar.

### TLS-Terminierung

Terminieren Sie TLS an Ihrem Reverse-Proxy (nginx, Caddy oder Cloud-Load-Balancer) und leiten Sie Anfragen über HTTP im internen Netzwerk an das Gateway weiter.

## Umgebungsvariablen

| Variable | Typ | Standard | Erforderlich | Beschreibung |
|----------|-----|----------|--------------|--------------|
| `ANONREQ_API_KEY` | string | — | Ja | Bearer-Token für API-Authentifizierung (≥ 32 Zeichen) |
| `ANONREQ_LOG_LEVEL` | string | `INFO` | Nein | Protokollierungsstufe: DEBUG, INFO, WARNING, ERROR |
| `ANONREQ_CACHE_URL` | string | `valkey://localhost:6379` | Nein | Valkey-Server-URL |
| `ANONREQ_CACHE_PASSWORD` | string | — | Nein | Valkey requirepass |
| `ANONREQ_CACHE_TTL` | int | `600` | Nein | Sitzungs-TTL in Sekunden (60–3600) |
| `ANONREQ_OPENAI_API_KEY` | string | — | Bedingt | OpenAI API-Schlüssel |
| `ANONREQ_ANTHROPIC_API_KEY` | string | — | Bedingt | Anthropic API-Schlüssel |
| `ANONREQ_GEMINI_API_KEY` | string | — | Bedingt | Google Gemini API-Schlüssel |
| `ANONREQ_OLLAMA_BASE_URL` | string | — | Nein | Ollama-Server-URL |
| `ANONREQ_LOCALE` | string | `en-US` | Nein | Standard-Erkennungs-Locale |
| `ANONREQ_COMPLIANCE_PRESET` | string | — | Nein | Name des Compliance-Presets |
| `ANONREQ_CONFIDENCE_THRESHOLD` | float | `0.7` | Nein | Erkennungs-Konfidenzschwellenwert (0.0–1.0) |
| `PRESIDIO_ANALYZER_URL` | string | `http://presidio-analyzer:5001` | Nein | Presidio Analyzer URL |

## Docker Compose Produktivkonfiguration

Passen Sie die standardmäßige `docker-compose.yml` mit einer `docker-compose.override.yml`-Datei an:

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

### Health-Check-Konfiguration

Jeder Dienst verfügt über eine integrierte Zustandsprüfung (Health Check). Überwachen Sie alle drei Dienste über den `/health`-Endpunkt des Gateways. Richten Sie eine externe Überwachung ein, um bei Nicht-200-Antworten zu alarmieren.

### Neustartrichtlinien

Alle Dienste nutzen `restart: unless-stopped`. Für unterbrechungsfreie Bereitstellungen (Zero-Downtime) betreiben Sie mehrere Gateway-Replikate hinter einem Load Balancer.

## Protokollierung

Strukturierte JSON-Logs werden auf stdout ausgegeben. Wichtige Felder: `timestamp`, `level`, `event`, `session_id`, `latency_ms`, `entity_count`, `provider`. Verarbeiten Sie diese mit Ihrem bevorzugten Log-Aggregator.

## Aktualisierung (Upgrade)

1. Neuestes Image abrufen: `docker compose pull anonreq`
2. Dienste neu erstellen: `docker compose up -d --force-recreate anonreq`
3. Zustand prüfen: `curl http://localhost:8000/health`

## Sicherheit

- Das Gateway verhält sich fail-secure: Jeder Erkennungs- oder Cache-Fehler liefert HTTP 5xx und leitet niemals unbereinigte Daten weiter.
- Die Rotation von API-Schlüsseln wird durch Neustart unterstützt: Aktualisieren Sie `ANONREQ_API_KEY` in `.env` und führen Sie `docker compose restart anonreq` aus.
- Alle Cache-Daten sind ephemer — es werden keine sensiblen Daten auf Festplatte geschrieben.
