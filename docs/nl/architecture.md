> translated from en/architecture.md

# AnonReq Gateway-architectuur

Dit document biedt een samenvatting in proza van de AnonReq gateway-architectuur. Het beschrijft de componententopologie, de levenscyclus van verzoeken en de belangrijkste beveiligingsinvarianten.

## Systeemoverzicht

AnonReq is een zelf-gehoste AI-beveiligings- en anonymisation-gateway die is ontworpen om plaats te nemen tussen enterprise-applicaties en externe of lokale LLM (Large Language Model) providers. Door te fungeren als een onderscheppende proxy, zorgt het ervoor dat gevoelige gegevens (zoals PII, PHI, PCI of bedrijfsonderdelen) worden geclassificeerd, getokeniseerd en gezuiverd voordat ze de vertrouwensgrens van het bedrijfsnetwerk overschrijden.

```
┌─────────────────┐       ┌─────────────────┐       ┌───────────────────┐
│                 │       │                 │       │                   │
│   Enterprise    │──────>│ AnonReq Gateway │──────>│   LLM Providers   │
│   Applicatie    │<──────│ (Zelf-gehost)   │<──────│ (OpenAI, Gemini)  │
│                 │       │                 │       │                   │
└─────────────────┘       └─────────────────┘       └───────────────────┘
```

## Levenscyclus van verzoeken

Elk verzoek dat via AnonReq naar een externe provider wordt verzonden, doorloopt een gestructureerde verwerkingspijplijn:

1. **Inbound en content-dispatching:** Het verzoek komt binnen bij de gateway. De dispatcher controleert de request-headers en stuurt de payload naar de juiste analyzer (Text, JSON of Multipart).
2. **Classificatie:** De classificatie-engine vergelijkt het verzoek met de geconfigureerde beveiligingsniveaus. Als een payload beperkte gegevens bevat die niet mogen doorgaan, blokkeert de engine het verzoek vroegtijdig of bepaalt of het lokale routering, anonymisation of directe pass-through nodig heeft.
3. **Detectie:** De detectie-engine combineert regex/checksum-recognizers, Presidio-clientintegratie en context-boosting-algoritmen om gevoelige entiteiten te lokaliseren (bijv. e-mailadressen, telefoonnummers, creditcardnummers).
4. **Tokenisatie:** Gedetecteerde gevoelige waarden worden geëxtraheerd en vervangen door anonieme tokens (bijv. `[EMAIL_0]`, `[PERSON_1]`). De unieke mappings worden opgeslagen in de Valkey/Redis Cache Manager onder een sessie-gebonden levenscyclus.
5. **Provider-adapter:** Het gezuiverde en getokeniseerde verzoek wordt door de provider-adapter vertaald naar het doel-LLM API-formaat (bijv. OpenAI-compatibel converteren naar Anthropic/Gemini) en doorgestuurd.
6. **LLM-respons:** Het externe LLM retourneert zijn antwoord met getokeniseerde referenties.
7. **Herstel (Restoration):** De herstel-engine leest de mappings uit de Cache Manager en vervangt de tokens door hun oorspronkelijke waarden in de respons (ondersteunt SSE-streaming).
8. **Outbound:** De herstelde respons wordt teruggestuurd naar de client-applicatie.

## Kerncomponenten

- **Proxy/Gateway:** FastAPI-applicatie die een ASGI-netwerklus uitvoert.
- **Classificatie-engine:** PDP (Policy Decision Point) en PEP (Policy Enforcement Point) die governance- en risicobeleid evalueren.
- **Detectie-engine:** Multi-locale entiteitsscanner met regex-recognizers en Microsoft Presidio.
- **Tokenisatie- en herstel-engines:** Code verantwoordelijk voor tokensubstitutie en -vervanging.
- **Cache Manager:** Tijdelijke Valkey/Redis-instantie die sessie-mappings in het geheugen bewaart onder een strikt TTL-contract.
- **Provider-adapters:** Compatibiliteitslaag die API-oproepen direct vertaalt.

## Belangrijkste beveiligingsinvarianten

- **Zero-Exposure Invariant:** Onbewerkte PII mag onder geen enkele omstandigheid de grens van het bedrijfsnetwerk naar externe providers overschrijden.
- **Fail-Secure gedrag:** Elke uitzondering, time-out, cache-fout of classificatie-ambiguïteit moet uitgaand verkeer onmiddellijk blokkeren en een HTTP 503 of 403 retourneren.
- **Geen PII in logs of metrics:** Audit trails, systeemlogboeken en Prometheus-statistieken bevatten alleen metadata. Er worden geen onbewerkte PII-waarden of tokensleutels gelogd.
- **Vluchtige opslag:** Mappings worden alleen opgeslagen in cachegeheugen met strikte TTL-configuraties, wat zorgt voor onmiddellijke verwijdering na de transactie.

---
*Dit document is een vertaling of bewerking van het Engelse origineel. In geval de vertaling afwijkt, is het Engelse origineel leidend.*
