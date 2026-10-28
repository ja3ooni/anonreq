> translated from en/installation.md

# Installation

## Voraussetzungen

- Python 3.12+
- Docker Engine 24+ mit Docker Compose v2+
- Mindestens 4 GB RAM (8 GB empfohlen)

## Repository klonen

```bash
git clone https://github.com/anonreq/anonreq.git
cd anonreq
```

## Umgebungskonfiguration

Kopieren Sie die Beispiel-Umgebungsdatei und konfigurieren Sie die erforderlichen Variablen:

```bash
cp .env.example .env
```

| Variable | Erforderlich | Standard | Beschreibung |
|----------|--------------|----------|--------------|
| `ANONREQ_API_KEY` | Ja | — | Statischer Bearer-Token für API-Authentifizierung (≥ 32 Zeichen). Wird nie upstream gesendet. |
| `PROVIDER_API_KEY` | Bedingt | — | Schlüssel des Modell-Anbieters. Pflicht, außer jeder konfigurierte Anbieter ist mock, local oder ollama. Nicht `ANONREQ_API_KEY` wiederverwenden. |
| `ANONREQ_LOG_LEVEL` | Nein | `INFO` | Protokollierungsstufe |
| `ANONREQ_CACHE_TTL` | Nein | `600` | Sitzungs-Cache-TTL in Sekunden |
| `ANONREQ_PRESIDIO_URL` | Nein | `http://presidio-analyzer:5001` | Presidio Analyzer URL |
| `ANONREQ_VALKEY_URL` | Nein | `valkey://localhost:6379` | Valkey-Verbindungszeichenfolge |

Der Start bricht ab, wenn ein konfigurierter Anbieter einen Schlüssel braucht und keinen hat. OpenAI akzeptiert `PROVIDER_API_KEY`, `ANONREQ_OPENAI_API_KEY` oder `OPENAI_API_KEY`. `ANONREQ_ANTHROPIC_API_KEY` und `ANONREQ_GEMINI_API_KEY` sind Pflicht, solange die Aliase `smart` und `gemini-pro` in `config/model_aliases.yaml` stehen. `mock`, `local` und `ollama` brauchen keinen Schlüssel. Der Gateway-Client-Schlüssel wird nie als Anbieter-Schlüssel verwendet.

## Docker Compose Setup

```bash
docker compose up -d --wait
```

Dies startet alle drei Dienste: `anonreq` (Gateway), `presidio-analyzer` (PII-Erkennung) und `valkey` (ephemerer Cache).

## Installation überprüfen

```bash
curl http://localhost:8000/health
```

Erwartete Antwort: HTTP 200 mit `{"status":"pass","checks":{"presidio":"pass","valkey":"pass"}}`.

## Fehlerbehebung

| Problem | Wahrscheinliche Ursache | Lösung |
|---------|-------------------------|--------|
| Health-Check liefert 503 | Presidio-Modell lädt noch | 60 s auf Modell-Download warten, dann erneut versuchen |
| `docker compose up` schlägt fehl | Port 8000 belegt | Andere Dienste stoppen oder Portzuordnung anpassen |
| `curl: connection refused` | Gateway noch nicht bereit | `docker compose ps` ausführen, um den Status zu prüfen |
