import { eventsWireQuery, InvalidEventCursorError, pageByKeyset } from "@/lib/events-page";
import {
  ANONYMIZATION_EVENTS,
  CONFIG_FIXTURES,
  FIXTURE_ROWS,
  filterConfig,
  filterFixtureRows,
  toCsv,
  type FixtureRow,
} from "@/lib/fixtures";
import {
  gatewayErrorMessage,
  gatewayRequest,
  isMockMode,
  readGatewayJson,
} from "@/lib/gateway";
import { GatewayRequestError } from "@/lib/gateway-error";
import { parseConfigPage, parseEventPage, parseLegacyExport, parseVerification } from "@/lib/parse";
import type {
  AnonymizationEventPage,
  AnonymizationEventQuery,
  ChainVerification,
  ConfigHistoryPage,
  ConfigHistoryQuery,
} from "@/lib/types";

export interface AnonymizationEventsClient {
  /**
   * GET /v1/admin/anonymization-events
   * Falls back to GET /v1/admin/audit/anonymization-export?format=json on 404.
   */
  list(query: AnonymizationEventQuery, tenantId: string): Promise<AnonymizationEventPage>;
  /**
   * GET /v1/admin/anonymization-events/export
   * Falls back to GET /v1/admin/audit/anonymization-export?format=csv on 404.
   */
  exportCsv(
    query: AnonymizationEventQuery,
    tenantId: string,
  ): Promise<{ body: Uint8Array; filename: string; source: "events" | "legacy-export" }>;
}

export interface ConfigHistoryClient {
  list(query: ConfigHistoryQuery, tenantId: string): Promise<ConfigHistoryPage>;
}

export interface ChainVerificationClient {
  verify(tenantId: string): Promise<ChainVerification>;
}

function cursorPage(
  rows: FixtureRow[],
  query: AnonymizationEventQuery,
  source: AnonymizationEventPage["source"],
  totalExact: boolean,
): AnonymizationEventPage {
  try {
    const page = pageByKeyset(
      rows.map((row) => ({ rowId: row.rowId, timestamp: row.event.timestamp, item: row.event })),
      query,
    );
    return {
      total: rows.length,
      totalExact,
      limit: query.limit,
      next_cursor: page.next_cursor,
      items: page.items,
      source,
    };
  } catch (error) {
    if (error instanceof InvalidEventCursorError) {
      throw new GatewayRequestError("Invalid cursor", 422);
    }
    throw error;
  }
}

function mockEvents(): AnonymizationEventsClient {
  return {
    async list(query, tenantId) {
      return cursorPage(filterFixtureRows(FIXTURE_ROWS, query, tenantId), query, "events", true);
    },
    async exportCsv(query, tenantId) {
      const filtered = filterFixtureRows(FIXTURE_ROWS, query, tenantId).map((row) => row.event);
      return {
        body: new TextEncoder().encode(toCsv(filtered)),
        filename: "anonymization-events.csv",
        source: "events",
      };
    },
  };
}

function liveEvents(): AnonymizationEventsClient {
  return {
    async list(query, tenantId) {
      const response = await gatewayRequest({
        path: "/v1/admin/anonymization-events",
        auth: "admin",
        tenantId,
        query: eventsWireQuery(query),
      });
      if (response.status === 404) {
        return legacyList(query, tenantId);
      }
      const body = await readGatewayJson(response);
      if (!response.ok) {
        throw new GatewayRequestError(gatewayErrorMessage(response.status, body.json), response.status);
      }
      const parsed = parseEventPage(body.json);
      if (!parsed) {
        throw new GatewayRequestError("Anonymization events response did not match the expected shape", 502);
      }
      return parsed;
    },
    async exportCsv(query, tenantId) {
      const response = await gatewayRequest({
        path: "/v1/admin/anonymization-events/export",
        auth: "admin",
        tenantId,
        accept: "text/csv",
        query: {
          date_from: query.date_from,
          date_to: query.date_to,
          entity_type: query.entity_type,
          sort: query.sort,
        },
      });
      if (response.status === 404) {
        return legacyCsv(query, tenantId);
      }
      if (!response.ok) {
        const body = await readGatewayJson(response);
        throw new GatewayRequestError(gatewayErrorMessage(response.status, body.json), response.status);
      }
      const bytes = new Uint8Array(await response.arrayBuffer());
      return { body: bytes, filename: "anonymization-events.csv", source: "events" };
    },
  };
}

