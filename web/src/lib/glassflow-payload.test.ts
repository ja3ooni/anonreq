import assert from "node:assert/strict";
import test from "node:test";

import { buildGlassFlowBundle } from "./glassflow.ts";
import { redactText } from "./redact.ts";
import { BUYER_SCENARIOS } from "./scenarios.ts";
import { checkPreview, MAX_BODY_BYTES, parseGlassFlowBundle, piiFindings, readCappedBody } from "./glassflow-payload.ts";

function bundleWith(anonymized: string, filename: string | null = null) {
  return buildGlassFlowBundle({
    mode: "scan_only",
    scenarioId: "bank",
    filename,
    tenantId: "default",
    locale: "de-DE",
    model: "grok-4",
    latencyMs: 40,
    preview: {
      request_id: "req_pl_01",
      locale: "de-DE",
      classification: "CONFIDENTIAL",
      highest_entity: "PERSON",
      anonymized_text: anonymized,
      anonymized_messages: null,
      entities: [{ entity_type: "PERSON", start: 0, end: 4, score: 0.9 }],
    } as never,
    chat: null,
  });
}

function parse(raw: unknown) {
  const parsed = parseGlassFlowBundle(JSON.stringify(raw));
  if (!parsed.ok) throw new Error(parsed.message);
  return parsed.bundle;
}

test("PII patterns: email, IBAN, phone, EGN, card, tax id, API keys; tokens are ignored", () => {
  const cases: Array<[string, string]> = [
    ["mail joerg@example.com", "EMAIL"],
    ["IBAN DE89 3704 0044 0532 0130 00", "IBAN"],
    ["IBAN BG80BNBG96611020345678", "IBAN"],
    ["call +49 30 1234 5678", "PHONE"],
    ["ЕГН 8001010008", "LONG_NUMBER"],
    ["card 4111 1111 1111 1111", "LONG_NUMBER"],
    ["Steuer-ID 12 345 678 901", "LONG_NUMBER"],
    ["key sk-proj-AbCdEfGhIjKlMnOpQrStUv", "API_KEY"],
  ];
  for (const [text, kind] of cases) {
    assert.ok(piiFindings(text).includes(kind), `${kind} not found in ${text}`);
  }
  assert.deepEqual(piiFindings("[PERSON_1] paid [IBAN_CODE_12] on [DATE_TIME_3]"), []);
});

test("preview: needs a [TYPE_N] token and no PII, else redacted; long text is clipped", () => {
  assert.deepEqual(checkPreview("Hello [PERSON_1]").reason, "ok");
  const noTokens = checkPreview("Hello Jörg Müller");
  assert.equal(noTokens.redacted, true);
  assert.equal(noTokens.reason, "no_tokens");
  assert.equal(noTokens.preview.includes("Jörg"), false);
  const leaked = checkPreview("[PERSON_1] joerg@example.com");
  assert.equal(leaked.reason, "pii_pattern");
  assert.equal(leaked.preview.includes("joerg"), false);
  assert.ok(checkPreview(`[PERSON_1] ${"a ".repeat(400)}`).preview.length <= 280);
});

test("raw_pii_leaked is computed: false for clean tokens, true when the 'sanitized' text still has PII", () => {
  const clean = parse(bundleWith("Kunde [PERSON_1] fragt nach [IBAN_CODE_1]"));
  assert.equal(clean.tares?.data.raw_pii_leaked, false);
  assert.equal(clean.tares?.data.preview_redacted, false);

  const leaky = parse(bundleWith("Kunde [PERSON_1], IBAN DE89 3704 0044 0532 0130 00"));
  assert.equal(leaky.tares?.data.raw_pii_leaked, true);
  assert.equal(leaky.tares?.data.preview_redacted, true);
  assert.equal(JSON.stringify(leaky).includes("DE89"), false);

  const untokenized = parse(bundleWith("Kunde Jörg Müller"));
  assert.equal(untokenized.tares?.data.preview_redaction_reason, "no_tokens");
  assert.equal(untokenized.tares?.data.raw_pii_leaked, false);
  assert.equal(JSON.stringify(untokenized).includes("Müller"), false);
});

test("file names with personal data are redacted in Tares and Rius", () => {
  const out = parse(bundleWith("[PERSON_1]", "Max_Mustermann_CV.pdf"));
  assert.equal(out.tares?.data.source_file, "[redacted]");
  assert.equal(JSON.stringify(out).includes("Mustermann"), false);
  assert.equal(parse(bundleWith("[PERSON_1]", "joerg@example.com.txt")).tares?.data.raw_pii_leaked, true);
  assert.equal(parse(bundleWith("[PERSON_1]", "sepa-ticket.txt")).tares?.data.source_file, "sepa-ticket.txt");
});

