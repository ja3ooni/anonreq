import assert from "node:assert/strict";
import test from "node:test";

import { eventsWireQuery, nextCursorFromOffset, sliceByCursor } from "./events-page.ts";

test("mock pages expose next_cursor and stop at the end", () => {
  const rows = ["a", "b", "c", "d", "e"];
  const first = sliceByCursor(rows, undefined, 2);
  assert.deepEqual(first.items, ["a", "b"]);
  assert.equal(typeof first.next_cursor, "string");

  const second = sliceByCursor(rows, first.next_cursor ?? undefined, 2);
  assert.deepEqual(second.items, ["c", "d"]);

  const last = sliceByCursor(rows, second.next_cursor ?? undefined, 2);
  assert.deepEqual(last.items, ["e"]);
  assert.equal(last.next_cursor, null);
});

test("wire query sends cursor and not offset", () => {
  const query = eventsWireQuery({
    sort: "timestamp:desc",
    limit: 10,
    cursor: "cur.a",
    entity_type: "PERSON",
  });
  assert.equal(query.cursor, "cur.a");
  assert.equal(query.offset, undefined);
  assert.equal(query.entity_type, "PERSON");
  assert.equal("tenant_id" in query, false);
});

test("offset bodies become a bridge cursor the UI can load-more", () => {
  const next = nextCursorFromOffset(0, 10, 30);
  assert.equal(next, "off.10");
  const query = eventsWireQuery({
    sort: "timestamp:asc",
    limit: 10,
    cursor: next ?? undefined,
  });
  assert.equal(query.offset, "10");
  assert.equal(query.cursor, undefined);
  assert.equal(nextCursorFromOffset(20, 10, 30), null);
});
