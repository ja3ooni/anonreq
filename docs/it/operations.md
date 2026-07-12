> translated from en/operations.md

# Guida operativa AnonReq

Questa guida fornisce runbook operativi, strutture di configurazione, specifiche di monitoraggio e passaggi per la risoluzione dei problemi per gli operatori del gateway AnonReq.

## Gestione della configurazione

Le configurazioni del gateway vengono gestite tramite file YAML caricati all'avvio del container. Le configurazioni principali sono:

- **Motore di policy (`config/policy.yaml`):** Definisce le regole del tenant, i limiti di velocità, i budget di spesa e le regole di residenza.
- **Configurazione SLO (`config/slo.yaml`):** Dichiara gli obiettivi operativi per la percentuale di successo, la latenza, gli eventi fail-secure e le scritture di controllo.
- **Trust Center (`config/trust_center.yaml`):** Regola l'accesso al portale di conformità.

Le configurazioni vengono ricaricate automaticamente al ricevimento del segnale `SIGHUP`.

### Esempio di configurazione delle policy

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

## Monitoraggio degli obiettivi del livello di servizio (SLO)

AnonReq tiene traccia di 4 SLO principali per garantire la sicurezza operativa e le prestazioni:

1. **Percentuale di successo:** Almeno il 99,9% delle richieste deve avere successo.
2. **Latenza P95:** Il tempo di elaborazione deve rimanere ≤100 ms.
3. **Percentuale fail-secure:** ≤0,1% delle transazioni deve attivare blocchi fail-secure.
4. **Scrittura log di controllo:** ≥99,99% delle scritture dei log deve essere completato con successo.

### Infrastruttura di monitoraggio

- **Prometheus Dashboard:** Raccoglie metriche da `/metrics` sulla porta `8080`.
- **Grafana Dashboard:** Visualizza lo stato di conformità dei vari SLO e il consumo del relativo budget.

## Operazioni amministrative CLI

Gli operatori di sistema utilizzano le richieste curl per verificare lo stato e aggiornare le policy.

### 1. Controllare le policy attive
```bash
curl -X GET http://localhost:8080/v1/admin/policies   -H "Authorization: Bearer <ADMIN_API_KEY>"   -H "X-AnonReq-Role: operator"   -H "X-AnonReq-Tenant-ID: default"
```

### 2. Interrogare la conformità degli SLO in tempo reale
```bash
curl -H "Authorization: Bearer <ADMIN_API_KEY>"      -H "X-AnonReq-Role: administrator"      http://localhost:8080/v1/governance/status
```

### 3. Verificare l'integrità della catena di controllo
```bash
curl -X POST http://localhost:8080/v1/governance/audit/verify   -H "Authorization: Bearer <ADMIN_API_KEY>"   -H "X-AnonReq-Role: administrator"
```

## Risoluzione dei problemi e diagnostica

Se un SLO viene violato, vengono inviate notifiche di allerta. Gli operatori dovrebbero controllare:

- **Calo percentuale di successo:** Verificare la connettività verso i provider LLM esterni e controllare il carico CPU/memoria di Valkey.
- **Picco di latenza:** Monitorare l'utilizzo delle risorse del gateway ed eventualmente scalare le repliche.
- **Aumento dei blocchi fail-secure:** Controllare lo stato e i log del container Presidio Analyzer.
- **Mancata scrittura dell'audit:** Verificare lo stato della connessione al database SQL o l'esaurimento dello spazio su disco.

---
*Questo documento è una traduzione dell'originale in inglese. In caso di discrepanza, prevale la versione inglese.*
