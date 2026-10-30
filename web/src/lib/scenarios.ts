import type { AnonymizePreviewResponse, PreviewEntity } from "@/lib/types";

export type ScenarioId = "bank" | "insurance" | "hr" | "energy" | "agent_sec" | "clean";

export type TaskPresetId = "as_is" | "summarize" | "draft_reply" | "extract_fields";

export interface BuyerScenario {
  id: ScenarioId;
  badge: string;
  recommendedLocale: string;
  sampleFilename: string;
  en: {
    label: string;
    persona: string;
    pain: string;
    value: string;
    buyerLine: string;
    prompt: string;
  };
  de: {
    label: string;
    persona: string;
    pain: string;
    value: string;
    buyerLine: string;
    prompt: string;
  };
}

export const BUYER_SCENARIOS: BuyerScenario[] = [
  {
    id: "bank",
    badge: "FinTech / Banking",
    recommendedLocale: "de-DE",
    sampleFilename: "frankfurt-sepa-ticket",
    en: {
      label: "1. Bank Support Ticket (IBAN + Tax ID)",
      persona: "Frankfurt Bank Ops Lead / CISO",
      pain: "[P1/P2/P6] Agents paste SEPA tickets with DE-IBAN & Steuer-ID into cloud AI — violating GDPR Art. 44 (3rd-country transfer), Art. 5(1)(c), DORA Art. 28 & BaFin VAIT.",
      value: "→ Solves [P1/P2/P6]: GDPR Art. 32 & 25 edge tokenization (MOD-97 + Presidio); Col 03 proves Grok only sees tokens; Col 04 restores reply + Art. 30 DPO CSV.",
      buyerLine: "GDPR Art. 44 & DORA Art. 28: IBAN & Steuer-ID never hit the model.",
      prompt:
        "Payment Dispute Ticket #4920 — Customer: Jörg Müller (joerg.mueller@nordbank.example, +49 170 1234567), Hauptstraße 12, Frankfurt. Please verify IBAN DE89 3704 0044 0532 0130 00 and German tax number (Steuer-Id) 86095742719 for the chargeback scheduled on 14.03.2026, and draft a short confirmation reply to the customer.",
    },
    de: {
      label: "1. Bank-Supportticket (IBAN + Steuer-ID)",
      persona: "Bank-Betriebsleitung / CISO (Frankfurt)",
      pain: "[P1/P2/P6] SEPA-Tickets mit DE-IBAN & Steuer-ID im KI-Chat verletzen DSGVO Art. 44 (Drittlandtransfer), Art. 5(1)(c), DORA Art. 28 & BaFin VAIT.",
      value: "→ Löst [P1/P2/P6]: DSGVO Art. 32 & 25 Tokenisierung am Gateway; Spalte 03 beweist Token-Antwort von Grok; Spalte 04 restauriert + Art. 30 DSB-CSV.",
      buyerLine: "DSGVO Art. 44 & DORA Art. 28: Kein Klartext-IBAN verlässt die Bank.",
      prompt:
        "Zahlungsreklamation Ticket #4920 — Kunde: Jörg Müller (joerg.mueller@nordbank.example, +49 170 1234567), Hauptstraße 12, 60311 Frankfurt. Bitte IBAN DE89 3704 0044 0532 0130 00 sowie Steuer-Id 86095742719 für die Rückbuchung am 14.03.2026 prüfen und eine kurze Bestätigungsantwort an den Kunden formulieren.",
    },
  },
  {
    id: "insurance",
    badge: "InsurTech / Claims",
    recommendedLocale: "de-DE",
    sampleFilename: "kfz-schadensmeldung",
    en: {
      label: "2. Insurance Claim (KVNR + Ausweis)",
      persona: "Claims Director / DPO (Datenschutzbeauftragter)",
      pain: "[P1/P3/P4] Claims contain KVNR (GDPR Art. 9 health ID), Personalausweis & Aktenzeichen — blocked under GDPR Art. 9, Art. 44 & EU AI Act Art. 12/14.",
      value: "→ Solves [P1/P3/P4]: GDPR Art. 9 & 32 pseudonymisation in ephemeral Valkey (save ''); DPO exports Art. 30 / AI Act Art. 12 metadata-only CSV.",
      buyerLine: "GDPR Art. 9 & Art. 30: DPO audit CSV logs entity types only — never raw values.",
      prompt:
        "Schadensmeldung — Kfz, München\nVersicherte: Anna Schmidt\nKVNR: A123456780\nPersonalausweis: L01X00T471\nIBAN: DE89370400440532013000\nAktenzeichen: Az. 14 C 123/24\nGesellschaft: HRB 12345\nKontakt: anna.schmidt@example.de, +49 89 12345678\nSachverhalt: Auffahrunfall am 12.03.2026 in der Leopoldstraße 44. Bitte Deckungszusage prüfen und nächste Schritte zusammenfassen.",
    },
    de: {
      label: "2. Versicherungsschaden (KVNR + Ausweis)",
      persona: "Schadensleitung / Datenschutzbeauftragte (DPO)",
      pain: "[P1/P3/P4] Schadensmeldungen mit KVNR (DSGVO Art. 9 Gesundheitsdaten) & Personalausweis verletzen DSGVO Art. 9, Art. 44 & EU AI Act Art. 12/14.",
      value: "→ Löst [P1/P3/P4]: DSGVO Art. 9 & 32 Pseudonymisierung im flüchtigen Valkey-Cache; DSB exportiert Art. 30 / AI Act Art. 12 Metadaten-CSV.",
      buyerLine: "DSGVO Art. 9 & 30: DPO-CSV beweist Maskierung ohne Rohdaten im Log.",
      prompt:
        "Schadensmeldung — Kfz, München\nVersicherte: Anna Schmidt\nKVNR: A123456780\nPersonalausweis: L01X00T471\nIBAN: DE89370400440532013000\nAktenzeichen: Az. 14 C 123/24\nGesellschaft: HRB 12345\nKontakt: anna.schmidt@example.de, +49 89 12345678\nSachverhalt: Auffahrunfall am 12.03.2026 in der Leopoldstraße 44. Bitte Deckungszusage prüfen und nächste Schritte zusammenfassen.",
    },
  },
  {
    id: "hr",
    badge: "HR / Betriebsrat",
    recommendedLocale: "de-DE",
    sampleFilename: "kandidaten-cv-frankfurt",
    en: {
      label: "3. HR / Works-Council CV Screening",
      persona: "Head of People / Works Council (Betriebsrat)",
      pain: "[P2/P3/P5] Uploading candidate CVs with DOB, address & Steuer-ID violates German Works Council co-determination (BetrVG § 87 Abs. 1 Nr. 6), BDSG § 26 & EU AI Act Art. 14.",
      value: "→ Solves [P2/P3/P5]: BetrVG § 87 & GDPR Art. 25 blind screening strips name, DOB, address & Steuer-ID pre-LLM; stdout JSON logs redact all prompt values.",
      buyerLine: "BetrVG § 87 & BDSG § 26: Works-council-safe (Betriebsrat-konform) recruiting AI.",
      prompt:
        "Candidate Resume Excerpt — Katharina Weber (geb. 14.05.1991), Hauptstraße 19, 60325 Frankfurt. Contact: katharina.weber@example.de, +49 151 98765432. Payroll & Tax onboarding file: Steuer-Id 41928374651, Payout IBAN DE89 3704 0044 0532 0130 00.\nExperience: 7 years Principal Cloud Security Engineer (Kubernetes, eBPF, Cloud Governance). Summarize candidate strengths for the Senior Security Architect role.",
    },
    de: {
      label: "3. HR / Bewerbungs-Screening (Betriebsrat)",
      persona: "HR-Leitung / Betriebsrat",
      pain: "[P2/P3/P5] CV-Uploads mit Geburtsdatum, Anschrift & Steuer-ID verletzen Mitbestimmung (BetrVG § 87 Abs. 1 Nr. 6), BDSG § 26 & EU AI Act Art. 14.",
      value: "→ Löst [P2/P3/P5]: BetrVG § 87 & DSGVO Art. 25 Maskierung vor dem Modellaufruf; stdout-JSON-Logs schwärzen alle Prompt-Werte.",
      buyerLine: "BetrVG § 87 & BDSG § 26: Betriebsrat-konformes CV-Screening ohne Klardaten.",
      prompt:
        "Lebenslauf-Auszug — Katharina Weber (geb. 14.05.1991), Hauptstraße 19, 60325 Frankfurt. Kontakt: katharina.weber@example.de, +49 151 98765432. Lohnsteuer-Merkmal: Steuer-Id 41928374651, Gehaltskonto IBAN DE89 3704 0044 0532 0130 00.\nErfahrung: 7 Jahre Principal Cloud Security Engineer (Kubernetes, eBPF, Cloud-Sicherheit). Bitte fachliche Eignung für die Stelle Senior Security Architect zusammenfassen.",
    },
  },
  {
    id: "energy",
    badge: "KRITIS / Energy Ops",
    recommendedLocale: "de-DE",
    sampleFilename: "kritis-grid-incident",
    en: {
      label: "4. Energy & Grid Ops (SITE_ID + Meter)",
      persona: "VP Grid Operations / KRITIS Security",
      pain: "[P6/P7] Dispatch logs expose critical substation Site IDs (UW-NORD-0417), meter accounts & engineer phones — violating NIS2 Art. 21/24, BSIG KRITIS & GDPR Art. 32.",
      value: "→ Solves [P6/P7]: NIS2 Art. 21/24 & DORA Art. 9 safeguard tokenizes KRITIS SITE_IDs and meter accounts before AI incident correlation with GlassFlow Tares.",
      buyerLine: "NIS2 Art. 21 & BSIG KRITIS: Incident triage without exposing substation IDs.",
      prompt:
        "Grid Dispatch Log — Substation UW-NORD-0417 (Stuttgart, Industriering 8). Affected commercial meter: Kundenkonto 4401-88921-03. On-call lead: Markus Hoffmann (m.hoffmann@stadtwerke.example, +49 711 4455667) reported voltage sag on 28.10.2026. Draft a 3-step operator handover summary.",
    },
    de: {
      label: "4. Energie / KRITIS-Betrieb (SITE_ID + Zähler)",
      persona: "Netzleitstelle / KRITIS-Informationssicherheit",
      pain: "[P6/P7] Störprotokolle mit Umspannwerk-IDs (UW-NORD-0417) & Rufbereitschaft verletzen NIS2 Art. 21/24, BSIG-KRITIS & DSGVO Art. 32.",
      value: "→ Löst [P6/P7]: NIS2 Art. 21/24 & DORA Art. 9 Schutz maskiert Anlagen-IDs (SITE_ID), Zählerkonten und Technikerdaten vor der KI-Analyse.",
      buyerLine: "NIS2 Art. 21 & BSIG-KRITIS: Runbooks auswerten ohne Anlagen-IDs preiszugeben.",
      prompt:
        "Netzleitstellen-Störmeldung — Umspannwerk UW-NORD-0417 (Stuttgart, Industriering 8). Betroffener Großkunde: Kundenkonto 4401-88921-03. Bereitschaftsleiter Markus Hoffmann (m.hoffmann@stadtwerke.example, +49 711 4455667) meldet Spannungseinbruch am 28.10.2026. Bitte Übergabeprotokoll in 3 Punkten erstellen.",
    },
  },
  {
    id: "agent_sec",
    badge: "Agent DLP / Secrets",
    recommendedLocale: "de-DE",
    sampleFilename: "agent-trace-leaked-key",
    en: {
      label: "5. Agent Tool Call + Leaked API Key",
      persona: "AI Platform Lead / SecOps",
      pain: "[P4/P7/P8] Agents leak production API keys (sk-...) alongside customer PII — violating NIS2 Art. 21/22 supply-chain security, EU AI Act Art. 12/14 & GDPR Art. 32.",
      value: "→ Solves [P4/P7/P8]: Customer PII is Reversible (restored in Col 04), while API_KEY is Permanent Mask (reversible: false) + EU AI Act Art. 12 zero-PII OTEL trace.",
      buyerLine: "NIS2 Art. 21 & GDPR Art. 32: PII restores for the user; API_KEY stays masked forever.",
      prompt:
        "Debug agent webhook failure for customer Thomas Becker (thomas.becker@example.de, IBAN DE89 3704 0044 0532 0130 00 in Berlin). Outbound header trace contained bearer secret sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz123456. Explain how to rotate the credential and notify the customer.",
    },
    de: {
      label: "5. Agent-Log mit geleaktem API-Key",
      persona: "AI-Platform-Lead / SecOps",
      pain: "[P4/P7/P8] Agenten senden produktive API-Keys (sk-...) samt Kundendaten an LLMs — Verstoß gegen NIS2 Art. 21/22, EU AI Act Art. 12/14 & DSGVO Art. 32.",
      value: "→ Löst [P4/P7/P8]: Kunden-PII wird in Spalte 04 wiederhergestellt, aber API_KEY bleibt dauerhaft maskiert (reversible: false) + EU AI Act Art. 12 OTLP-Trace.",
      buyerLine: "NIS2 Art. 21 & DSGVO Art. 32: PII wird restauriert — API-Keys bleiben für immer maskiert.",
      prompt:
        "Analysiere den Webhook-Fehler für Kunde Thomas Becker (thomas.becker@example.de, IBAN DE89 3704 0044 0532 0130 00 in Berlin). Im Debug-Header stand versehentlich der Schlüssel sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz123456. Beschreibe kurz die Schlüsselrotation und eine Kundeninfo.",
    },
  },
  {
    id: "clean",
    badge: "Clean Baseline",
    recommendedLocale: "de-DE",
    sampleFilename: "clean-architecture-note",
    en: {
      label: "6. Clean Prompt (0 PII Baseline)",
      persona: "Security Architect",
      pain: "Need to verify that non-sensitive prompts pass through with zero false-positive distortion.",
      value: "0 entities detected → classification PUBLIC → passes cleanly through the gateway.",
      buyerLine: "Clean traffic flows untouched with full audit visibility.",
      prompt: "Explain in three sentences how a gateway that fails closed on detector outage differs from a standard reverse proxy.",
    },
    de: {
      label: "6. Sauberer Prompt (0-PII-Vergleich)",
      persona: "Sicherheitsarchitekt",
      pain: "Nachweis, dass unkritische Anfragen ohne unnötige Veränderung durchlaufen.",
      value: "0 Entitäten erkannt → Klassifizierung PUBLIC → unveränderter Durchlauf mit Audit-Nachweis.",
      buyerLine: "Sauberer Traffic läuft ohne Reibungsverlust durch.",
      prompt: "Erkläre in drei Sätzen, worin sich ein Gateway, das bei Fehlern blockiert (Fail-Closed), von einem normalen Proxy unterscheidet.",
    },
  },
];

