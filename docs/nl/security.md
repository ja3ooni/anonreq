> translated from en/security.md

# AnonReq Beveiligingsbeleid

Dit document beschrijft de beveiligingsstatus, gegevensverwerkingsgaranties en incidentrespons-procedures voor de AnonReq gateway.

## Beveiligingsstatus

AnonReq is gebouwd op een Zero-Trust architectuur. We gaan ervan uit dat alle externe model-endpoints en openbare netwerken onbetrouwbaar zijn, en dwingen strikte beveiligingsgrenzen af:

- **Minimale privileges:** Alle administratieve routes en configuratiewijzigingen vereisen gevalideerde autorisatie met behulp van API-sleutels met hoge entropie.
- **Fail-Secure standaardinstellingen:** Alle configuratieparameters zijn standaard ingesteld op de meest beperkende status (bijvoorbeeld Trust Center uitgeschakeld, verplichte compliance presets, standaard blokkeeracties).
- **Isolatie:** Gegevens van tenants, beleidsregels en sessie-caches zijn strikt geïsoleerd binnen het Valkey-geheugen met behulp van prefix-namespaces.

## Anonymisation en gegevensgaranties

AnonReq garandeert dat gevoelige informatie in plaintext nooit wordt blootgesteld aan externe netwerken:

1. **Uitgaande gegevensbescherming:** De gateway onderschept alle tekstverzoeken, JSON-objecten en multipart-formulieren. Plaintext-matches worden getokeniseerd met placeholders (bijv. `[EMAIL_N]`) vóór netwerktransport.
2. **Tijdelijk geheugenmodel:** Token-mappings worden exclusief opgeslagen in de Valkey/Redis-cache. Ze zijn gebonden aan strikte TTL-beleidsregels en worden onmiddellijk verwijderd nadat de respons is afgeleverd of de time-out is verstreken.
3. **Geen PII in logboeken of telemetrie:** Audit trails, systeemlogboeken en Prometheus-statistieken bevatten alleen metadata. Plaintext-gegevens en token-waarden worden nooit gelogd.

## Incidentrespons-protocol

AnonReq hanteert een actieve incidentrespons-workflow voor operationele of sanitatie-anomalieën. Incidenten worden ingedeeld in drie ernstniveaus:

### Ernstniveaus

- **Ernst 1 (Kritiek):** Direct lekken van plaintext PII of datalek; mislukte verificatie van de cryptografische handtekening op de auditketen. Vereist inperking binnen 1 uur.
- **Ernst 2 (Groot):** Service-uitval of volledige uitval van de zuiveringspijplijn. Vereist herstel binnen 4 uur.
- **Ernst 3 (Klein):** Niet-kritieke operationele waarschuwingen of kleine prestatieverslechtering (bijv. overschrijding van de latentiedrempel). Vereist onderzoek binnen 24 uur.

### Responsflow

1. **Detectie:** Waarschuwingen worden gegenereerd via Prometheus-statistieken of handmatige verificatie van de auditketen.
2. **Triage:** De SRE of de dienstdoende beveiligingsingenieur beoordeelt de waarschuwing en bepaalt de ernst.
3. **Inperking:** Bij kritieke incidenten kan de gateway onmiddellijk worden opgeschort (noodopschorting) of kunnen de sleutels van tenants worden ingetrokken.
4. **Herstel:** Ontwikkelaars isoleren de oorzaak, bouwen een patch en updaten de container.
5. **Nazorg:** Het normale verkeer wordt hersteld en de integriteit van de auditketen wordt geverifieerd.

---
*Dit document is een vertaling of bewerking van het Engelse origineel. In geval de vertaling afwijkt, is het Engelse origineel leidend.*
