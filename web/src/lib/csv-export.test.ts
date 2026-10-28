import assert from "node:assert/strict";
import test from "node:test";

import { inspectExportCsv } from "./csv-export.ts";

const HEADER = "request_id,timestamp,tenant_id,model,locale,decision,token_count,entity_types";

test("a trailing export_failed row is removed and reported", () => {
  const csv = [
    HEADER,
    'req_1,2026-10-30T15:00:00.000Z,default,grok-4,de-DE,ANONYMIZE,1,"[{""type"":""PERSON"",""count"":1}]"',
    "#error,,,,,export_failed,",
  ].join("\n");
  const result = inspectExportCsv(csv);
  assert.equal(result.failed, true);
  assert.equal(result.dataRows, 1);
  assert.equal(result.csv.includes("#error"), false);
  assert.equal(result.csv.includes("req_1"), true);
  assert.equal(result.csv.includes("export_failed"), false);
});

test("a formula-escaped #error trailer is still a failure", () => {
  const result = inspectExportCsv(`${HEADER}\n'#error,,,,,export_failed,\n`);
  assert.equal(result.failed, true);
  assert.equal(result.dataRows, 0);
});

test("a complete export is left unchanged", () => {
  const csv = `${HEADER}\nreq_1,2026-10-30T15:00:00.000Z,default,grok-4,en,PASS,0,[]\n`;
  const result = inspectExportCsv(csv);
  assert.equal(result.failed, false);
  assert.equal(result.dataRows, 1);
});
