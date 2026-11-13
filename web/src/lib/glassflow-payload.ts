/**
 * Server-side allowlist for the GlassFlow bundle posted to /api/glassflow.
 *
 * The browser's bundle is never forwarded as-is. We rebuild it from fixed fields with enums,
 * patterns and per-field length limits; anything else is dropped, and an invalid value is a 400.
 * Free text (the sanitized prompt preview, the source file name) is checked for leftover PII:
 * it must carry at least one [TYPE_N] token and match no PII pattern, otherwise it is redacted.
 * raw_pii_leaked is computed from that check (true = the "sanitized" text still looked like PII).
 *
 * No imports, so tests run it under `node --experimental-strip-types`.
 */

/** Body fields that would pick a target or credential. Refused with 400. Single source of truth. */
export const CLIENT_TARGET_FIELDS = ["taresUrl", "taresToken", "riusEndpoint", "riusApiKey", "url", "token"] as const;

export const MAX_BODY_BYTES = 64 * 1024;
export const PREVIEW_MAX_CHARS = 280;
const CONTEXT_MAX_CHARS = 8_000;

export type PayloadError = { ok: false; status: 400 | 413; message: string };

/** Reads at most `max` bytes of the request body; larger bodies are a 413 without reading the rest. */
export async function readCappedBody(request: Request, max = MAX_BODY_BYTES): Promise<{ ok: true; text: string } | PayloadError> {
  const declared = Number(request.headers.get("content-length") ?? "");
  if (Number.isFinite(declared) && declared > max) {
    return { ok: false, status: 413, message: `Payload too large (max ${max} bytes)` };
  }
  if (!request.body) {
    return { ok: true, text: "" };
  }
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > max) {
      await reader.cancel().catch(() => undefined);
      return { ok: false, status: 413, message: `Payload too large (max ${max} bytes)` };
    }
    chunks.push(value);
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return { ok: true, text: new TextDecoder().decode(bytes) };
}

// ---- PII check ------------------------------------------------------------------

const TOKEN = /\[[A-Z][A-Z0-9_]*_\d+\]/g;
const PII_PATTERNS: ReadonlyArray<[string, RegExp]> = [
  ["EMAIL", /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/],
  ["IBAN", /\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,4})?\b/],
  ["PHONE", /(?:\+|\b00)\d{1,3}[\s\-/().]*\d(?:[\s\-/().]*\d){5,}/],
  // EGN (10 digits), tax IDs (11), card numbers (13-19), any long digit run with separators.
  ["LONG_NUMBER", /\d(?:[\s\-.]?\d){8,}/],
  ["API_KEY", /\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|xai-[A-Za-z0-9]{16,})\b/],
];

/** Names of the PII patterns found in `text`, ignoring [TYPE_N] tokens. */
export function piiFindings(text: string): string[] {
  const stripped = text.replace(TOKEN, " ");
  return PII_PATTERNS.filter(([, pattern]) => pattern.test(stripped)).map(([name]) => name);
}

export interface PreviewCheck {
  preview: string;
  redacted: boolean;
  reason: "ok" | "empty" | "no_tokens" | "pii_pattern";
  piiFound: string[];
}

/** Builds the forwarded preview: tokens required, no PII patterns, at most PREVIEW_MAX_CHARS. */
export function checkPreview(raw: string): PreviewCheck {
  const text = raw.replace(/\s+/g, " ").trim();
  if (!text) {
    return { preview: "", redacted: false, reason: "empty", piiFound: [] };
  }
  const piiFound = piiFindings(text);
  if (piiFound.length > 0) {
    return { preview: "[redacted: possible PII]", redacted: true, reason: "pii_pattern", piiFound };
  }
  if (!new RegExp(TOKEN.source).test(text)) {
    return { preview: "[redacted: no anonymization tokens]", redacted: true, reason: "no_tokens", piiFound };
  }
  const clipped = text.length > PREVIEW_MAX_CHARS ? `${text.slice(0, PREVIEW_MAX_CHARS - 1)}…` : text;
  return { preview: clipped, redacted: false, reason: "ok", piiFound };
}

// ---- field validators -------------------------------------------------------------

class InvalidField extends Error {}

