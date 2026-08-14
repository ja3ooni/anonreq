# LinkedIn posts — copy the 6 beats, not anyone else’s deals

Cadence: **4–5 posts/week**, each post in **German and English** (same thread or back-to-back). Named **place + vertical**, no fake logos, no “we deployed at Bank X.”

Beats: (1) place + vertical (2) shadow AI or legal freeze (3) regulator fear (4) middleware not a new model (5) speed (6) proof artifact.

## Post 1 — Ban vs govern (highest-converting shape)

**DE**
In Frankfurt sitzen Banken, die Claude verbieten — und dieselben Banken, in denen Steuer-IDs trotzdem im privaten Chat landen.

Verbote erzeugen Schatten-KI. Governance erzeugt ein Protokoll.

Wir setzen keinen neuen Modellanbieter. Ein Proxy vor dem bestehenden Key: Identifikatoren raus, Tokens rein, Audit-CSV für den DSB.

Wenn Legal „Nein“ sagt, ist die Alternative selten „kein GPT“. Die Alternative ist „GPT ohne Ausweisnummern auf dem US-Server“.

**EN**
Frankfurt banks that ban Claude still have Steuer-IDs in personal chats.

Bans create shadow AI. Governance creates an audit trail.

Not a new model. A proxy in front of the key you already bought: identifiers out, tokens in, CSV for the DPO.

Legal’s “no” is rarely “no GPT.” It is “no ID numbers on a server we do not control.”

## Post 2 — Munich insurance

**DE**
München, Schadenabteilung: KVNR und Personalausweis stehen im Ticket. Jemand fügt den Text in ChatGPT ein, weil die Zusammenfassung sonst zwei Stunden dauert. Legal stoppt den Piloten.

Der Haken ist nicht das Modell. Der Haken ist Art. 44 plus das, was die DSB als Nachweis sehen will.

Middleware: Ticket → Proxy → Modell. KVNR kommt nicht mit. Die Zusammenfassung schon. Export in Minuten, nicht nach Quartalsende.

**EN**
Munich claims: KVNR and ID-card numbers live in the ticket. Someone pastes the ticket into ChatGPT. Legal kills the pilot.

The blocker is not the model. It is Art. 44 plus the evidence the DPO will be asked for.

Ticket → proxy → model. KVNR stays. The summary comes back. Export in minutes.

## Post 3 — Berlin public sector

**DE**
Berliner Bürgeramt, Schreiben mit steuerlicher Identifikationsnummer. Ein KI-Pilot für Antwortentwürfe. Datensicherheit sagt: nicht in die Cloud, solange die Nummer im Prompt steht.

Wir ersetzen nicht GovGPT. Wir sitzen davor. Az. und Steuer-ID werden Tokens. Der Entwurf kommt zurück. Kein Trust-Center-Marketing, ein Helm-Chart an einem Tag.

**EN**
Berlin Bürgeramt letter, tax ID in the body. A draft-reply pilot. Security: not in the cloud while that number is in the prompt.

We do not replace a government model. We sit in front. File numbers and tax IDs become tokens. The draft comes back. A Helm chart in a day, not a portal.

## Post 4 — Hamburg logistics / IBAN

**DE**
Hamburg, Disposition: DE-IBAN in jedem zweiten Ticket. Das Modell soll den Disput zusammenfassen. Die IBAN muss nicht mitreisen.

MOD-97 kennt der Proxy. Der Anbieter sieht `[IBAN_DE_0]`. Ops sieht die restaurierte Antwort. API-Keys im Runbook werden nicht restauriert — absichtlich.

**EN**
Hamburg ops: a DE-IBAN in every other ticket. The model should summarise the dispute. The IBAN should not travel.

The proxy knows MOD-97. The vendor sees `[IBAN_DE_0]`. Ops sees the restored answer. API keys in the runbook stay masked on purpose.

## Post 5 — Speed without the four-day lie

**DE**
Anbieter, die „zwei Monate Rollout“ sagen, verkaufen Plattform. Ein CISO in NRW braucht: Compose oder Helm, den eigenen Key, einen Ticket-Ausschnitt, eine CSV ohne Klartext.

Das ist der ehrliche erste Tag. Air-Gap-Bundle und Entra-ID kommen nach dem unterschriebenen PoC, nicht davor.

**EN**
Vendors quoting two-month rollouts are selling a platform. A CISO in NRW needs Compose or Helm, their key, a ticket sample, a CSV with no raw PII.

That is the honest day one. Air-gap bundles and Entra ID come after a signed PoC.

## Rules

- Never name a bank, insurer, or ministry as a customer until they agree to a case study.
- Never claim BSI C5, ISO 27001, or “GDPR-compliant Claude.”
- Controversial-but-true (ban vs govern) first; product screenshots later.
- Rotate city + vertical; keep the six beats.
