import assert from "node:assert/strict";
import test from "node:test";

import {
  InvalidEventCursorError,
  encodeEventCursor,
  eventsWireQuery,
  pageByKeyset,
  type KeyedRow,
} from "./events-page.ts";

const rows: KeyedRow<string>[] = [
  { rowId: 1, timestamp: "2026-10-30T15:00:00.000Z", item: "newest-low-id" },
  { rowId: 5, timestamp: "2026-10-30T15:00:00.000Z", item: "newest-high-id" },
  { rowId: 2, timestamp: "2026-10-30T10:00:00.000Z", item: "middle" },
  { rowId: 3, timestamp: "2026-10-30T05:00:00.000Z", item: "oldest" },
];

test("desc pages use timestamp|id and stop on a short page", () => {
  const first = pageByKeyset(rows, { sort: "timestamp:desc", limit: 2 });
  assert.deepEqual(first.items, ["newest-high-id", "newest-low-id"]);
  assert.equal(first.next_cursor, encodeEventCursor("2026-10-30T15:00:00.000Z", 1));

  const second = pageByKeyset(rows, {
    sort: "timestamp:desc",
    limit: 2,
    cursor: first.next_cursor ?? undefined,
  });
  assert.deepEqual(second.items, ["middle", "oldest"]);
  assert.equal(second.next_cursor, encodeEventCursor("2026-10-30T05:00:00.000Z", 3));

  const last = pageByKeyset(rows, {
    sort: "timestamp:desc",
    limit: 2,
    cursor: second.next_cursor ?? undefined,
  });
  assert.deepEqual(last.items, []);
  assert.equal(last.next_cursor, null);
});

test("asc cursor walks forward by timestamp then id", () => {
  const first = pageByKeyset(rows, { sort: "timestamp:asc", limit: 1 });
  assert.deepEqual(first.items, ["oldest"]);
  const second = pageByKeyset(rows, {
    sort: "timestamp:asc",
    limit: 1,
    cursor: first.next_cursor ?? undefined,
  });
  assert.deepEqual(second.items, ["middle"]);
});

test("wire query is cursor, limit, and sort only", () => {
  const query = eventsWireQuery({
    sort: "timestamp:desc",
    limit: 50,
    cursor: "2026-10-30T10:00:00.000Z|2",
    entity_type: "PERSON",
  });
  assert.equal(query.cursor, "2026-10-30T10:00:00.000Z|2");
  assert.equal(query.limit, "50");
  assert.equal(query.sort, "timestamp:desc");
  assert.equal("offset" in query, false);
  assert.equal("tenant_id" in query, false);
});

test("a cursor without timestamp|id is rejected", () => {
  assert.throws(
    () => pageByKeyset(rows, { sort: "timestamp:desc", limit: 2, cursor: "not-a-cursor" }),
    InvalidEventCursorError,
  );
});
