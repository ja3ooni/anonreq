import type { PreviewEntity } from "@/lib/types";

interface FoundSpan {
  entity_type: string;
  start: number;
  end: number;
  priority: number;
  score: number;
}

const LEVEL: Record<string, number> = {
  PERSON: 1,
  LOCATION: 1,
  DATE_TIME: 1,
  EMAIL_ADDRESS: 2,
  PHONE_NUMBER: 2,
  CREDIT_CARD: 3,
  IBAN_CODE: 3,
};

const LEVEL_NAME = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED", "HIGHLY_RESTRICTED"];

const CITIES = [
  "Berlin",
  "München",
  "Munich",
  "Hamburg",
  "Frankfurt",
  "Köln",
  "Cologne",
  "Stuttgart",
  "Düsseldorf",
  "Wien",
  "Vienna",
  "Zürich",
  "Zurich",
  "London",
  "Paris",
];

const PERSON_STOP = new Set(
  [
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "in",
    "on",
    "he",
    "she",
    "his",
    "her",
    "iban",
    "please",
    "draft",
    "explain",
    "summarize",
    "this",
    "that",
    "for",
    "with",
    "from",
    "will",
    "be",
    "die",
    "der",
    "das",
    "den",
    "dem",
    "ein",
    "eine",
    "einer",
    "einem",
    "er",
    "sie",
    "ihre",
    "ihr",
    "bitte",
    "formuliere",
    "antwort",
    "kurze",
    "am",
    "ist",
    "und",
    "im",
  ].map((word) => word.toLowerCase()),
);

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function collect(text: string): FoundSpan[] {
  const found: FoundSpan[] = [];
  const add = (entityType: string, expression: RegExp, priority: number, score: number) => {
    for (const match of text.matchAll(expression)) {
      if (match.index === undefined) {
        continue;
      }
      const value = match[0];
      if (entityType === "PERSON") {
        const words = value.split(/\s+/);
        if (words.some((word) => PERSON_STOP.has(word.toLowerCase()))) {
          continue;
        }
      }
      found.push({
        entity_type: entityType,
        start: match.index,
        end: match.index + value.length,
        priority,
        score,
      });
    }
  };

  add("EMAIL_ADDRESS", /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, 1, 0.99);
  add("IBAN_CODE", /\b[A-Z]{2}\d{2}(?: ?\d{4}){4} ?\d{2}\b/g, 2, 0.97);
  add("CREDIT_CARD", /\b(?:\d{4}[ -]){3}\d{4}\b/g, 3, 0.95);
  add("PHONE_NUMBER", /\+\d{1,3}[\s-]?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,6}/g, 4, 0.9);
  add("DATE_TIME", /\b\d{2}\.\d{2}\.\d{4}\b|\b\d{4}-\d{2}-\d{2}\b/g, 5, 0.85);
  for (const city of CITIES) {
    add(
      "LOCATION",
      new RegExp(`(?<![\\p{L}])${escapeRegExp(city)}(?![\\p{L}])`, "gu"),
      6,
      0.8,
    );
  }
  add(
    "PERSON",
    /(?<![\p{L}])[\p{Lu}][\p{L}'’-]+(?:\s+[\p{Lu}][\p{L}'’-]+)+(?![\p{L}])/gu,
    7,
    0.78,
  );

  const sorted = [...found].sort(
    (a, b) => a.start - b.start || a.priority - b.priority || a.end - b.end,
  );
  const kept: FoundSpan[] = [];
  for (const span of sorted) {
    const overlap = kept.find((item) => span.start < item.end && span.end > item.start);
    if (!overlap) {
      kept.push(span);
      continue;
    }
    if (span.priority < overlap.priority) {
      kept[kept.indexOf(overlap)] = span;
    }
  }
  return kept.sort((a, b) => a.start - b.start);
}

