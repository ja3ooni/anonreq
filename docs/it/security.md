> translated from en/security.md

# Politica di sicurezza AnonReq

Questo documento descrive la postura di sicurezza, le garanzie sul trattamento dei dati e le procedure di risposta agli incidenti per il gateway AnonReq.

## Postura di sicurezza

AnonReq si basa su un'architettura Zero-Trust. Assumiamo che tutti gli endpoint del modello esterno e le reti pubbliche non siano attendibili e applichiamo rigidi limiti di sicurezza:

- **Privilegio minimo:** Tutti i percorsi amministrativi e le modifiche alla configurazione richiedono un'autorizzazione convalidata tramite chiavi API ad alta entropia.
- **Impostazioni predefinite fail-secure:** Tutti i parametri di configurazione sono impostati per impostazione predefinita sullo stato più restrittivo (ad esempio, portale Trust Center disabilitato, preset di conformità richiesti, azioni di blocco predefinite).
- **Isolamento:** I dati dei tenant, i criteri configurati e le cache di sessione sono isolati all'interno della memoria Valkey tramite spazi dei nomi prefissati.

## Garanzie di anonymisation e trattamento dei dati

AnonReq garantisce che le informazioni sensibili in chiaro non vengano mai esposte alle reti esterne:

1. **Protezione dei dati in uscita:** Il gateway intercetta tutte le richieste di testo, oggetti JSON e moduli multipart. Le corrispondenze in testo chiaro sono tokenizzate con variabili (es. `[EMAIL_N]`) prima del transito sulla rete.
2. **Modello di memoria effimera:** Le mappature dei token sono memorizzate esclusivamente nella cache Valkey/Redis. Sono soggette a rigidi criteri TTL e rimosse subito dopo la risposta.
3. **Nessun PII nei log o nella telemetria:** I log di controllo e le metriche di Prometheus contengono solo metadati. I dati in chiaro e i valori dei token non vengono mai memorizzati nella cache persistente o scritti su stdout.

## Protocollo di risposta agli incidenti

AnonReq mantiene un flusso di lavoro attivo di risposta agli incidenti per anomalie operative o di sanitizzazione. Gli incidenti sono classificati in tre livelli di gravità:

### Livelli di gravità

- **Gravità 1 (Critica):** Perdita di PII in chiaro o violazione di dati; errore di firma dell'ancora sulla catena di controllo. Richiede il contenimento entro 1 ora.
- **Gravità 2 (Maggiore):** Interruzione del servizio o degradazione completa della pipeline di sanitizzazione. Richiede la correzione entro 4 ore.
- **Gravità 3 (Minore):** Avvisi operativi non critici o lieve calo delle prestazioni (es. superamento della soglia di latenza). Richiede un'indagine entro 24 ore.

### Flusso di risposta

1. **Rilevamento:** Gli avvisi vengono attivati tramite metriche Prometheus o convalida manuale della catena di controllo.
2. **Triage:** L'ingegnere di guardia valuta lo stato dell'incidente e assegna la gravità.
3. **Contenimento:** Per gli incidenti critici, il gateway può essere sospeso (sospensione di emergenza) o le chiavi dei tenant sospese.
4. **Risoluzione:** I componenti difettosi vengono corretti dal team di sviluppo e viene rilasciato un aggiornamento.
5. **Ripristino:** Viene ripristinato il traffico e convalidata l'integrità della catena di controllo.

---
*Questo documento è una traduzione dell'originale in inglese. In caso di discrepanza, prevale la versione inglese.*