test("unknown fields are dropped; enums, patterns and lengths are enforced (400)", () => {
  const raw = bundleWith("[PERSON_1]") as unknown as Record<string, Record<string, unknown>>;
  const out = parse({ ...raw, extra: 1, tares: { ...raw.tares, injected: "x" } });
  assert.equal("injected" in (out.tares as object), false);
  assert.equal("sanitized_context" in (out.tares?.data as object), false);

  const bad: Array<[string, (b: Record<string, Record<string, unknown>>) => void]> = [
    ["decision", (b) => (b.tares.decision = "ALLOW_ALL")],
    ["classification", (b) => (b.tares.classification = "TOP")],
    ["type", (b) => (b.tares.type = "evil.event")],
    ["tenant_id", (b) => (b.tares.tenant_id = "x".repeat(65))],
    ["locale", (b) => ((b.tares.data as Record<string, unknown>).locale = "de-DE; drop")],
    ["context", (b) => ((b.tares.data as Record<string, unknown>).sanitized_context = "[A_1]".repeat(2000))],
    ["counts", (b) => ((b.tares.data as Record<string, unknown>).entity_counts = { PERSON: -1 })],
    ["span name", (b) => ((b.rius.spans as Array<Record<string, unknown>>)[0].name = "custom")],
    ["span count", (b) => (b.rius.spans = Array(9).fill((b.rius.spans as unknown[])[0]))],
  ];
  for (const [label, mutate] of bad) {
    const copy = structuredClone(raw);
    mutate(copy);
    const parsed = parseGlassFlowBundle(JSON.stringify(copy));
    assert.equal(!parsed.ok && parsed.status, 400, label);
  }
});

test("rius attributes are allowlisted and cleartext_pii_forwarded is not passed through", () => {
  const raw = bundleWith("[PERSON_1]") as unknown as { rius: { spans: Array<{ attributes: Record<string, unknown> }> } };
  raw.rius.spans[0].attributes["user.email"] = "joerg@example.com";
  const out = parse(raw);
  const attrs = out.rius?.spans[0].attributes ?? {};
  assert.equal("user.email" in attrs, false);
  assert.equal("anonreq.cleartext_pii_forwarded" in attrs, false);
  assert.equal(attrs["anonreq.decision"], "ANONYMIZE");
});

test("413 above 64 KB, by Content-Length or by streamed size", async () => {
  const big = "x".repeat(MAX_BODY_BYTES + 1);
  const declared = await readCappedBody(new Request("http://127.0.0.1/api/glassflow", { method: "POST", body: big }));
  assert.equal(!declared.ok && declared.status, 413);

  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (let i = 0; i < 70; i += 1) controller.enqueue(new Uint8Array(1024));
      controller.close();
    },
  });
  const streamed = await readCappedBody(
    new Request("http://127.0.0.1/api/glassflow", { method: "POST", body: stream, duplex: "half" } as RequestInit),
  );
  assert.equal(!streamed.ok && streamed.status, 413);

  const ok = await readCappedBody(new Request("http://127.0.0.1/api/glassflow", { method: "POST", body: '{"a":1}' }));
  assert.deepEqual(ok, { ok: true, text: '{"a":1}' });
});

test("every demo scenario (EN + DE, mock redaction) passes the allowlist and leaks nothing", () => {
  for (const scenario of BUYER_SCENARIOS) {
    for (const lang of ["en", "de"] as const) {
      const prompt = scenario[lang].prompt;
      const redaction = redactText(prompt);
      const raw = buildGlassFlowBundle({
        mode: "full_chat",
        scenarioId: scenario.id,
        filename: "02-frankfurt-pii-dossier.md",
        tenantId: "default",
        locale: scenario.recommendedLocale,
        model: "grok-4",
        latencyMs: 50,
        preview: {
          request_id: "req_demo_1",
          locale: scenario.recommendedLocale,
          classification: redaction.classification,
          highest_entity: redaction.highest_entity,
          anonymized_text: redaction.anonymized_text,
          anonymized_messages: null,
          entities: redaction.entities,
        },
        chat: null,
      });
      const parsed = parseGlassFlowBundle(JSON.stringify(raw));
      assert.ok(parsed.ok, `${scenario.id}/${lang}: ${!parsed.ok && parsed.message}`);
      const out = JSON.stringify(parsed.ok && parsed.bundle);
      for (const entity of redaction.entities) {
        const value = prompt.slice(entity.start, entity.end);
        if (value.length >= 4) assert.equal(out.includes(value), false, `${scenario.id}/${lang} leaks ${value}`);
      }
    }
  }
});
