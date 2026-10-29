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
      pain: "Support agents paste SEPA dispute tickets with DE-IBAN and Steuer-ID into ChatGPT/Grok. Compliance blocks shadow AI.",
      value: "DE-IBAN, Steuer-ID, and customer identity are tokenized at the edge; agent still gets a full restored draft reply.",
      buyerLine: "IBAN & Steuer-ID never hit the model.",
      prompt:
        "Payment Dispute Ticket #4920 — Customer: Jörg Müller (joerg.mueller@nordbank.example, +49 170 1234567), Hauptstraße 12, Frankfurt. Please verify IBAN DE89 3704 0044 0532 0130 00 and German tax number (Steuer-Id) 86095742719 for the chargeback scheduled on 14.03.2026, and draft a short confirmation reply to the customer.",
    },
    de: {
      label: "1. Bank-Supportticket (IBAN + Steuer-ID)",
      persona: "Bank-Betriebsleitung / CISO (Frankfurt)",
      pain: "Support-Teams kopieren SEPA-Tickets mit IBAN und Steuer-ID in KI-Chats. Compliance blockiert Shadow-AI.",
      value: "DE-IBAN, Steuer-ID und Kundendaten werden am Gateway tokenisiert; die Antwort wird für die Sachbearbeitung wiederhergestellt.",
      buyerLine: "Kein Klartext-IBAN verlässt die Bankgrenze.",
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
      pain: "Claims documents contain health insurance IDs (KVNR), Personalausweis numbers, and court case references (Aktenzeichen).",
      value: "Automated claim triage via Grok while KVNR, Ausweis, and IBAN stay inside the boundary; DPO exports metadata-only CSV.",
      buyerLine: "DPO audit CSV logs entity types only — never raw values.",
      prompt:
        "Schadensmeldung — Kfz, München\nVersicherte: Anna Schmidt\nKVNR: A123456780\nPersonalausweis: L01X00T471\nIBAN: DE89370400440532013000\nAktenzeichen: Az. 14 C 123/24\nGesellschaft: HRB 12345\nKontakt: anna.schmidt@example.de, +49 89 12345678\nSachverhalt: Auffahrunfall am 12.03.2026 in der Leopoldstraße 44. Bitte Deckungszusage prüfen und nächste Schritte zusammenfassen.",
    },
    de: {
      label: "2. Versicherungsschaden (KVNR + Ausweis)",
      persona: "Schadensleitung / Datenschutzbeauftragte (DPO)",
      pain: "Schadensmeldungen enthalten KVNR, Personalausweisnummern, IBAN und gerichtliche Aktenzeichen.",
      value: "KI-gestützte Schadensprüfung ohne Abfluss von KVNR oder Ausweisdaten; DPO-Export enthält nur Entitätstypen.",
      buyerLine: "DPO-CSV beweist Maskierung ohne Rohdaten im Log.",
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
      pain: "Recruiters want AI to summarize CVs, but German Works Councils forbid uploading candidate identity, DOB, and tax details.",
      value: "Strips name, birth date, street address, phone, email, and Steuer-ID before Grok evaluates technical qualifications.",
      buyerLine: "Works-council-safe (Betriebsrat-konform) recruiting AI.",
      prompt:
        "Candidate Resume Excerpt — Katharina Weber (geb. 14.05.1991), Hauptstraße 19, 60325 Frankfurt. Contact: katharina.weber@example.de, +49 151 98765432. Payroll & Tax onboarding file: Steuer-Id 41928374651, Payout IBAN DE89 3704 0044 0532 0130 00.\nExperience: 7 years Principal Cloud Security Engineer (Kubernetes, eBPF, Cloud Governance). Summarize candidate strengths for the Senior Security Architect role.",
    },
    de: {
      label: "3. HR / Bewerbungs-Screening (Betriebsrat)",
      persona: "HR-Leitung / Betriebsrat",
      pain: "Recruiter möchten Lebensläufe per KI auswerten, aber der Betriebsrat untersagt den Upload von Klarnamen, Geburtsdaten und Adressen.",
      value: "Name, Geburtsdatum, Anschrift und Steuer-ID werden vor dem Modellaufruf maskiert; Fachprofil wird objektiv ausgewertet.",
      buyerLine: "Betriebsrat-konformes CV-Screening ohne Klardaten.",
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
      pain: "Dispatch logs mix critical substation Site IDs (UW-NORD-0417), customer meter accounts, and on-call engineer contact data.",
      value: "Tokenizes infrastructure Site IDs and customer account numbers before AI incident correlation with GlassFlow Tares.",
      buyerLine: "Runbooks & incident triage without exposing KRITIS site IDs.",
      prompt:
        "Grid Dispatch Log — Substation UW-NORD-0417 (Stuttgart, Industriering 8). Affected commercial meter: Kundenkonto 4401-88921-03. On-call lead: Markus Hoffmann (m.hoffmann@stadtwerke.example, +49 711 4455667) reported voltage sag on 28.10.2026. Draft a 3-step operator handover summary.",
    },
    de: {
      label: "4. Energie / KRITIS-Betrieb (SITE_ID + Zähler)",
      persona: "Netzleitstelle / KRITIS-Informationssicherheit",
      pain: "Störprotokolle enthalten Umspannwerk-Kennungen (UW-NORD-0417), Kundenkonten und Rufbereitschaftsdaten.",
      value: "Anlagen-IDs (SITE_ID), Zählerkonten und Technikerdaten werden maskiert, bevor KI-Agenten den Vorfall analysieren.",
      buyerLine: "KRITIS-Runbooks mit KI auswerten ohne Anlagen-IDs preiszugeben.",
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
      pain: "Developers and autonomous agents accidentally include production API keys (sk-..., AKIA...) alongside customer PII in prompts.",
      value: "Customer PII (IBAN, Name) is reversible in the reply, while API_KEY is non-reversible (stays permanently masked even after restoration).",
      buyerLine: "PII is restored for the user; leaked API keys stay masked forever.",
      prompt:
        "Debug agent webhook failure for customer Thomas Becker (thomas.becker@example.de, IBAN DE89 3704 0044 0532 0130 00 in Berlin). Outbound header trace contained bearer secret sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz123456. Explain how to rotate the credential and notify the customer.",
    },
    de: {
      label: "5. Agent-Log mit geleaktem API-Key",
      persona: "AI-Platform-Lead / SecOps",
      pain: "Entwickler oder Agenten senden versehentlich produktive API-Schlüssel (sk-..., AKIA...) zusammen mit Kundendaten an LLMs.",
      value: "Kunden-PII (IBAN, Name) wird in der Antwort wiederhergestellt, aber API_KEY ist nicht umkehrbar (reversible: false) und bleibt dauerhaft maskiert.",
      buyerLine: "PII wird kontrolliert re-identifiziert — API-Keys bleiben für immer maskiert.",
      prompt:
        "Analysiere den Webhook-Fehler für Kunde Thomas Becker (thomas.becker@example.de, IBAN DE89 3704 0044 0532 0130 00 in Berlin). Im Debug-Header stand versehentlich der Schlüssel sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz123456. Beschreibe kurz die Schlüsselrotation und eine Kundeninfo.",
    },
  },
  {
    id: "clean",
    badge: "Clean Baseline",
    recommendedLocale: "en",
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
