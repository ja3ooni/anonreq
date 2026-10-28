import assert from "node:assert/strict";
import test from "node:test";

import { segmentText } from "./segments.ts";

test("segments keep unmatched text and skip overlaps", () => {
  const segments = segmentText("abcdef", [
    { start: 4, end: 6, entityType: "PERSON", token: "[PERSON_1]" },
    { start: 1, end: 3, entityType: "EMAIL_ADDRESS", token: "[EMAIL_ADDRESS_1]" },
    { start: 2, end: 5, entityType: "PHONE_NUMBER", token: "[PHONE_NUMBER_1]" },
  ]);
  assert.deepEqual(
    segments.map((segment) => segment.text),
    ["a", "bc", "d", "ef"],
  );
  assert.equal(segments[1]?.span?.entityType, "EMAIL_ADDRESS");
  assert.equal(segments[3]?.span?.entityType, "PERSON");
});