const ID = /^[A-Za-z0-9._:-]{1,64}$/;
const KEY = /^[A-Za-z0-9._:-]{1,130}$/;
const REQUEST_ID = /^[A-Za-z0-9_-]{1,80}$/;
const ENTITY = /^[A-Z][A-Z0-9_]{0,39}$/;
const LOCALE = /^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$/;
const MODEL = /^[\w.:/-]{1,128}$/;
const HEX32 = /^[0-9a-f]{32}$/;
const HEX16 = /^[0-9a-f]{16}$/;
const NANOS = /^\d{1,20}$/;

const DECISIONS = ["ANONYMIZE", "PASS", "BLOCK", "FAIL_CLOSED"] as const;
const CLASSIFICATIONS = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED", "HIGHLY_RESTRICTED", "BLOCKED"] as const;
const EVENT_TYPES = ["ai.anonreq.context.sanitized", "ai.anonreq.gateway.fail_closed"] as const;
const SPAN_KINDS = ["SERVER", "INTERNAL", "CLIENT"] as const;
const SPAN_STATUS = ["STATUS_CODE_OK", "STATUS_CODE_ERROR"] as const;
const SPAN_NAMES = ["anonreq.gateway.handle_request", "anonreq.pipeline.detect_and_tokenize", "gen_ai.xai.chat.completions"] as const;
const MODES = ["scan_only", "full_chat"] as const;

function upper(value: unknown): unknown {
  return typeof value === "string" ? value.toUpperCase() : value;
}
function rec(value: unknown, field: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new InvalidField(`${field} must be an object`);
  return value as Record<string, unknown>;
}
function str(value: unknown, field: string, pattern: RegExp): string {
  if (typeof value !== "string" || !pattern.test(value)) throw new InvalidField(`${field} is invalid`);
  return value;
}
function optStr(value: unknown, field: string, pattern: RegExp): string {
  return value === undefined || value === null || value === "" ? "" : str(value, field, pattern);
}
function oneOf<T extends string>(value: unknown, field: string, allowed: readonly T[]): T {
  if (typeof value !== "string" || !(allowed as readonly string[]).includes(value)) throw new InvalidField(`${field} is invalid`);
  return value as T;
}
function int(value: unknown, field: string, max = 1_000_000): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0 || value > max) throw new InvalidField(`${field} is invalid`);
  return value;
}
function bool(value: unknown, field: string): boolean {
  if (typeof value !== "boolean") throw new InvalidField(`${field} is invalid`);
  return value;
}
function counts(value: unknown, field: string): Record<string, number> {
  const input = value === undefined ? {} : rec(value, field);
  const keys = Object.keys(input);
  if (keys.length > 50) throw new InvalidField(`${field} has too many keys`);
  const out: Record<string, number> = {};
  for (const key of keys) {
    out[str(key, `${field} key`, ENTITY)] = int(input[key], `${field}.${key}`, 100_000);
  }
  return out;
}
function iso(value: unknown, field: string): string {
  if (typeof value !== "string" || value.length > 40 || Number.isNaN(Date.parse(value))) throw new InvalidField(`${field} is invalid`);
  return new Date(value).toISOString();
}
/** File names can carry personal data (e.g. "Max_Mustermann_CV.pdf"): forward only when clean. */
function safeFileName(value: unknown, field: string): { name: string | null; pii: boolean } {
  if (value === undefined || value === null || value === "" || value === "inline_prompt") return { name: null, pii: false };
  if (typeof value !== "string" || value.length > 128) throw new InvalidField(`${field} is invalid`);
  if (piiFindings(value).length > 0) return { name: "[redacted]", pii: true };
  return /^[\w .()-]{1,128}$/.test(value) && !/[A-Z][a-z]+[_ .-][A-Z][a-z]+/.test(value)
    ? { name: value, pii: false }
    : { name: "[redacted]", pii: false };
}

export interface SanitizedTares {
  specversion: "1.0";
  id: string;
  source: "urn:anonreq:gateway:de-frankfurt";
  service: "anonreq-gateway";
  type: (typeof EVENT_TYPES)[number];
  time: string;
  subject: string;
  correlation_key: string;
  tenant_id: string;
  scenario: string;
  decision: (typeof DECISIONS)[number];
  classification: (typeof CLASSIFICATIONS)[number];
  highest_entity: string;
  data: {
    request_id: string;
    tenant_id: string;
    locale: string;
    scenario: string;
    source_file: string | null;
    decision: (typeof DECISIONS)[number];
    classification: (typeof CLASSIFICATIONS)[number];
    highest_entity: string;
    entity_counts: Record<string, number>;
    non_reversible_masked: number;
    sanitized_prompt_preview: string;
    preview_redacted: boolean;
    preview_redaction_reason: PreviewCheck["reason"];
    /** Computed: the client's "sanitized" text or file name matched a PII pattern (then redacted). */
    raw_pii_leaked: boolean;
    agent_wake_allowed: boolean;
    upstream_model: string | null;
  };
}

