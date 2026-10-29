import assert from "node:assert/strict";
import test from "node:test";

import { buildGlassFlowBundle } from "./glassflow.ts";
import { redactText } from "./redact.ts";

test("GlassFlow Rius & Tares bundle contains zero cleartext PII and preserves entity metadata", () => {
  const rawPrompt =
    "SEPA Ticket: Jörg Müller, IBAN DE89 3704 0044 0532 0130 00, Key sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz123456";
  const redacted = redactText(rawPrompt);
  const bundle = buildGlassFlowBundle({
    mode: "full_chat",
    scenarioId: "bank",
    filename: "sepa-ticket.txt",
    tenantId: "default",
    locale: "de-DE",
    model: "grok-4",
    latencyMs: 120,
    preview: {
      request_id: "req_gf_01",
      locale: "de-DE",
      classification: redacted.classification,
      highest_entity: redacted.highest_entity,
      anonymized_text: redacted.anonymized_text,
      anonymized_messages: null,
      entities: redacted.entities,
    },
    chat: {
      answer: "Restored reply",
      model: "grok-4",
      completionId: "chatcmpl_1",
      headers: {
        requestId: "req_gf_01",
        entityCount: String(redacted.entities.length),
        classification: redacted.classification,
        highestEntity: redacted.highest_entity,
        processed: "true",
      },
    },
  });

  const serialized = JSON.stringify(bundle);
  assert.equal(serialized.includes("Jörg Müller"), false);
  assert.equal(serialized.includes("DE89 3704"), false);
  assert.equal(serialized.includes("sk-proj-AbCd"), false);
  assert.equal(bundle.rius.spans.length, 3);
  assert.equal(bundle.tares.data.decision, "ANONYMIZE");
  assert.equal(bundle.tares.data.non_reversible_masked, 1);
  assert.ok(bundle.tares.data.sanitized_context.includes("[IBAN_CODE_1]"));
});

