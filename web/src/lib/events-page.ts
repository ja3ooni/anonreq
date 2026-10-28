import type { AnonymizationEventSort } from "@/lib/types";

/**
 * Pagination for GET /v1/admin/anonymization-events.
 *
 * The screen only sees an opaque cursor and `next_cursor`. It never
 * sends or reads `offset`.
 *
 * Target wire (keyset, PR #5):
 *   ?cursor=&limit=&sort=&date_from=&date_to=&entity_type=
 *   → { total, limit, next_cursor, items }
 *
 * `tenant_id` is the caller (`X-AnonReq-Tenant-ID`), not a query filter.
 *
 * If a response still includes `offset` and omits `next_cursor`, the
 * adapter mints a bridge cursor and the next request sends `offset`
 * as well as dropping that bridge token. That translation stays here.
 */

const MOCK_PREFIX = "cur.";
const OFFSET_BRIDGE_PREFIX = "off.";

export interface EventsCursorQuery {
  date_from?: string;
  date_to?: string;
  entity_type?: string;
  sort: AnonymizationEventSort;
  limit: number;
  cursor?: string;
}

export function mockCursor(index: number): string {
  return `${MOCK_PREFIX}${index.toString(36)}`;
}

export function sliceByCursor<T>(
  items: T[],
  cursor: string | undefined,
  limit: number,
): { items: T[]; next_cursor: string | null } {
  const start = mockCursorIndex(cursor);
  const page = items.slice(start, start + limit);
  const next = start + page.length;
  return {
    items: page,
    next_cursor: next < items.length ? mockCursor(next) : null,
  };
}

export function nextCursorFromOffset(offset: number, pageLength: number, total: number): string | null {
  const next = offset + pageLength;
  if (next >= total) {
    return null;
  }
  return `${OFFSET_BRIDGE_PREFIX}${next}`;
}

/** Query string for the gateway. No tenant filter. No offset unless bridging. */
export function eventsWireQuery(query: EventsCursorQuery): Record<string, string | undefined> {
  const bridged = bridgeOffset(query.cursor);
  return {
    date_from: query.date_from,
    date_to: query.date_to,
    entity_type: query.entity_type,
    sort: query.sort,
    limit: String(query.limit),
    cursor: bridged == null ? query.cursor : undefined,
    offset: bridged == null ? undefined : String(bridged),
  };
}

function mockCursorIndex(cursor: string | undefined): number {
  if (!cursor || !cursor.startsWith(MOCK_PREFIX)) {
    return 0;
  }
  const index = Number.parseInt(cursor.slice(MOCK_PREFIX.length), 36);
  return Number.isInteger(index) && index >= 0 ? index : 0;
}

function bridgeOffset(cursor: string | undefined): number | undefined {
  if (!cursor?.startsWith(OFFSET_BRIDGE_PREFIX)) {
    return undefined;
  }
  const offset = Number(cursor.slice(OFFSET_BRIDGE_PREFIX.length));
  return Number.isInteger(offset) && offset >= 0 ? offset : undefined;
}
