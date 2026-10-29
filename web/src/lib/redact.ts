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
  PERSON_NAME_DE: 1,
  LOCATION: 1,
  STREET_ADDRESS_DE: 1,
  POSTCODE_CITY_DE: 1,
  DATE_TIME: 1,
  DATE_DE: 1,
  DATE_OF_BIRTH: 2,
  SITE_ID: 2,
  HR_NUMBER: 2,
  AKTENZEICHEN: 2,
  EMAIL_ADDRESS: 2,
  PHONE_NUMBER: 2,
  ACCOUNT_NUMBER_DE: 3,
  CREDIT_CARD: 3,
  IBAN_CODE: 3,
  IBAN_DE: 3,
  TAX_ID_DE: 3,
  PERSONAL_AUSWEIS: 3,
  KVNR: 3,
  SVNR_DE: 3,
  API_KEY: 4,
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
    "schadensmeldung",
    "versicherte",
    "versicherter",
    "kontakt",
    "sachverhalt",
    "kundenkonto",
    "steuer",
    "personalausweis",
    "aktenzeichen",
    "gesellschaft",
    "ticket",
    "auffahrunfall",
    "deckungszusage",
    "kandidat",
    "kandidatin",
    "lebenslauf",
    "störmeldung",
    "umspannwerk",
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

  add("API_KEY", /\b(?:sk-(?:proj-)?[a-zA-Z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36})\b/g, 0, 0.99);
  add("EMAIL_ADDRESS", /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, 1, 0.99);
  add("IBAN_CODE", /\b[A-Z]{2}\d{2}(?: ?\d{4}){4} ?\d{2}\b/g, 2, 0.97);
  add("TAX_ID_DE", /\b[1-9]\d{10}\b/g, 2, 0.94);
  add("KVNR", /\b[A-Z]\d{9}\b/g, 2, 0.93);
  add("PERSONAL_AUSWEIS", /\b[A-Z](?!\d{9}\b)[A-Z0-9]{8}\d\b/g, 2, 0.92);
  add("AKTENZEICHEN", /\bAz\.?\s*\d{1,3}\s*[A-ZÄÖÜ]{1,5}\s*\d{1,6}\/\d{2,4}\b/g, 3, 0.91);
  add("HR_NUMBER", /\bHR[AB]\s?\d{1,6}(?:\s[A-Z]{1,3})?\b/g, 3, 0.9);
  add("SITE_ID", /\b[A-Z]{2,5}(?:-[A-Z0-9]{2,10})+-\d{2,6}\b/g, 3, 0.89);
  add("CREDIT_CARD", /\b(?:\d{4}[ -]){3}\d{4}\b/g, 3, 0.95);
  add("PHONE_NUMBER", /\+\d{1,3}[\s-]?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,6}/g, 4, 0.9);
  add("DATE_TIME", /\b\d{2}\.\d{2}\.\d{4}\b|\b\d{4}-\d{2}-\d{2}\b/g, 5, 0.85);
  add(
    "STREET_ADDRESS_DE",
    /\b[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ]?[a-zäöüß]+)*(?:straße|strasse|str\.|weg|allee|platz|gasse|ring|damm|ufer)\s+\d{1,4}[a-zA-Z]?\b/g,
    5,
    0.84,
  );
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
  const pickToken = (type: string) => entities.find((entity) => entity.entity_type === type)?.token;
  const person = pick("PERSON") ?? pick("PERSON_NAME_DE");
  const email = pick("EMAIL_ADDRESS");
  const phone = pick("PHONE_NUMBER");
  const iban = pick("IBAN_CODE") ?? pick("IBAN_DE");
  const taxId = pick("TAX_ID_DE");
  const kvnr = pick("KVNR");
  const ausweis = pick("PERSONAL_AUSWEIS");
  const aktenzeichen = pick("AKTENZEICHEN");
  const siteId = pick("SITE_ID");
  const place = pick("LOCATION") ?? pick("STREET_ADDRESS_DE");
  const date = pick("DATE_TIME") ?? pick("DATE_DE");
  const card = pick("CREDIT_CARD");
  const apiKeyToken = pickToken("API_KEY");

  if (german) {
    const parts = [
      person ? `${person} ist erreichbar` : "Die Angaben sind wieder eingesetzt",
      email ? `unter ${email}` : "",
      phone ? `Telefon ${phone}` : "",
      iban ? `Konto ${iban}` : "",
      taxId ? `Steuer-ID ${taxId}` : "",
      kvnr ? `KVNR ${kvnr}` : "",
      ausweis ? `Ausweis ${ausweis}` : "",
      aktenzeichen ? `Aktenzeichen ${aktenzeichen}` : "",
      siteId ? `Anlage ${siteId}` : "",
      card ? `Karte ${card}` : "",
      place ? `Ort ${place}` : "",
      date ? `Datum ${date}` : "",
      apiKeyToken ? `Zugangsschlüssel bleibt dauerhaft maskiert als ${apiKeyToken} (nicht umkehrbar)` : "",
    ].filter(Boolean);
    return `Wiederhergestellte Antwort: ${parts.join(", ")}.`;
  }

  const parts = [
    person ? `${person} is reachable` : "The original values are restored",
    email ? `at ${email}` : "",
    phone ? `phone ${phone}` : "",
    iban ? `account ${iban}` : "",
    taxId ? `tax ID ${taxId}` : "",
    kvnr ? `KVNR ${kvnr}` : "",
    ausweis ? `ID ${ausweis}` : "",
    aktenzeichen ? `case ${aktenzeichen}` : "",
    siteId ? `site ${siteId}` : "",
    card ? `card ${card}` : "",
    place ? `place ${place}` : "",
    date ? `date ${date}` : "",
    apiKeyToken ? `secret key remains permanently masked as ${apiKeyToken} (non-reversible)` : "",
  ].filter(Boolean);
  return `Restored reply: ${parts.join(", ")}.`;
}

