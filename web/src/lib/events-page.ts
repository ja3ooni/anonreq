import type { AnonymizationEventSort } from "@/lib/types";

/**
 * Keyset pagination for GET /v1/admin/anonymization-events.
 *
 *   ?cursor=<timestamp|id>&limit=50&sort=timestamp:desc|asc
 *   → { total, limit, next_cursor, items }
 *
 * `next_cursor` is `timestamp|id` of the last row when the page is full,
 * and null on the last page. There is no offset.
 */

export interface KeyedRow<T> {
  rowId: number;
  timestamp: string;
  item: T;
}

export interface KeysetQuery {
  sort: AnonymizationEventSort;
  limit: number;
  cursor?: string;
}

export interface KeysetPage<T> {
  items: T[];
  next_cursor: string | null;
}

export class InvalidEventCursorError extends Error {
  constructor() {
    super("Invalid cursor");
    this.name = "InvalidEventCursorError";
  }
}

export function encodeEventCursor(timestamp: string, rowId: number): string {
  return `${timestamp}|${rowId}`;
}

export function decodeEventCursor(cursor: string): { timestamp: string; rowId: number } {
  const splitAt = cursor.lastIndexOf("|");
  if (splitAt <= 0 || splitAt === cursor.length - 1) {
    throw new InvalidEventCursorError();
  }
  const timestamp = cursor.slice(0, splitAt);
  const rowId = Number(cursor.slice(splitAt + 1));
  if (!timestamp || !Number.isInteger(rowId) || rowId < 1 || Number.isNaN(Date.parse(timestamp))) {
    throw new InvalidEventCursorError();
  }
  return { timestamp, rowId };
}

/**
 * Page rows the way the gateway does: timestamp then id, descending by default.
 * A full page (length === limit) carries `next_cursor`. A short page is the last.
 */
export function pageByKeyset<T>(rows: KeyedRow<T>[], query: KeysetQuery): KeysetPage<T> {
  const cursor = query.cursor ? decodeEventCursor(query.cursor) : null;
  const direction = query.sort === "timestamp:asc" ? 1 : -1;
  const sorted = [...rows].sort((left, right) => {
    const delta = Date.parse(left.timestamp) - Date.parse(right.timestamp);
    if (delta !== 0) {
      return delta * direction;
    }
    return (left.rowId - right.rowId) * direction;
  });
  const rest = cursor
    ? sorted.filter((row) => isAfterCursor(row, cursor, query.sort))
    : sorted;
  const page = rest.slice(0, query.limit);
  const last = page.at(-1);
  const nextCursor =
    page.length < query.limit || !last ? null : encodeEventCursor(last.timestamp, last.rowId);
  return {
    items: page.map((row) => row.item),
    next_cursor: nextCursor,
  };
}

export function eventsWireQuery(query: {
  date_from?: string;
  date_to?: string;
  entity_type?: string;
  sort: AnonymizationEventSort;
  limit: number;
  cursor?: string;
}): Record<string, string | undefined> {
  return {
    date_from: query.date_from,
    date_to: query.date_to,
    entity_type: query.entity_type,
    sort: query.sort,
    limit: String(query.limit),
    cursor: query.cursor,
  };
}

function isAfterCursor(
  row: KeyedRow<unknown>,
  cursor: { timestamp: string; rowId: number },
  sort: AnonymizationEventSort,
): boolean {
  const rowTime = Date.parse(row.timestamp);
  const cursorTime = Date.parse(cursor.timestamp);
  if (sort === "timestamp:asc") {
    return rowTime > cursorTime || (rowTime === cursorTime && row.rowId > cursor.rowId);
  }
  return rowTime < cursorTime || (rowTime === cursorTime && row.rowId < cursor.rowId);
}
