> translated from en/compliance.md

# Compliance Presets

## Overzicht

AnonReq biedt compliance presets die verplichte entiteitsdetectie afdwingen voor specifieke regelgevingskaders. Elke preset activeert een bundel van recognizers die vereist zijn door de bijbehorende regelgeving.

| Preset | Regelgeving | Regio | Verplichte entiteiten |
|--------|------------|--------|-------------------|
| `gdpr` | Algemene verordening gegevensbescherming | EU | E-mail, telefoon, naam, adres, IP, nationaal ID |
| `lgpd` | Lei Geral de Proteção de Dados | Brazilië | CPF, CNPJ, e-mail, telefoon, naam, adres |
| `pdpa` | Personal Data Protection Act | Thailand | E-mail, telefoon, naam, adres, nationaal ID |
| `popia` | Protection of Personal Information Act | Zuid-Afrika | E-mail, telefoon, naam, adres, ID-nummer |
| `privacy-act` | Privacy Act 1988 | Australië | E-mail, telefoon, naam, adres, Medicare, TFN |
| `pipeda` | Personal Information Protection and Electronic Documents Act | Canada | E-mail, telefoon, naam, adres, SIN |

## Configuratie per preset

Elke preset definieert:

- **Verplichte entiteitstypen**: detectieregels die niet kunnen worden uitgeschakeld terwijl de preset actief is.
- **Betrouwbaarheidsdrempel**: minimale betrouwbaarheidsscore voor op NER gebaseerde detectie (standaard per preset).
- **Locale**: gekoppelde locale voor taalspecifieke recognizers.

## Presets configureren

Stel de preset in via de `X-AnonReq-Compliance-Preset`-header bij verzoeken:

```bash
curl -H "X-AnonReq-Compliance-Preset: gdpr"   -H "Authorization: Bearer $ANONREQ_API_KEY"   ...
```

Vraag beschikbare presets en hun configuraties op:

```bash
curl http://localhost:8000/v1/compliance/presets
```

## Meerdere presets

Wanneer meerdere presets worden gespecificeerd (door komma's gescheiden), is de resulterende configuratie een unie van alle verplichte entiteitstypen met de hoogste betrouwbaarheidsdrempel onder de geselecteerde presets.

## Validatie bij opstarten

Als er bij het opstarten een compliance preset is geconfigureerd, controleert de gateway of alle door de preset verplichte entiteitstypen actieve recognizers hebben. Een configuratie die een verplicht type uitschakelt, wordt bij het opstarten geweigerd.

---
*Dit document is een vertaling of bewerking van het Engelse origineel. In geval de vertaling afwijkt, is het Engelse origineel leidend.*