export function mockRawModelAnswer(entities: PreviewEntity[], locale: string): string {
  const german = locale.toLowerCase().startsWith("de");
  if (entities.length === 0) {
    return german
      ? "In diesem Prompt wurde nichts erkannt, das maskiert werden müsste."
      : "Nothing in this prompt needed masking.";
  }
  const pickToken = (type: string) => entities.find((entity) => entity.entity_type === type)?.token;
  const person = pickToken("PERSON") ?? pickToken("PERSON_NAME_DE");
  const email = pickToken("EMAIL_ADDRESS");
  const phone = pickToken("PHONE_NUMBER");
  const iban = pickToken("IBAN_CODE") ?? pickToken("IBAN_DE");
  const taxId = pickToken("TAX_ID_DE");
  const kvnr = pickToken("KVNR");
  const ausweis = pickToken("PERSONAL_AUSWEIS");
  const aktenzeichen = pickToken("AKTENZEICHEN");
  const siteId = pickToken("SITE_ID");
  const place = pickToken("LOCATION") ?? pickToken("STREET_ADDRESS_DE");
  const date = pickToken("DATE_TIME") ?? pickToken("DATE_DE");
  const card = pickToken("CREDIT_CARD");
  const apiKeyToken = pickToken("API_KEY");

  if (german) {
    const parts = [
      person ? `${person} ist erreichbar` : "Die Angaben sind wieder eingesetzt",
      email ? `unter ${email}` : "",
      phone ? `Telefon ${phone}` : "",
      iban ? `Konto ${iban}` : "",
      taxId ? `Steuer-ID ${taxId}` : "",
      kvnr ? `KVNR ${kvnr}` : "",
      ausweis ? `Ausweis ${ausweis}` : "",
      aktenzeichen ? `Aktenzeichen ${aktenzeichen}` : "",
      siteId ? `Anlage ${siteId}` : "",
      card ? `Karte ${card}` : "",
      place ? `Ort ${place}` : "",
      date ? `Datum ${date}` : "",
      apiKeyToken ? `Zugangsschlüssel bleibt dauerhaft maskiert als ${apiKeyToken} (nicht umkehrbar)` : "",
    ].filter(Boolean);
    return `Wiederhergestellte Antwort: ${parts.join(", ")}.`;
  }

  const parts = [
    person ? `${person} is reachable` : "The original values are restored",
    email ? `at ${email}` : "",
    phone ? `phone ${phone}` : "",
    iban ? `account ${iban}` : "",
    taxId ? `tax ID ${taxId}` : "",
    kvnr ? `KVNR ${kvnr}` : "",
    ausweis ? `ID ${ausweis}` : "",
    aktenzeichen ? `case ${aktenzeichen}` : "",
    siteId ? `site ${siteId}` : "",
    card ? `card ${card}` : "",
    place ? `place ${place}` : "",
    date ? `date ${date}` : "",
    apiKeyToken ? `secret key remains permanently masked as ${apiKeyToken} (non-reversible)` : "",
  ].filter(Boolean);
  return `Restored reply: ${parts.join(", ")}.`;
}

