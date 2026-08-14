# AnonReq — eine Seite für CISO / DSB / Legal

**Was es ist:** Ein Proxy vor Claude, ChatGPT oder Gemini. Ihre Keys, Ihr Cluster. Kein neues Modell, keine 140-Modelle-Cloud.

**Was Legal „Nein“ sagt:** Mitarbeitende kleben Steuer-ID, KVNR, IBAN in den privaten Chat. Art. 44 (Drittland), AI-Act-Protokoll, DORA-ICT, Betriebsrat.

**Was der Proxy ändert:** Dieselben Prompts, aber Identifikatoren sind Tokens, bevor der Anbieter sie sieht. Die Antwort kommt restauriert zurück. API-Keys bleiben maskiert.

**Beweis in einem Tag:** Helm oder Docker Compose, `X-AnonReq-Locale: de-DE`, Preset `germany`. CSV-Export: wer, wann, welches Modell, welche *Entitätstypen* — keine Klartext-PII.

**Formulierung:** Nicht „DSGVO-konformes Claude“. Sondern: „Identifikatoren erreichen den Anbieter nicht; das Protokoll kann die Aufsicht anfordern.“

**Nicht behauptet:** BSI C5, ISO 27001, Air-Gap in vier Tagen, Hosting der Modelle.

Details: [germany-trust-pack.md](germany-trust-pack.md) · Demo: [germany-demo.md](../operations/germany-demo.md)
