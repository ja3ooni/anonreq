# Compliance (Deutschland)

*Kurzfassung für CISO, DSB und Legal. Die verbindliche Fassung ist [docs/compliance/germany-trust-pack.md](../compliance/germany-trust-pack.md) (Englisch).*

AnonReq ist ein **On-Prem-Proxy**, kein souveränes Modell-Hosting. Identifikatoren (Steuer-ID, Personalausweis, KVNR, DE-IBAN, Aktenzeichen, …) werden vor dem Modellaufruf tokenisiert. Rohwerte verlassen Ihre Umgebung nicht. API-Schlüssel werden irreversibel maskiert.

- Preset: `ANONREQ_ACTIVE_PRESETS=germany` und Header `X-AnonReq-Locale: de-DE`
- Audit-Export: nur Metadaten (Entitätstypen, Zeit, Modell) — keine Klartext-PII
- Demo: [docs/operations/germany-demo.md](../operations/germany-demo.md)
- Trust-Pack (DPA-Vorlage, TOMs, Datenfluss, AI Act, DORA): [germany-trust-pack.md](../compliance/germany-trust-pack.md)

**Nicht behauptet:** BSI C5, ISO 27001, „DSGVO-konformes Claude“. Behauptet wird: Identifikatoren erreichen den Anbieter nicht; Sie erhalten das Protokoll, das eine Aufsichtsbehörde anfordert.