export const TASK_PRESETS: Record<TaskPresetId, { en: { label: string; prefix: string }; de: { label: string; prefix: string } }> = {
  as_is: {
    en: { label: "Send document / prompt as-is", prefix: "" },
    de: { label: "Dokument / Prompt unverändert senden", prefix: "" },
  },
  summarize: {
    en: {
      label: "Task: Executive Summary & Action Items",
      prefix: "Analyze the following document and provide a concise 3-bullet summary with recommended next steps:\n\n",
    },
    de: {
      label: "Aufgabe: Management-Zusammenfassung & Maßnahmen",
      prefix: "Analysiere das folgende Dokument und erstelle eine prägnante Zusammenfassung in 3 Stichpunkten inklusive empfohlener Maßnahmen:\n\n",
    },
  },
  draft_reply: {
    en: {
      label: "Task: Draft Customer / Stakeholder Reply",
      prefix: "Based on the following case file, draft a polite, compliant response to the customer confirming next steps:\n\n",
    },
    de: {
      label: "Aufgabe: Antwort an Kunden / Versicherte entwerfen",
      prefix: "Entwirf auf Basis der folgenden Akte eine höfliche, verbindliche Antwort an die betroffene Person mit den nächsten Schritten:\n\n",
    },
  },
  extract_fields: {
    en: {
      label: "Task: Extract Structured Case Checklist",
      prefix: "Extract the key case identifiers, dates, parties, and required follow-ups from this document as a structured list:\n\n",
    },
    de: {
      label: "Aufgabe: Strukturierte Fall-Checkliste extrahieren",
      prefix: "Extrahiere die wichtigsten Fallkennungen, Daten, Beteiligten und offenen Punkte aus diesem Dokument als strukturierte Liste:\n\n",
    },
  },
};

