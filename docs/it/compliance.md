> translated from en/compliance.md

# Preset di conformità

## Panoramica

AnonReq fornisce preset di conformità che impongono il rilevamento delle entità richiesto per specifici quadri normativi. Ciascun preset attiva un set di rilevatori richiesti dal regolamento corrispondente.

| Preset | Regolamento | Regione | Entità richieste |
|--------|-------------|--------|-------------------|
| `gdpr` | Regolamento generale sulla protezione dei dati | UE | E-mail, telefono, nome, indirizzo, IP, ID nazionale |
| `lgpd` | Lei Geral de Proteção de Dados | Brasile | CPF, CNPJ, e-mail, telefono, nome, indirizzo |
| `pdpa` | Personal Data Protection Act | Thailandia | E-mail, telefono, nome, indirizzo, ID nazionale |
| `popia` | Protection of Personal Information Act | Sudafrica | E-mail, telefono, nome, indirizzo, numero ID |
| `privacy-act` | Privacy Act 1988 | Australia | E-mail, telefono, nome, indirizzo, Medicare, TFN |
| `pipeda` | Personal Information Protection and Electronic Documents Act | Canada | E-mail, telefono, nome, indirizzo, SIN |

## Configurazione per preset

Ciascun preset definisce:

- **Tipi di entità obbligatori**: regole di rilevamento che non possono essere disabilitate mentre il preset è attivo.
- **Soglia di confidenza**: punteggio minimo di confidenza per il rilevamento basato su NER (predefinito per ciascun preset).
- **Locale**: locale associato per rilevatori specifici della lingua.

## Configurazione dei preset

Impostare il preset tramite l'intestazione `X-AnonReq-Compliance-Preset` sulle richieste:

```bash
curl -H "X-AnonReq-Compliance-Preset: gdpr"   -H "Authorization: Bearer $ANONREQ_API_KEY"   ...
```

Interrogare i preset disponibili e le relative configurazioni:

```bash
curl http://localhost:8000/v1/compliance/presets
```

## Preset multipli

Quando vengono specificati più preset (separati da virgole), la configurazione effettiva è un'unione di tutti i tipi di entità richiesti con la soglia di confidenza più elevata tra i preset selezionati.

## Validazione all'avvio

Se all'avvio viene configurato un preset di conformità, il gateway convalida che tutti i tipi di entità richiesti dal preset dispongano di rilevatori attivi. La configurazione che disabilita un tipo richiesto viene rifiutata all'avvio.

---
*Questo documento è una traduzione dell'originale in inglese. In caso di discrepanza, prevale la versione inglese.*
