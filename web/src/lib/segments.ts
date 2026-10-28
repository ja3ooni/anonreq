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
  EMAIL_ADDRESS: "bg-[#b7e0d6]",
  PHONE_NUMBER: "bg-[#c5d4f6]",
  IBAN_CODE: "bg-[#f3c1c1]",
  IBAN: "bg-[#f3c1c1]",
  CREDIT_CARD: "bg-[#f6c9ae]",
  DATE_TIME: "bg-[#ddd0f3]",
  LOCATION: "bg-[#cfe6be]",
};

export function entityClassName(entityType: string): string {
  return ENTITY_CLASS[entityType] ?? "bg-[#e4dccf]";
}

export const LEGEND_TYPES = [
  "PERSON",
  "EMAIL_ADDRESS",
  "PHONE_NUMBER",
  "IBAN_CODE",
  "CREDIT_CARD",
  "DATE_TIME",
  "LOCATION",
] as const;