/** UTF-16 index → Unicode code-point index. Regex matches are UTF-16. */
export function codePointIndex(text: string, utf16Index: number): number {
  const end = Math.max(0, Math.min(utf16Index, text.length));
  return [...text.slice(0, end)].length;
}

export interface Redaction {
  anonymized_text: string;
  entities: PreviewEntity[];
  classification: string;
  highest_entity: string;
}

/**
 * Demo stand-in for the gateway recognizers. Same token contract: `[TYPE_N]`,
 * and the same value reuses the same token. Not a detector to ship in production.
 */
export function redactText(text: string, messageIndex: number | null = null): Redaction {
  const spans = collect(text);
  const tokenByValue = new Map<string, string>();
  const counters = new Map<string, number>();
  let anonymized = "";
  let cursor = 0;
  const entities: PreviewEntity[] = [];

  for (const span of spans) {
    anonymized += text.slice(cursor, span.start);
    const spanText = text.slice(span.start, span.end);
    const key = `${span.entity_type}\u0000${spanText}`;
    let token = tokenByValue.get(key);
    if (!token) {
      const next = (counters.get(span.entity_type) ?? 0) + 1;
      counters.set(span.entity_type, next);
      token = `[${span.entity_type}_${next}]`;
      tokenByValue.set(key, token);
    }
    const tokenStart = [...anonymized].length;
    const tokenStartUtf16 = anonymized.length;
    anonymized += token;
    entities.push({
      entity_type: span.entity_type,
      span: spanText,
      token,
      score: span.score,
      start: codePointIndex(text, span.start),
      end: codePointIndex(text, span.end),
      start_utf16: span.start,
      end_utf16: span.end,
      token_start: tokenStart,
      token_end: [...anonymized].length,
      token_start_utf16: tokenStartUtf16,
      token_end_utf16: anonymized.length,
      message_index: messageIndex,
    });
    cursor = span.end;
  }
  anonymized += text.slice(cursor);

  let rank = 0;
  let highest = "";
  for (const entity of entities) {
    const level = LEVEL[entity.entity_type] ?? 1;
    if (level > rank) {
      rank = level;
      highest = entity.entity_type;
    }
  }

  return {
    anonymized_text: anonymized,
    entities,
    classification: LEVEL_NAME[rank] ?? "PUBLIC",
    highest_entity: highest,
  };
}

export function mockRestoredAnswer(entities: PreviewEntity[], locale: string): string {
  const german = locale.toLowerCase().startsWith("de");
  if (entities.length === 0) {
    return german
      ? "In diesem Prompt wurde nichts erkannt, das maskiert werden müsste."
      : "Nothing in this prompt needed masking.";
  }
  const pick = (type: string) => entities.find((entity) => entity.entity_type === type)?.span;
  const person = pick("PERSON");
  const email = pick("EMAIL_ADDRESS");
  const phone = pick("PHONE_NUMBER");
  const iban = pick("IBAN_CODE");
  const place = pick("LOCATION");
  const date = pick("DATE_TIME");
  const card = pick("CREDIT_CARD");

  if (german) {
    const parts = [
      person ? `${person} ist erreichbar` : "Die Angaben sind wieder eingesetzt",
      email ? `unter ${email}` : "",
      phone ? `Telefon ${phone}` : "",
      iban ? `Konto ${iban}` : "",
      card ? `Karte ${card}` : "",
      place ? `Ort ${place}` : "",
      date ? `Datum ${date}` : "",
    ].filter(Boolean);
    return `Wiederhergestellte Antwort: ${parts.join(", ")}.`;
  }

  const parts = [
    person ? `${person} is reachable` : "The original values are restored",
    email ? `at ${email}` : "",
    phone ? `phone ${phone}` : "",
    iban ? `account ${iban}` : "",
    card ? `card ${card}` : "",
    place ? `place ${place}` : "",
    date ? `date ${date}` : "",
  ].filter(Boolean);
  return `Restored reply: ${parts.join(", ")}.`;
}
