export interface HighlightSpan {
  start: number;
  end: number;
  entityType: string;
  token: string;
}

export interface TextSegment {
  text: string;
  span?: HighlightSpan;
}

/** Slice by UTF-16 indexes, which match Python indexes for BMP text (German). */
export function segmentText(text: string, spans: HighlightSpan[]): TextSegment[] {
  const sorted = [...spans]
    .filter((span) => span.start >= 0 && span.end > span.start && span.start < text.length)
    .map((span) => ({ ...span, end: Math.min(span.end, text.length) }))
    .sort((a, b) => a.start - b.start || a.end - b.end);

  const segments: TextSegment[] = [];
  let cursor = 0;
  for (const span of sorted) {
    if (span.start < cursor) {
      continue;
    }
    if (span.start > cursor) {
      segments.push({ text: text.slice(cursor, span.start) });
    }
    segments.push({ text: text.slice(span.start, span.end), span });
    cursor = span.end;
  }
  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor) });
  }
  if (segments.length === 0) {
    segments.push({ text });
  }
  return segments;
}

const ENTITY_CLASS: Record<string, string> = {
  PERSON: "bg-[#f3d7a1]",
  PERSON_NAME_DE: "bg-[#f3d7a1]",
  EMAIL_ADDRESS: "bg-[#b7e0d6]",
  PHONE_NUMBER: "bg-[#c5d4f6]",
  IBAN_CODE: "bg-[#f3c1c1]",
  IBAN_DE: "bg-[#f3c1c1]",
  IBAN_UNVERIFIED: "bg-[#f3c1c1]",
  IBAN: "bg-[#f3c1c1]",
  ACCOUNT_NUMBER_DE: "bg-[#f6c9ae]",
  CREDIT_CARD: "bg-[#f6c9ae]",
  TAX_ID_DE: "bg-[#f8b4b4]",
  TAX_ID_DE_UNVERIFIED: "bg-[#f8b4b4]",
  PERSONAL_AUSWEIS: "bg-[#f5c2e7]",
  KVNR: "bg-[#fbcfe8]",
  SVNR_DE: "bg-[#fbcfe8]",
  HR_NUMBER: "bg-[#d8e2dc]",
  AKTENZEICHEN: "bg-[#fde68a]",
  SITE_ID: "bg-[#bae6fd]",
  API_KEY: "bg-[#fca5a5] font-semibold ring-1 ring-[#991b1b]/40",
  DATE_TIME: "bg-[#ddd0f3]",
  DATE_DE: "bg-[#ddd0f3]",
  DATE_OF_BIRTH: "bg-[#ddd0f3]",
  LOCATION: "bg-[#cfe6be]",
  STREET_ADDRESS_DE: "bg-[#cfe6be]",
  POSTCODE_CITY_DE: "bg-[#cfe6be]",
  MNPI_TICKER: "bg-[#e2e8f0]",
};

export function entityClassName(entityType: string): string {
  return ENTITY_CLASS[entityType] ?? "bg-[#e4dccf]";
}

export function isNonReversibleEntity(entityType: string): boolean {
  return entityType === "API_KEY" || entityType === "SECRET" || entityType === "CREDENTIAL";
}

export const LEGEND_TYPES = [
  "PERSON",
  "EMAIL_ADDRESS",
  "PHONE_NUMBER",
  "IBAN_DE",
  "IBAN_CODE",
  "TAX_ID_DE",
  "KVNR",
  "PERSONAL_AUSWEIS",
  "AKTENZEICHEN",
  "HR_NUMBER",
  "SITE_ID",
  "API_KEY",
  "DATE_TIME",
  "LOCATION",
] as const;