export interface SanitizedSpan {
  traceId: string;
  spanId: string;
  parentSpanId?: string;
  name: (typeof SPAN_NAMES)[number];
  kind: (typeof SPAN_KINDS)[number];
  startTimeUnixNano: string;
  endTimeUnixNano: string;
  status: { code: (typeof SPAN_STATUS)[number] };
  attributes: Record<string, string | number | boolean>;
}

export interface SanitizedRius {
  resource: { attributes: { "service.name": "anonreq-gateway"; "service.namespace": "frankfurt-eu-edge"; "deployment.environment": string } };
  spans: SanitizedSpan[];
}

export interface SanitizedBundle {
  tares: SanitizedTares | null;
  rius: SanitizedRius | null;
}

function sanitizeTares(raw: unknown): SanitizedTares {
  const t = rec(raw, "tares");
  const d = rec(t.data ?? {}, "tares.data");
  const decision = oneOf(t.decision, "tares.decision", DECISIONS);
  const classification = oneOf(upper(t.classification), "tares.classification", CLASSIFICATIONS);
  const highest = optStr(t.highest_entity === "NONE" ? "" : t.highest_entity, "tares.highest_entity", ENTITY);
  const context = d.sanitized_prompt_preview ?? d.sanitized_context ?? "";
  if (typeof context !== "string" || context.length > CONTEXT_MAX_CHARS) throw new InvalidField("tares.data.sanitized_context is invalid");
  const preview = checkPreview(context);
  const file = safeFileName(d.source_file, "tares.data.source_file");
  const tenant = str(t.tenant_id, "tares.tenant_id", ID);
  const scenario = str(t.scenario, "tares.scenario", ID);
  return {
    specversion: "1.0",
    id: str(t.id, "tares.id", /^evt_[A-Za-z0-9_-]{1,80}$/),
    source: "urn:anonreq:gateway:de-frankfurt",
    service: "anonreq-gateway",
    type: oneOf(t.type, "tares.type", EVENT_TYPES),
    time: iso(t.time, "tares.time"),
    subject: `tenant:${tenant}:scenario:${scenario}`,
    correlation_key: str(t.correlation_key, "tares.correlation_key", KEY),
    tenant_id: tenant,
    scenario,
    decision,
    classification,
    highest_entity: highest || "NONE",
    data: {
      request_id: str(d.request_id, "tares.data.request_id", REQUEST_ID),
      tenant_id: tenant,
      locale: str(d.locale, "tares.data.locale", LOCALE),
      scenario,
      source_file: file.name,
      decision,
      classification,
      highest_entity: highest,
      entity_counts: counts(d.entity_counts, "tares.data.entity_counts"),
      non_reversible_masked: int(d.non_reversible_masked ?? 0, "tares.data.non_reversible_masked", 100_000),
      sanitized_prompt_preview: preview.preview,
      preview_redacted: preview.redacted,
      preview_redaction_reason: preview.reason,
      raw_pii_leaked: preview.reason === "pii_pattern" || file.pii,
      agent_wake_allowed: bool(d.agent_wake_allowed ?? false, "tares.data.agent_wake_allowed"),
      upstream_model: d.upstream_model == null ? null : str(d.upstream_model, "tares.data.upstream_model", MODEL),
    },
  };
}

