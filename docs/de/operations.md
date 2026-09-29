> translated from en/operations.md

# AnonReq Betriebsleitfaden

Dieser Leitfaden enthält Betriebs-Runbooks, Konfigurationsstrukturen, Überwachungsspezifikationen und Schritte zur Fehlerbehebung für Systemoperatoren, die das AnonReq-Gateway verwalten.

## Konfigurationsmanagement

Die Gateway-Konfigurationen werden über YAML-Dateien verwaltet, die beim Start des Containers geladen werden. Die Hauptkonfigurationen sind:

- **Policy Engine (`config/policy.yaml`):** Definiert Mandantenregeln, Ratenbegrenzungen, Ausgabenbudgets und Datenresidenzgrenzen.
- **SLO-Konfiguration (`config/slo.yaml`):** Deklariert Betriebsziele für Erfolgsquote, Latenzen, Fail-Secure-Zustände und Audit-Schreibvorgänge.
- **Trust Center (`config/trust_center.yaml`):** Steuert öffentliche Compliance-Portale und Anzeige-Metadaten.

Konfigurationen werden beim Empfang eines `SIGHUP`-Signals automatisch im laufenden Betrieb neu geladen.

### Beispiel für eine Richtlinienkonfiguration

```yaml
version: "1.0"
rules:
  - rule_id: "block_restricted_pii"
    name: "Block Restricted Data"
    action: "BLOCK"
    priority: 100
    enabled: true
    conditions:
      classification_level: "Restricted"
rate_limits:
  enabled: true
  rpm: 1000
```

## Überwachung der Service Level Objectives (SLOs)

AnonReq überwacht 4 primäre SLOs, um Systemsicherheit und -leistung zu gewährleisten:

1. **Erfolgsquote (Success Rate):** ≥99,9 % der Gateway-Anfragen müssen erfolgreich sein.
2. **P95-Latenz:** Der Verarbeitungs-Overhead muss ≤100 ms bleiben.
3. **Fail-Secure-Quote:** ≤0,1 % der Transaktionen dürfen Fail-Secure-Blockierungen auslösen.
4. **Audit-Schreibquote:** ≥99,99 % der Audit-Log-Schreibvorgänge müssen erfolgreich abgeschlossen werden.

### Observability-Infrastruktur

- **Prometheus-Dashboard:** Ruft Metriken von `/metrics` auf Port `8080` ab.
- **Grafana-Dashboard:** Visualisiert SLO-Einhaltungsziele und Fehlerbudgets.

## Administrative CLI-Operationen

Systemoperatoren verwenden `curl`-Befehle, um den Status abzufragen, Metriken abzurufen und Aktualisierungen durchzuführen.

### 1. Aktive Richtlinien prüfen

```bash
curl -X GET http://localhost:8080/v1/admin/policies \
  -H "Authorization: Bearer <ADMIN_API_KEY>" \
  -H "X-AnonReq-Role: operator" \
  -H "X-AnonReq-Tenant-ID: default"
```

### 2. Echtzeit-SLO-Einhaltung abfragen

```bash
curl -H "Authorization: Bearer <ADMIN_API_KEY>" \
     -H "X-AnonReq-Role: administrator" \
     http://localhost:8080/v1/governance/status
```

### 3. Integrität der kryptografischen Audit-Kette verifizieren

```bash
curl -X POST http://localhost:8080/v1/governance/audit/verify \
  -H "Authorization: Bearer <ADMIN_API_KEY>" \
  -H "X-AnonReq-Role: administrator"
```

## Fehlerbehebung und Wiederherstellung nach Vorfällen

Wenn ein SLO verletzt wird, gibt das Gateway automatisch Warnmeldungen aus. Operatoren sollten folgende Subsysteme überprüfen:

- **Rückgang der Erfolgsquote:** Prüfen Sie die Netzwerkkonnektivität zu Upstream-LLM-Anbietern (OpenAI/Gemini) und untersuchen Sie die Ressourcennutzung von Valkey vor Ort.
- **Latenzspitzen:** Überprüfen Sie die CPU-/Speicherauslastung der Gateway-Container und skalieren Sie die Instanzen nach Bedarf.
- **Anstieg der Fail-Secure-Quote:** Prüfen Sie die Protokolle, um festzustellen, ob der Microsoft Presidio Analyzer-Container antwortet oder benutzerdefinierte Regex-Muster nicht kompiliert werden können.
- **Fehler beim Schreiben von Audit-Logs:** Überprüfen Sie die Valkey-Konnektivität oder die Kapazität des SQL-Datenbankverbindungspools. Prüfen Sie auf Deadlocks oder Speicherplatzmangel.
