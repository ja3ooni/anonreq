import assert from "node:assert/strict";
import test from "node:test";

import { redactText } from "./redact.ts";
import { BUYER_SCENARIOS, evaluateComplianceVerdict } from "./scenarios.ts";

test("all regulated buyer scenarios detect PII and evaluate as governed or credential_risk", () => {
  for (const scenario of BUYER_SCENARIOS) {
    const redaction = redactText(scenario.de.prompt);
    const verdict = evaluateComplianceVerdict({
      request_id: "req_test",
      locale: scenario.recommendedLocale,
      classification: redaction.classification,
      highest_entity: redaction.highest_entity,
      anonymized_text: redaction.anonymized_text,
      anonymized_messages: null,
      entities: redaction.entities,
    });

    if (scenario.id === "clean") {
      assert.equal(verdict.state, "clean");
      assert.equal(verdict.okForCleartextAi, true);
      assert.equal(verdict.totalEntities, 0);
    } else if (scenario.id === "agent_sec") {
      assert.equal(verdict.state, "credential_risk");
      assert.equal(verdict.okForCleartextAi, false);
      assert.equal(verdict.okViaAnonReq, true);
      assert.ok(verdict.nonReversibleCount >= 1);
    } else {
      assert.equal(verdict.state, "governed");
      assert.equal(verdict.okForCleartextAi, false);
      assert.equal(verdict.okViaAnonReq, true);
      assert.ok(verdict.totalEntities >= 3, `Expected >= 3 entities for ${scenario.id}`);
    }
  }
});

test("fail-closed verdict is returned on 503 detector outage", () => {
  const verdict = evaluateComplianceVerdict(null, 503);
  assert.equal(verdict.state, "fail_closed");
  assert.equal(verdict.okForCleartextAi, false);
  assert.equal(verdict.okViaAnonReq, false);
});

