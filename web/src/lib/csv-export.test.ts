import assert from "node:assert/strict";
import test from "node:test";

import { configHistoryCsv, inspectExportCsv } from "./csv-export.ts";

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

test("config history csv is built from loaded rows", () => {
  const csv = configHistoryCsv([
    {
      event_id: "cfg_01",
      timestamp: "2026-10-28T09:12:00.000Z",
      tenant_id: "default",
      change_type: "policy_update",
      operator_id: "ops-berlin",
      prev_value_hash: "abc",
      new_value_hash: "def",
    },
  ]);
  assert.equal(csv.startsWith("event_id,timestamp,tenant_id,change_type,operator_id,prev_value_hash,new_value_hash\n"), true);
  assert.equal(csv.includes("cfg_01"), true);
  assert.equal(csv.includes("policy_update"), true);
});

test("a complete export is left unchanged", () => {
  const csv = `${HEADER}\nreq_1,2026-10-30T15:00:00.000Z,default,grok-4,en,PASS,0,[]\n`;
  const result = inspectExportCsv(csv);
  assert.equal(result.failed, false);
  assert.equal(result.dataRows, 1);
});
