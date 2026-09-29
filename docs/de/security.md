> translated from en/security.md

# AnonReq Sicherheitsrichtlinie

Dieses Dokument beschreibt die Sicherheitsarchitektur, Datenverarbeitungsgarantien und Incident-Response-Verfahren für das AnonReq-Gateway.

## Sicherheitskonzept

AnonReq basiert auf einer Zero-Trust-Architektur. Wir stufen alle externen Modell-Endpunkte und öffentlichen Netzwerke als nicht vertrauenswürdig ein und setzen strikte, ausfallsichere (fail-secure) Sicherheitsgrenzen durch:

- **Minimales Privileg (Least Privilege):** Alle administrativen Routen und Konfigurationsänderungen erfordern eine validierte Autorisierung mittels API-Schlüsseln hoher Entropie.
- **Fail-Secure-Standards:** Alle Konfigurationsparameter sind standardmäßig auf den restriktivsten Zustand eingestellt (z. B. Trust Center deaktiviert, aktive Voreinstellungen erforderlich, Standard-Blockieraktionen).
- **Isolation:** Mandantendaten, Richtlinienspeicher und sitzungsbasierte Caches werden innerhalb der Valkey-Speicherschicht mittels Präfix-Namespaces strikt voneinander isoliert.

## Anonymisierung und Datengarantien

AnonReq garantiert, dass vertrauliche Informationen im Klartext niemals an externe Netzwerke weitergegeben werden:

1. **Ausgehender Datenschutz:** Das Gateway fängt sämtlichen Anfragetext, JSON-Objekte und mehrteilige Formulare ab. Klartext-Treffer werden vor dem Netzwerktransit durch formatwahrende Variablen (z. B. `[EMAIL_N]`) tokenisiert.
2. **Ephemeres Speichermodell:** Token-Zuordnungen werden ausschließlich im Valkey/Redis-Cache gespeichert. Sie unterliegen strengen Time-to-Live-Richtlinien (TTL) und werden unmittelbar nach Auslieferung der Transaktionsantwort oder nach Ablauf des Timeouts gelöscht.
3. **Keine PII in Protokollen oder Telemetrie:** Audit-Trails, Systemprotokolle (stdout/stderr) und Prometheus-Metriken enthalten ausschließlich Metadaten (wie Anfragestatus, Latenz und Regel-IDs). Klartext-Nutzlasten, Sitzungsschlüssel und einzelne Token-Werte werden niemals protokolliert.

## Incident-Response-Protokoll

AnonReq unterhält einen aktiven Incident-Response-Workflow für betriebliche, kryptografische oder sanitierungsbezogene Anomalien. Sicherheitsvorfälle werden in drei Schweregrade eingeteilt:

### Schweregrade

- **Schweregrad 1 (Kritisch):** Klartext-PII-Leck oder Datenschutzverletzung; Fehler bei der kryptografischen Verifizierung der Anker-Signatur in der Audit-Trail-Kette. Erfordert Eindämmung innerhalb von 1 Stunde.
- **Schweregrad 2 (Schwerwiegend):** Dienstausfall, Container-Absturz oder vollständige Beeinträchtigung der Pipeline. Erfordert Behebung innerhalb von 4 Stunden.
- **Schweregrad 3 (Geringfügig):** Unkritische Betriebswarnungen oder geringfügige Leistungseinbußen (z. B. Überschreitung des Latenzschwellenwerts, Anstauung in der Datenbank-DLQ). Erfordert Untersuchung innerhalb von 24 Stunden.

### Reaktionsablauf

1. **Erkennung:** Warnmeldungen werden über Prometheus-Metriken oder die manuelle Validierung der Endpunkte für die Integrität des Audit-Trails ausgelöst.
2. **Triage:** Der SRE- oder Security-On-Call-Ingenieur bewertet den Alarm und weist den Schweregrad zu.
3. **Eindämmung:** Bei kritischen Vorfällen kann das Gateway sofort ausgesetzt werden (Notfallaussetzung) oder einzelne Mandantenschlüssel können widerrufen werden.
4. **Behebung:** Kernentwickler isolieren die Ursache, erstellen einen Container-Patch und spielen das Update ein.
5. **Wiederherstellung:** Der Normalbetrieb wird wiederhergestellt und die Integrität der Audit-Kette verifiziert.
6. **Post-Mortem:** Innerhalb von 5 Werktagen wird eine formelle Überprüfung durchgeführt, um den Zeitablauf, die Ursache und präventive Maßnahmen zu dokumentieren.
