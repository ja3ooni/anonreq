> translated from en/operations.md

# AnonReq Operations Handleiding

Deze handleiding biedt operationele runbooks, configuratiestructuren, monitoringsspecificaties en probleemoplossingsstappen voor beheerders van de AnonReq-gateway.

## Configuratiebeheer

De gatewayconfiguraties worden beheerd via YAML-bestanden die tijdens het opstarten van de container worden geladen. De belangrijkste configuraties zijn:

- **Policy Engine (`config/policy.yaml`):** Definieert tenant-specifieke regels, snelheidslimieten, spend-budgetten en residency-regels.
- **SLO-configuratie (`config/slo.yaml`):** Declareert de operationele doelen voor succespercentage, latentie, fail-secure statussen en audit-schrijfbewerkingen.
- **Trust Center (`config/trust_center.yaml`):** Regelt de toegang tot de openbare compliance portal.

Configuraties worden automatisch opnieuw geladen bij het ontvangen van een `SIGHUP`-signaal.

### Voorbeeld van een policyconfiguratie

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

## Monitoren van Service Level Objectives (SLO's)

AnonReq volgt 4 primaire SLO's om de operationele veiligheid en prestaties te garanderen:

1. **Succespercentage:** Ten minste 99,9% van de verzoeken moet slagen.
2. **P95-latentie:** De verwerkingstijd moet ≤100 ms blijven.
3. **Fail-secure percentage:** ≤0,1% van de transacties mag een fail-secure blokkering activeren.
4. **Audit-schrijfpercentage:** Ten minste 99,99% van de audit-schrijfbewerkingen moet slagen.

### Monitoring-infrastructuur

- **Prometheus-dashboard:** Verzamelt statistieken van `/metrics` op poort `8080`.
- **Grafana-dashboard:** Visualiseert de naleving van de SLO's en foutbudgetten.

## Administratieve CLI-bewerkingen

Systeembeheerders gebruiken curl-verzoeken om de status op te vragen en beleidsregels bij te werken.

### 1. Actieve policies controleren
```bash
curl -X GET http://localhost:8080/v1/admin/policies   -H "Authorization: Bearer <ADMIN_API_KEY>"   -H "X-AnonReq-Role: operator"   -H "X-AnonReq-Tenant-ID: default"
```

### 2. Realtime SLO-naleving opvragen
```bash
curl -H "Authorization: Bearer <ADMIN_API_KEY>"      -H "X-AnonReq-Role: administrator"      http://localhost:8080/v1/governance/status
```

### 3. Integriteit van de cryptografische auditketen controleren
```bash
curl -X POST http://localhost:8080/v1/governance/audit/verify   -H "Authorization: Bearer <ADMIN_API_KEY>"   -H "X-AnonReq-Role: administrator"
```

## Probleemoplossing en herstel

Wanneer een SLO wordt geschonden, verstuurt de gateway automatisch waarschuwingen. Beheerders moeten de volgende subsystemen controleren:

- **Daling succespercentage:** Controleer de verbinding met externe LLM-providers en inspecteer het resourceverbruik van Valkey.
- **Latentiepieken:** Controleer het CPU-/geheugengebruik van de gatewaycontainers en schaal de instanties indien nodig op.
- **Toename fail-secure percentage:** Inspecteer de logboeken om te controleren of de Presidio Analyzer-container reageert.
- **Fouten bij het schrijven van audits:** Controleer de verbinding met Valkey of de capaciteit van de databasepool. Controleer de schijfruimte.

---
*Dit document is een vertaling of bewerking van het Engelse origineel. In geval de vertaling afwijkt, is het Engelse origineel leidend.*