export type VerdictState = "clean" | "governed" | "credential_risk" | "fail_closed";

export interface EntityGroupSummary {
  entityType: string;
  count: number;
  tokens: string[];
  reversible: boolean;
}

export interface ComplianceVerdict {
  state: VerdictState;
  okForCleartextAi: boolean;
  okViaAnonReq: boolean;
  classification: string;
  highestEntity: string;
  totalEntities: number;
  nonReversibleCount: number;
  groups: EntityGroupSummary[];
}

export function evaluateComplianceVerdict(
  preview: AnonymizePreviewResponse | null,
  errorStatus?: number | null,
): ComplianceVerdict {
  if (!preview && errorStatus && errorStatus >= 500) {
    return {
      state: "fail_closed",
      okForCleartextAi: false,
      okViaAnonReq: false,
      classification: "BLOCKED",
      highestEntity: "",
      totalEntities: 0,
      nonReversibleCount: 0,
      groups: [],
    };
  }

  const entities: PreviewEntity[] = preview?.entities ?? [];
  const groupMap = new Map<string, EntityGroupSummary>();
  let nonReversibleCount = 0;

  for (const entity of entities) {
    const reversible = entity.entity_type !== "API_KEY" && entity.entity_type !== "SECRET";
    if (!reversible) {
      nonReversibleCount += 1;
    }
    const existing = groupMap.get(entity.entity_type);
    if (existing) {
      existing.count += 1;
      if (!existing.tokens.includes(entity.token)) {
        existing.tokens.push(entity.token);
      }
    } else {
      groupMap.set(entity.entity_type, {
        entityType: entity.entity_type,
        count: 1,
        tokens: [entity.token],
        reversible,
      });
    }
  }

  const groups = [...groupMap.values()].sort((a, b) => b.count - a.count || a.entityType.localeCompare(b.entityType));
  const classification = preview?.classification || (entities.length > 0 ? "CONFIDENTIAL" : "PUBLIC");
  const highestEntity = preview?.highest_entity || groups[0]?.entityType || "";

  if (entities.length === 0) {
    return {
      state: "clean",
      okForCleartextAi: true,
      okViaAnonReq: true,
      classification,
      highestEntity,
      totalEntities: 0,
      nonReversibleCount: 0,
      groups,
    };
  }

  if (nonReversibleCount > 0) {
    return {
      state: "credential_risk",
      okForCleartextAi: false,
      okViaAnonReq: true,
      classification,
      highestEntity,
      totalEntities: entities.length,
      nonReversibleCount,
      groups,
    };
  }

  return {
    state: "governed",
    okForCleartextAi: false,
    okViaAnonReq: true,
    classification,
    highestEntity,
    totalEntities: entities.length,
    nonReversibleCount: 0,
    groups,
  };
}
