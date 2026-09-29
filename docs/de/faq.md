> translated from en/faq.md

# Häufig gestellte Fragen (FAQ)

## Was passiert, wenn die PII-Erkennung fehlschlägt?

Das Gateway verhält sich fail-secure. Wenn Fehler bei der Erkennung, im Cache oder Timeouts beim Anbieter auftreten, gibt die Anfrage HTTP 5xx zurück und es werden null Daten nach außen weitergeleitet. Einzelheiten hierzu finden Sie in der Fail-Secure-Architektur in der Projekt-README.

## Werden meine Daten irgendwo dauerhaft gespeichert?

Nein. Alle PII-zu-Token-Zuordnungen werden in Valkey ohne Persistenz gespeichert (`save ""`). Die Zuordnungen werden nach dem Senden der Antwort gelöscht. Protokolle enthalten ausschließlich Metadaten — keine PII-Rohwerte.

## Welche LLM-Anbieter werden unterstützt?

OpenAI, Azure OpenAI, Anthropic (Claude), Google Gemini und Ollama (lokale Modelle). Das Gateway übersetzt das OpenAI-kompatible Anfrageformat in das native Protokoll des jeweiligen Anbieters.

## Wie funktioniert Streaming?

Das Gateway verwendet eine Tail_Buffer-FSM (Finite State Machine), um Tokens zu verarbeiten, die über SSE-Chunk-Grenzen hinweg aufgeteilt sind. Tokens werden in Echtzeit wiederhergestellt, sobald Chunks eintreffen. Die Antwort ist Byte für Byte identisch mit dem Non-Streaming-Modus.

## Welches Format haben die Tokens?

Erkannte PII wird durch Platzhalter im Format `[TYPE_N]` ersetzt, wobei `TYPE` der Entitätstyp (z. B. `EMAIL`, `PHONE`) und `N` ein eindeutiger Index ist. Der Token-Abgleich bei der Wiederherstellung erfolgt unabhängig von Groß-/Kleinschreibung und optional ohne eckige Klammern.

## Wie werden verschiedene Sprachen und Regionen (Locales) behandelt?

Setzen Sie den Header `X-AnonReq-Locale`, um die regionsspezifische Erkennung zu aktivieren. Mehrere Locales können kombiniert werden (durch Kommas getrennt). Nicht unterstützte Locales geben HTTP 400 zurück.

## Kann ich benutzerdefinierte Erkennungsmuster hinzufügen?

Ja, benutzerdefinierte Regex-Erkenner können über eine YAML-Konfigurationsdatei hinzugefügt und im laufenden Betrieb ohne Neustart neu geladen werden. Das Regelformat finden Sie in der Konfigurationsdokumentation.

## Wie kann ich zum Projekt beitragen?

Beiträge sind unter der Apache 2.0-Lizenz herzlich willkommen. Richtlinien für Pull Requests und Hinweise zur Entwicklungsumgebung finden Sie im Leitfaden für Mitwirkende (Contributing Guide) im Repository.