export interface AnswerHighlightPair {
  rawModelText: string;
  rawModelSpans: Array<{ start: number; end: number; entityType: string; token: string }>;
  restoredSpans: Array<{ start: number; end: number; entityType: string; token: string }>;
}

/**
 * Given the restored answer, optional raw model answer (before restoration),
 * and the preview entities, builds the pre-restoration model reply and
 * highlight spans for both the raw model reply (tokens) and the restored answer (values).
 */
export function buildAnswerHighlights(
  restoredAnswer: string,
  rawAnswerFromGateway: string | null | undefined,
  entities: PreviewEntity[],
): AnswerHighlightPair {
  // Unique (span -> token, entityType) pairs, longest span first so replacements don't collide
  const uniqueBySpan = new Map<string, { token: string; entityType: string }>();
  const tokenToType = new Map<string, string>();
  for (const entity of entities) {
    tokenToType.set(entity.token.toUpperCase(), entity.entity_type);
    if (entity.span && !uniqueBySpan.has(entity.span)) {
      uniqueBySpan.set(entity.span, { token: entity.token, entityType: entity.entity_type });
    }
  }

  let rawModelText = rawAnswerFromGateway ?? "";
  if (!rawModelText && restoredAnswer) {
    // Reconstruct the pre-restoration model response by replacing restored spans with their [TYPE_N] tokens
    rawModelText = restoredAnswer;
    const entries = [...uniqueBySpan.entries()].sort((a, b) => b[0].length - a[0].length);
    for (const [spanValue, { token, entityType }] of entries) {
      if (entityType === "API_KEY" || entityType === "SECRET") {
        continue;
      }
      rawModelText = rawModelText.split(spanValue).join(token);
    }
  }

  // Find all [TYPE_N] tokens in rawModelText
  const rawModelSpans: Array<{ start: number; end: number; entityType: string; token: string }> = [];
  const tokenRegex = /\[([A-Z][A-Z0-9_]*)_\d+\]/gi;
  for (const match of rawModelText.matchAll(tokenRegex)) {
    if (match.index === undefined) continue;
    const tokenStr = match[0];
    const prefixType = match[1]?.toUpperCase() ?? "PERSON";
    const entityType = tokenToType.get(tokenStr.toUpperCase()) ?? prefixType;
    rawModelSpans.push({
      start: match.index,
      end: match.index + tokenStr.length,
      entityType,
      token: tokenStr,
    });
  }

  // Find all restored span values (and any residual non-reversible [API_KEY_N] tokens) in restoredAnswer
  const restoredSpans: Array<{ start: number; end: number; entityType: string; token: string }> = [];
  const entries = [...uniqueBySpan.entries()].sort((a, b) => b[0].length - a[0].length);
  for (const [spanValue, { token, entityType }] of entries) {
    if (!spanValue) continue;
    let searchFrom = 0;
    while (searchFrom < restoredAnswer.length) {
      const idx = restoredAnswer.indexOf(spanValue, searchFrom);
      if (idx === -1) break;
      restoredSpans.push({
        start: idx,
        end: idx + spanValue.length,
        entityType,
        token,
      });
      searchFrom = idx + spanValue.length;
    }
  }
  for (const match of restoredAnswer.matchAll(tokenRegex)) {
    if (match.index === undefined) continue;
    const tokenStr = match[0];
    const prefixType = match[1]?.toUpperCase() ?? "API_KEY";
    const entityType = tokenToType.get(tokenStr.toUpperCase()) ?? prefixType;
    restoredSpans.push({
      start: match.index,
      end: match.index + tokenStr.length,
      entityType,
      token: tokenStr,
    });
  }

  return {
    rawModelText,
    rawModelSpans,
    restoredSpans,
  };
}
