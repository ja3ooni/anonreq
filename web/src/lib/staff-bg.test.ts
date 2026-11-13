import assert from "node:assert/strict";
import test from "node:test";

import { FAKE_IBAN_1, STAFF_DEMO_PROMPTS } from "./bg-demo-prompts.ts";
import { buildAnswerHighlights, mockRawModelAnswer, mockRestoredAnswer, redactText } from "./redact.ts";
import { segmentText } from "./segments.ts";
import {
  BGGPT_ALIAS_PLACEHOLDER,
  resolveAdminContext,
  resolveBgGptAlias,
  staffDetectionLocale,
  staffModelOptions,
} from "./staff-config.ts";

function ibanIsValid(iban: string): boolean {
  const compact = iban.replace(/\s+/g, "");
  const rearranged = compact.slice(4) + compact.slice(0, 4);
  const digits = [...rearranged].map((char) => parseInt(char, 36).toString()).join("");
  let remainder = 0;
  for (const digit of digits) {
    remainder = (remainder * 10 + Number(digit)) % 97;
  }
  return remainder === 1;
}

test("demo prompts are synthetic, with clearly fake EGN and BG IBAN", () => {
  assert.ok(STAFF_DEMO_PROMPTS.length >= 2);
  for (const example of STAFF_DEMO_PROMPTS) {
    assert.equal(example.synthetic, true);
    assert.ok(example.label.bg && example.label.en && example.label.de);
    if (example.fakeEgn) {
      assert.match(example.fakeEgn, /^\d{10}$/);
      // Month 99 cannot occur in a real EGN.
      assert.equal(example.fakeEgn.slice(2, 4), "99");
      assert.ok(example.prompt.includes(example.fakeEgn));
      assert.ok(example.prompt.startsWith("[СИНТЕТИЧНИ ДАННИ]"));
    }
    if (example.fakeIban) {
      assert.match(example.fakeIban.replace(/\s+/g, ""), /^BG\d{2}TEST\d{14}$/);
      assert.equal(ibanIsValid(example.fakeIban), true);
      assert.ok(example.prompt.includes(example.fakeIban));
    }
    assert.equal(/@(?!example\.org)/.test(example.prompt), false);
  }
});

test("mock redaction masks EGN, BG IBAN, Cyrillic names and cities with correct offsets", () => {
  const sample = STAFF_DEMO_PROMPTS[0]!.prompt;
  const result = redactText(sample);
  const byType = new Map(result.entities.map((entity) => [entity.entity_type, entity.span]));
  assert.equal(byType.get("EGN_BG"), "9999999999");
  assert.equal(byType.get("IBAN_CODE"), FAKE_IBAN_1);
  assert.equal(byType.get("PERSON"), "Иван Тестов Примеров");
  assert.equal(byType.get("LOCATION"), "София");
  assert.equal(result.entities.some((entity) => entity.span.includes("СИНТЕТИЧНИ")), false);
  for (const entity of result.entities) {
    assert.equal(sample.slice(entity.start_utf16, entity.end_utf16), entity.span);
    assert.equal(result.anonymized_text.slice(entity.token_start_utf16, entity.token_end_utf16), entity.token);
  }
  assert.equal(result.anonymized_text.includes("9999999999"), false);
  assert.equal(result.anonymized_text.includes("Иван"), false);
});

test("Cyrillic highlighting slices by UTF-16 offsets even after an emoji", () => {
  const text = "📎 Молба от Мария Пробна Демова, ЕГН 8899999990";
  const result = redactText(text);
  const person = result.entities.find((entity) => entity.entity_type === "PERSON");
  assert.ok(person);
  assert.notEqual(person.start, person.start_utf16);
  const segments = segmentText(
    text,
    result.entities.map((entity) => ({
      start: entity.start_utf16,
      end: entity.end_utf16,
      entityType: entity.entity_type,
      token: entity.token,
    })),
  );
  const marked = segments.filter((segment) => segment.span).map((segment) => segment.text);
  assert.deepEqual(marked, ["Мария Пробна Демова", "8899999990"]);
  assert.equal(segments.map((segment) => segment.text).join(""), text);
});

test("mock answers are Bulgarian and round-trip through answer highlights", () => {
  const { entities } = redactText(STAFF_DEMO_PROMPTS[0]!.prompt);
  const restored = mockRestoredAnswer(entities, "bg");
  const raw = mockRawModelAnswer(entities, "bg");
  assert.match(restored, /Иван Тестов Примеров/);
  assert.match(restored, /Служител трябва да провери/);
  assert.equal(raw.includes("Иван"), false);
  assert.match(raw, /\[EGN_BG_1\]/);
  const pair = buildAnswerHighlights(restored, raw, entities);
  assert.ok(pair.restoredSpans.some((span) => span.entityType === "EGN_BG"));
  assert.ok(pair.rawModelSpans.some((span) => span.token === "[PERSON_1]"));
});

test("German sample is unchanged by the Bulgarian recognizers", () => {
  const sample =
    "Draft a short reply to Jörg Müller (joerg.mueller@nordbank.example, +49 170 1234567). The IBAN is DE89 3704 0044 0532 0130 00. He will be in München on 14.03.2026.";
  assert.equal(redactText(sample).entities.some((entity) => entity.entity_type === "EGN_BG"), false);
});

test("staff config: BgGPT alias first, admin flag, detection locale", () => {
  assert.equal(resolveBgGptAlias(undefined), BGGPT_ALIAS_PLACEHOLDER);
  assert.equal(resolveBgGptAlias("  "), "bggpt");
  assert.equal(resolveBgGptAlias("bggpt-9b"), "bggpt-9b");
  assert.equal(resolveBgGptAlias("bad alias!"), "bggpt");
  assert.deepEqual(staffModelOptions("bggpt", ["grok-4", "bggpt", "grok"]), ["bggpt", "grok-4", "grok"]);
  assert.equal(resolveAdminContext(undefined), false);
  assert.equal(resolveAdminContext("false"), false);
  assert.equal(resolveAdminContext("true"), true);
  assert.equal(staffDetectionLocale("bg"), "bg");
  assert.equal(staffDetectionLocale("de"), "de-DE");
});
