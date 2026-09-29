> translated from en/architecture.md

# AnonReq Gateway-Architektur

Dieses Dokument bietet eine Übersicht über die Architektur des AnonReq-Gateways. Es beschreibt die Komponententopologie, den Anfrage-Lebenszyklus und zentrale Sicherheitsinvarianten.

## Systemübersicht

AnonReq ist ein selbstgehostetes KI-Sicherheits- und Anonymisierungs-Gateway, das zwischen Unternehmensanwendungen und externen oder lokalen LLM-Anbietern (Large Language Model) geschaltet ist. Als abfangender Proxy stellt es sicher, dass sensible Daten (wie PII, PHI, PCI oder Geschäftsgeheimnisse) klassifiziert, tokenisiert und bereinigt werden, bevor sie die Vertrauensgrenze des Unternehmensnetzwerks überschreiten.

```
┌─────────────────┐       ┌─────────────────┐       ┌───────────────────┐
│                 │       │                 │       │                   │
│  Unternehmens-  │──────>│ AnonReq-Gateway │──────>│   LLM-Anbieter    │
│   anwendung     │<──────│ (Self-Hosted)   │<──────│ (OpenAI, Gemini)  │
│                 │       │                 │       │                   │
└─────────────────┘       └─────────────────┘       └───────────────────┘
```

## Anfrage-Lebenszyklus

Jede Anfrage, die über AnonReq an einen externen Anbieter gesendet wird, durchläuft eine mehrstufige Verarbeitungspipeline:

1. **Eingehende Anfragen & Content-Dispatching:** Die Anfrage erreicht das Gateway. Der Content-Type-Dispatcher prüft die Anfrage-Header und leitet die Nutzlast an den entsprechenden Analysator (Text, JSON oder Multipart) weiter.
2. **Klassifizierung:** Die Classification Engine prüft die Anfrage anhand konfigurierter Sicherheitsstufen. Enthält eine Nutzlast unzulässige vertrauliche Daten, blockiert die Engine die Anfrage frühzeitig oder entscheidet, ob ein lokales Routing, eine Anonymisierung oder ein direkter Durchgriff erforderlich ist.
3. **Erkennung:** Die Detection Engine kombiniert Prüfsummen-/Regex-Erkenner, Microsoft Presidio-Integration und Kontext-Boosting-Algorithmen, um sensible Entitäten (z. B. E-Mail-Adressen, Telefonnummern, Kreditkartennummern) zu identifizieren.
4. **Tokenisierung:** Erkannte sensible Werte werden extrahiert und durch anonyme Tokens ersetzt (z. B. `[EMAIL_0]`, `[PERSON_1]`). Die eindeutigen Zufallszuordnungen werden im sitzungsgebundenen Cache Manager (Valkey/Redis) gespeichert.
5. **Provider-Adapter:** Die bereinigte, tokenisierte Anfrage wird vom Provider-Adapter in das Ziel-LLM-API-Format übersetzt (z. B. Konvertierung des OpenAI-kompatiblen Schemas zu Anthropic/Gemini) und weitergeleitet.
6. **LLM-Antwort:** Das externe LLM gibt seine Antwort mit den tokenisierten Referenzen zurück.
7. **Wiederherstellung:** Die Restoration Engine liest die Sitzungszuordnungen aus dem Cache Manager und ersetzt die Tokens im Antworttext durch ihre Originalwerte (unterstützt sowohl Standard- als auch SSE-Streaming-Antworten).
8. **Ausgabe:** Die vollständig wiederhergestellte, natürliche Antwort wird an die Client-Anwendung zurückgegeben.

## Kernkomponenten

- **Proxy/Gateway:** FastAPI-Anwendung mit ASGI-Netzwerkschleife.
- **Classification Engine:** PDP (Policy Decision Point) und PEP (Policy Enforcement Point) zur Bewertung von Governance- und Risikoregeln.
- **Detection Engine:** Multi-Locale-Entitätsscanner mit Regex-Erkennern und Microsoft Presidio.
- **Tokenization- & Restoration-Engines:** Komponenten für Tokensubstitution und -rückersetzung.
- **Cache Manager:** Ephemerer In-Memory-Valkey/Redis-Dienst für sitzungsbezogene Zuordnungen unter strikter Time-to-Live (TTL).
- **Provider-Adapter:** Kompatibilitätsschicht zur dynamischen Übersetzung von API-Aufrufen.

## Sicherheitsinvarianten

- **Zero-Exposure-Invariante:** Reine Klartext-PII darf unter keinen Umständen die Netzwerkgrenze zu externen Anbietern überschreiten.
- **Fail-Secure/Fail-Closed-Verhalten:** Jede Laufzeitausnahme, jedes Timeout, jede Nichtverfügbarkeit des Caches, jeder Pipeline-Engpass oder jede Unklarheit bei der Klassifizierung führt zur sofortigen Blockierung des ausgehenden Datenverkehrs (`503 Service Unavailable` oder `403 Forbidden`), anstatt Daten preiszugeben.
- **Keine PII in Telemetriedaten:** Protokolle, Prometheus-Metriken und Sicherheitsberichte enthalten ausschließlich Metadaten. Keine Rohtexte, Nutzlasten oder Token-Schlüssel werden in persistente Speicher oder Standard-Ausgaben geschrieben.
- **Ephemerer Speicher:** Anonymisierungszuordnungen werden ausschließlich im Arbeitsspeicher-Cache mit engen TTL-Konfigurationen gehalten und nach Abschluss der Transaktion sofort gelöscht.
