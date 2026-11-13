import assert from "node:assert/strict";
import test from "node:test";

import { FAKE_IBAN_1, STAFF_DEMO_PROMPTS } from "./bg-demo-prompts.ts";
import { egnBirthDate, isValidEgn } from "./egn.ts";
import { buildAnswerHighlights, mockRawModelAnswer, mockRestoredAnswer, redactText } from "./redact.ts";
import { segmentText } from "./segments.ts";
import {
  BGGPT_ALIAS_PLACEHOLDER,
  mockModelList,
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

test("demo prompts are synthetic, with obviously fake but valid EGNs and BG IBANs", () => {
  assert.ok(STAFF_DEMO_PROMPTS.length >= 2);
  for (const example of STAFF_DEMO_PROMPTS) {
    assert.equal(example.synthetic, true);
    assert.ok(example.label.bg && example.label.en && example.label.de);
    if (example.fakeEgn) {
      assert.match(example.fakeEgn, /^\d{10}$/);
      // Passes the month + check-digit validation, but the birth year is 2099.
      assert.equal(isValidEgn(example.fakeEgn), true);
      assert.equal(egnBirthDate(example.fakeEgn)?.year, 2099);
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
  const result = redactText(sample, null, "bg");
  const byType = new Map(result.entities.map((entity) => [entity.entity_type, entity.span]));
  assert.equal(byType.get("EGN_BG"), "9952319991");
  assert.equal(byType.get("IBAN_CODE"), FAKE_IBAN_1);
  assert.equal(byType.get("PERSON"), "Иван Тестов Примеров");
  assert.equal(byType.get("LOCATION"), "София");
  assert.equal(result.entities.some((entity) => entity.span.includes("СИНТЕТИЧНИ")), false);
  for (const entity of result.entities) {
    assert.equal(sample.slice(entity.start_utf16, entity.end_utf16), entity.span);
    assert.equal(result.anonymized_text.slice(entity.token_start_utf16, entity.token_end_utf16), entity.token);
  }
  assert.equal(result.anonymized_text.includes("9952319991"), false);
  assert.equal(result.anonymized_text.includes("Иван"), false);
});

test("Cyrillic highlighting slices by UTF-16 offsets even after an emoji", () => {
  const text = "📎 Молба от Мария Пробна Демова, ЕГН 9951019990";
  const result = redactText(text, null, "bg");
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
  assert.deepEqual(marked, ["Мария Пробна Демова", "9951019990"]);
  assert.equal(segments.map((segment) => segment.text).join(""), text);
});

test("mock answers are Bulgarian and round-trip through answer highlights", () => {
  const { entities } = redactText(STAFF_DEMO_PROMPTS[0]!.prompt, null, "bg");
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

test("EGN is detected only for the bg locale and only when valid", () => {
  const valid = "ЕГН 9952319991 по молбата";
  assert.ok(redactText(valid, null, "bg").entities.some((entity) => entity.entity_type === "EGN_BG"));
  assert.ok(redactText(valid, null, "bg-BG").entities.some((entity) => entity.entity_type === "EGN_BG"));
  assert.equal(redactText(valid, null, "en").entities.some((entity) => entity.entity_type === "EGN_BG"), false);
  assert.equal(redactText(valid, null, "de-DE").entities.some((entity) => entity.entity_type === "EGN_BG"), false);
  // Bad check digit, impossible month, impossible day.
  for (const bad of ["9952319990", "9999999999", "9952329991", "0102300000"]) {
    assert.equal(isValidEgn(bad), false, bad);
    assert.equal(redactText(`ЕГН ${bad}`, null, "bg").entities.some((entity) => entity.entity_type === "EGN_BG"), false, bad);
  }
});

test("EGN validation decodes the century from the month", () => {
  assert.deepEqual(egnBirthDate("7501010010"), { year: 1975, month: 1, day: 1 });
  assert.deepEqual(egnBirthDate("9952319991"), { year: 2099, month: 12, day: 31 });
  assert.deepEqual(egnBirthDate("0422290000"), { year: 1804, month: 2, day: 29 });
  assert.equal(egnBirthDate("0022290000"), null); // 1800 is not a leap year
  assert.equal(egnBirthDate("0102290000"), null);
});

test("staff config: alias acceptance and no BgGPT injection outside mock", () => {
  assert.deepEqual(resolveBgGptAlias(undefined), { alias: BGGPT_ALIAS_PLACEHOLDER, accepted: false });
  assert.deepEqual(resolveBgGptAlias("  "), { alias: "bggpt", accepted: false });
  assert.deepEqual(resolveBgGptAlias("bggpt-9b"), { alias: "bggpt-9b", accepted: true });
  // Setting the placeholder explicitly does not confirm the alias.
  assert.deepEqual(resolveBgGptAlias("bggpt"), { alias: "bggpt", accepted: false });
  assert.deepEqual(resolveBgGptAlias("bad alias!"), { alias: "bggpt", accepted: false });
  assert.deepEqual(staffModelOptions("bggpt", ["grok-4", "bggpt", "grok"]), ["bggpt", "grok-4", "grok"]);
  assert.deepEqual(staffModelOptions("bggpt", ["grok-4", "grok"]), ["grok-4", "grok"]);
  assert.deepEqual(mockModelList("bggpt", ["grok-4", "grok"]), ["bggpt", "grok-4", "grok"]);
  assert.equal(staffDetectionLocale("bg"), "bg");
  assert.equal(staffDetectionLocale("de"), "de-DE");
});