async function legacyList(query: AnonymizationEventQuery, tenantId: string): Promise<AnonymizationEventPage> {
  const response = await gatewayRequest({
    path: "/v1/admin/audit/anonymization-export",
    auth: "admin",
    tenantId,
    query: {
      format: "json",
      date_from: query.date_from,
      date_to: query.date_to,
      entity_type: query.entity_type,
    },
  });
  const body = await readGatewayJson(response);
  if (!response.ok) {
    throw new GatewayRequestError(gatewayErrorMessage(response.status, body.json), response.status);
  }
  const rows = parseLegacyExport(body.json);
  if (!rows) {
    throw new GatewayRequestError("Anonymization export did not match the expected shape", 502);
  }
  const keyed = rows
    .filter((event) => !tenantId || event.tenant_id === tenantId)
    .filter((event) => !query.entity_type || event.entity_types.some((entity) => entity.type === query.entity_type))
    .map((event, index) => ({ rowId: index + 1, event }));
  return cursorPage(keyed, query, "legacy-export", false);
}

async function legacyCsv(
  query: AnonymizationEventQuery,
  tenantId: string,
): Promise<{ body: Uint8Array; filename: string; source: "legacy-export" }> {
  const response = await gatewayRequest({
    path: "/v1/admin/audit/anonymization-export",
    auth: "admin",
    tenantId,
    accept: "text/csv",
    query: {
      format: "csv",
      date_from: query.date_from,
      date_to: query.date_to,
      entity_type: query.entity_type,
    },
  });
  if (!response.ok) {
    const body = await readGatewayJson(response);
    throw new GatewayRequestError(gatewayErrorMessage(response.status, body.json), response.status);
  }
  return {
    body: new Uint8Array(await response.arrayBuffer()),
    filename: "anonymization-export.csv",
    source: "legacy-export",
  };
}

export function getEventsClient(): AnonymizationEventsClient {
  return isMockMode() ? mockEvents() : liveEvents();
}

function mockConfig(): ConfigHistoryClient {
  return {
    async list(query, tenantId) {
      const filtered = filterConfig(CONFIG_FIXTURES, query, tenantId);
      try {
        const page = pageByKeyset(
          filtered.map((row) => ({ rowId: row.rowId, timestamp: row.item.timestamp, item: row.item })),
          { sort: "timestamp:desc", limit: query.limit, cursor: query.cursor },
        );
        return {
          total: filtered.length,
          limit: query.limit,
          next_cursor: page.next_cursor,
          items: page.items,
        };
      } catch (error) {
        if (error instanceof InvalidEventCursorError) {
          throw new GatewayRequestError("Invalid cursor", 422);
        }
        throw error;
      }
    },
  };
}

function liveConfig(): ConfigHistoryClient {
  return {
    async list(query, tenantId) {
      const response = await gatewayRequest({
        path: "/v1/admin/audit/config-history",
        auth: "admin",
        tenantId,
        query: {
          event_type: query.event_type,
          operator_id: query.operator_id,
          date_from: query.date_from,
          date_to: query.date_to,
          limit: String(query.limit),
          cursor: query.cursor,
        },
      });
      const body = await readGatewayJson(response);
      if (!response.ok) {
        throw new GatewayRequestError(gatewayErrorMessage(response.status, body.json), response.status);
      }
      const parsed = parseConfigPage(body.json);
      if (!parsed) {
        throw new GatewayRequestError("Config history response did not match the expected shape", 502);
      }
      return parsed;
    },
  };
}

export function getConfigClient(): ConfigHistoryClient {
  return isMockMode() ? mockConfig() : liveConfig();
}

function mockVerify(): ChainVerificationClient {
  return {
    async verify(tenantId) {
      const checked = ANONYMIZATION_EVENTS.filter((event) => event.tenant_id === tenantId).length;
      return { is_intact: true, checked_count: checked, broken_at: null };
    },
  };
}

function liveVerify(): ChainVerificationClient {
  return {
    async verify(tenantId) {
      const response = await gatewayRequest({
        path: "/v1/governance/audit/verify",
        auth: "user",
        tenantId,
        query: { tenant_id: tenantId },
      });
      const body = await readGatewayJson(response);
      if (!response.ok) {
        throw new GatewayRequestError(gatewayErrorMessage(response.status, body.json), response.status);
      }
      const parsed = parseVerification(body.json);
      if (!parsed) {
        throw new GatewayRequestError("Chain verification response did not match the expected shape", 502);
      }
      return parsed;
    },
  };
}

export function getVerifyClient(): ChainVerificationClient {
  return isMockMode() ? mockVerify() : liveVerify();
}