type AttrRule = (value: unknown, field: string) => string | number | boolean;
const ATTR_RULES: Record<string, AttrRule> = {
  "anonreq.request_id": (v, f) => str(v, f, REQUEST_ID),
  "anonreq.tenant_id": (v, f) => str(v, f, ID),
  "anonreq.locale": (v, f) => str(v, f, LOCALE),
  "anonreq.mode": (v, f) => oneOf(v, f, MODES),
  "anonreq.decision": (v, f) => oneOf(v, f, DECISIONS),
  "anonreq.classification": (v, f) => oneOf(upper(v), f, CLASSIFICATIONS),
  "anonreq.highest_entity": (v, f) => str(v, f, /^(?:NONE|[A-Z][A-Z0-9_]{0,39})$/),
  "anonreq.entity_total": (v, f) => int(v, f, 100_000),
  "anonreq.non_reversible_entities": (v, f) => int(v, f, 100_000),
  "anonreq.presidio.language": (v, f) => str(v, f, /^[a-z]{2}$/),
  "anonreq.entity_counts_json": (v, f) => {
    if (typeof v !== "string" || v.length > 2_000) throw new InvalidField(`${f} is invalid`);
    let parsed: unknown;
    try {
      parsed = JSON.parse(v);
    } catch {
      throw new InvalidField(`${f} is invalid`);
    }
    return JSON.stringify(counts(parsed, f));
  },
  "anonreq.source_file": (v, f) => safeFileName(v, f).name ?? "inline_prompt",
  "gen_ai.system": (v, f) => oneOf(v, f, ["xai"] as const),
  "gen_ai.request.model": (v, f) => str(v, f, MODEL),
  "anonreq.tokens_restored_in_response": (v, f) => int(Math.max(0, Number(v)), f, 100_000),
  "anonreq.secrets_kept_masked": (v, f) => int(v, f, 100_000),
};

function sanitizeRius(raw: unknown): SanitizedRius {
  const r = rec(raw, "rius");
  const spansIn = r.spans;
  if (!Array.isArray(spansIn) || spansIn.length === 0 || spansIn.length > 8) throw new InvalidField("rius.spans is invalid");
  const env = rec(rec(r.resource ?? {}, "rius.resource").attributes ?? {}, "rius.resource.attributes")["deployment.environment"];
  const spans = spansIn.map((spanRaw, index) => {
    const s = rec(spanRaw, `rius.spans[${index}]`);
    const attrsIn = rec(s.attributes ?? {}, `rius.spans[${index}].attributes`);
    const attributes: Record<string, string | number | boolean> = {};
    for (const [key, rule] of Object.entries(ATTR_RULES)) {
      if (key in attrsIn) attributes[key] = rule(attrsIn[key], `rius.spans[${index}].${key}`);
    }
    const span: SanitizedSpan = {
      traceId: str(s.traceId, `rius.spans[${index}].traceId`, HEX32),
      spanId: str(s.spanId, `rius.spans[${index}].spanId`, HEX16),
      name: oneOf(s.name, `rius.spans[${index}].name`, SPAN_NAMES),
      kind: oneOf(s.kind, `rius.spans[${index}].kind`, SPAN_KINDS),
      startTimeUnixNano: str(s.startTimeUnixNano, `rius.spans[${index}].startTimeUnixNano`, NANOS),
      endTimeUnixNano: str(s.endTimeUnixNano, `rius.spans[${index}].endTimeUnixNano`, NANOS),
      status: { code: oneOf(rec(s.status ?? {}, `rius.spans[${index}].status`).code, `rius.spans[${index}].status.code`, SPAN_STATUS) },
      attributes,
    };
    if (s.parentSpanId !== undefined) span.parentSpanId = str(s.parentSpanId, `rius.spans[${index}].parentSpanId`, HEX16);
    return span;
  });
  return {
    resource: {
      attributes: {
        "service.name": "anonreq-gateway",
        "service.namespace": "frankfurt-eu-edge",
        "deployment.environment": optStr(env, "rius.resource.deployment.environment", /^[a-z0-9-]{1,48}$/) || "demo",
      },
    },
    spans,
  };
}

/** Parses the request body and rebuilds an allowlisted bundle, or returns a 400. */
export function parseGlassFlowBundle(text: string): { ok: true; bundle: SanitizedBundle } | PayloadError {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return { ok: false, status: 400, message: "Telemetry payload must be JSON" };
  }
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return { ok: false, status: 400, message: "Telemetry payload must be a JSON object" };
  }
  const body = raw as Record<string, unknown>;
  const clientTargets = CLIENT_TARGET_FIELDS.filter((field) => field in body);
  if (clientTargets.length > 0) {
    return {
      ok: false,
      status: 400,
      message: `GlassFlow targets are server-configured (GLASSFLOW_TARES_WEBHOOK_URL, GLASSFLOW_TARES_TOKEN, GLASSFLOW_RIUS_OTLP_ENDPOINT). Remove: ${clientTargets.join(", ")}`,
    };
  }
  try {
    return {
      ok: true,
      bundle: {
        tares: body.tares == null ? null : sanitizeTares(body.tares),
        rius: body.rius == null ? null : sanitizeRius(body.rius),
      },
    };
  } catch (error) {
    if (error instanceof InvalidField) {
      return { ok: false, status: 400, message: error.message };
    }
    throw error;
  }
}
