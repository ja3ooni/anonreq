import assert from "node:assert/strict";
import test from "node:test";

import { buildAnswerHighlights, mockRawModelAnswer, mockRestoredAnswer, redactText } from "./redact.ts";

const SAMPLE =
  "Draft a short reply to Jörg Müller (joerg.mueller@nordbank.example, +49 170 1234567). The IBAN is DE89 3704 0044 0532 0130 00. He will be in München on 14.03.2026.";

test("redaction uses TYPE_N tokens and round-trips indexes", () => {
  const result = redactText(SAMPLE);
  const tokens = result.entities.map((entity) => entity.token);
  assert.deepEqual(tokens, [
    "[PERSON_1]",
    "[EMAIL_ADDRESS_1]",
    "[PHONE_NUMBER_1]",
    "[IBAN_CODE_1]",
    "[LOCATION_1]",
    "[DATE_TIME_1]",
  ]);
  assert.equal(result.classification, "RESTRICTED");
  assert.equal(result.highest_entity, "IBAN_CODE");
  assert.equal(result.anonymized_text.includes("joerg.mueller@nordbank.example"), false);
  assert.equal(result.anonymized_text.includes("DE89"), false);
  for (const entity of result.entities) {
    assert.equal(entity.message_index, null);
    assert.equal(SAMPLE.slice(entity.start_utf16, entity.end_utf16), entity.span);
    assert.equal([...SAMPLE].slice(entity.start, entity.end).join(""), entity.span);
    assert.equal(result.anonymized_text.slice(entity.token_start_utf16, entity.token_end_utf16), entity.token);
    assert.equal([...result.anonymized_text].slice(entity.token_start, entity.token_end).join(""), entity.token);
  }
});

test("utf-16 offsets diverge from code points after a supplementary character", () => {
  const text = "Note 😀 for Jörg Müller";
  const result = redactText(text);
  const person = result.entities.find((entity) => entity.entity_type === "PERSON");
  assert.ok(person);
  assert.equal(text.slice(person.start_utf16, person.end_utf16), "Jörg Müller");
  assert.notEqual(person.start, person.start_utf16);
  assert.equal([...text].slice(person.start, person.end).join(""), "Jörg Müller");
  assert.equal(result.anonymized_text.slice(person.token_start_utf16, person.token_end_utf16), person.token);
});

test("The IBAN is not treated as a person", () => {
  const result = redactText("The IBAN is DE89 3704 0044 0532 0130 00.");
  assert.equal(
    result.entities.some((entity) => entity.entity_type === "PERSON"),
    false,
  );
  assert.equal(result.entities[0]?.entity_type, "IBAN_CODE");
});

test("the same value reuses one token", () => {
  const result = redactText("Berlin then Berlin");
  assert.equal(result.entities.length, 2);
  assert.equal(result.entities[0]?.token, "[LOCATION_1]");
  assert.equal(result.entities[1]?.token, "[LOCATION_1]");
});

test("empty detection stays public", () => {
  const result = redactText("Explain a gateway in three sentences.");
  assert.equal(result.entities.length, 0);
  assert.equal(result.classification, "PUBLIC");
  assert.equal(result.anonymized_text, "Explain a gateway in three sentences.");
});

test("detects German insurance & tax identifiers and non-reversible API keys", () => {
  const text =
    "Versicherte: Anna Schmidt, KVNR: A123456780, Personalausweis: L01X00T471, Steuer-ID: 86095742719, Key: sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz123456";
  const result = redactText(text);
  const types = result.entities.map((entity) => entity.entity_type);
  assert.ok(types.includes("PERSON"));
  assert.ok(types.includes("KVNR"));
  assert.ok(types.includes("PERSONAL_AUSWEIS"));
  assert.ok(types.includes("TAX_ID_DE"));
  assert.ok(types.includes("API_KEY"));
  assert.equal(result.classification, "HIGHLY_RESTRICTED");
  assert.equal(result.highest_entity, "API_KEY");

  const rawReply = mockRawModelAnswer(result.entities, "de-DE");
  const restoredReply = mockRestoredAnswer(result.entities, "de-DE");
  assert.ok(rawReply.includes("[PERSON_1]"));
  assert.ok(rawReply.includes("[KVNR_1]"));
  assert.equal(rawReply.includes("Anna Schmidt"), false);
  assert.ok(restoredReply.includes("Anna Schmidt"));
  assert.ok(restoredReply.includes("[API_KEY_1]"));

  const highlights = buildAnswerHighlights(restoredReply, rawReply, result.entities);
  assert.ok(highlights.rawModelSpans.some((s) => s.token === "[PERSON_1]"));
  assert.ok(highlights.restoredSpans.some((s) => s.entityType === "PERSON"));
});
