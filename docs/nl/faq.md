> translated from en/faq.md

# Veelgestelde vragen

## Wat gebeurt er als de PII-detectie mislukt?

De gateway is fail-secure. Als er detectie-, cache- of provider-timeoutfouten optreden, retourneert het verzoek HTTP 5xx en worden er geen gegevens doorgestuurd. Zie de fail-secure architectuur in de project-README voor details.

## Worden mijn gegevens ergens opgeslagen?

Nee. Alle PII-naar-token mappings worden opgeslagen in Valkey zonder persistentie (`save ""`). Mappings worden verwijderd nadat het antwoord is verzonden. Logboeken bevatten alleen metadata, geen onbewerkte PII-waarden.

## Welke LLM-providers worden ondersteund?

OpenAI, Azure OpenAI, Anthropic (Claude), Google Gemini en Ollama (lokale modellen). De gateway vertaalt het OpenAI-compatibele verzoeksformaat naar het eigen protocol van elke provider.

## Hoe werkt streaming?

De gateway gebruikt een Tail_Buffer FSM om tokens te verwerken die zijn gesplitst over SSE-chunkgrenzen. Tokens worden in realtime hersteld naarmate chunks binnenkomen. De respons is byte-voor-byte identiek aan de niet-streamingmodus.

## Wat is de token-indeling?

Gedetecteerde PII wordt vervangen door `[TYPE_N]` tijdelijke aanduidingen, waarbij `TYPE` het entiteitstype is (bijvoorbeeld `EMAIL`, `PHONE`) en `N` een unieke index is. Token-matching is hoofdletterongevoelig en haken zijn optioneel tijdens het herstellen.

## Hoe worden locales afgehandeld?

Stel de `X-AnonReq-Locale`-header in om taalspecifieke detectie te activeren. Meerdere locales kunnen worden gecombineerd (door komma's gescheiden). Niet-ondersteunde locales retourneren HTTP 400.

## Kan ik aangepaste detectiepatronen toevoegen?

Ja, aangepaste regex-recognizers kunnen worden toegevoegd via een YAML-configuratiebestand en warm worden herladen zonder opnieuw op te starten. Zie de configuratiedocumentatie voor de regelindeling.

## Hoe kan ik bijdragen?

Bijdragen zijn welkom onder de Apache 2.0-licentie. Zie de bijdragershandleiding in de repository voor pull request-richtlijnen en instructies voor de ontwikkelingsomgeving.

---
*Dit document is een vertaling of bewerking van het Engelse origineel. In geval de vertaling afwijkt, is het Engelse origineel leidend.*
