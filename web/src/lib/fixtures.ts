import type {
  AnonymizationEvent,
  AnonymizationEventQuery,
  ConfigHistoryItem,
  ConfigHistoryQuery,
} from "@/lib/types";

const PATTERNS: AnonymizationEvent["entity_types"][] = [
  [
    { type: "PERSON", count: 1 },
    { type: "EMAIL_ADDRESS", count: 1 },
  ],
  [{ type: "IBAN_CODE", count: 1 }],
  [
    { type: "PHONE_NUMBER", count: 1 },
    { type: "LOCATION", count: 1 },
  ],
  [{ type: "DATE_TIME", count: 1 }],
  [{ type: "CREDIT_CARD", count: 1 }],
  [
    { type: "PERSON", count: 1 },
    { type: "IBAN_CODE", count: 1 },
    { type: "DATE_TIME", count: 1 },
  ],
];

const NEWEST = Date.parse("2026-10-30T15:00:00Z");

export interface FixtureRow {
  rowId: number;
  event: AnonymizationEvent;
}

export const FIXTURE_ROWS: FixtureRow[] = Array.from({ length: 30 }, (_, index) => {
  const decision = index % 11 === 0 ? "BLOCK" : index % 7 === 0 ? "PASS" : "ANONYMIZE";
  const entityTypes = decision === "PASS" ? [] : (PATTERNS[index % PATTERNS.length] ?? []);
  const tokenCount = entityTypes.reduce((sum, entity) => sum + entity.count, 0);
  return {
    rowId: index + 1,
    event: {
      request_id: `req_demo_${String(index + 1).padStart(2, "0")}`,
      timestamp: new Date(NEWEST - index * 5 * 60 * 60 * 1000).toISOString(),
      tenant_id: index % 3 === 0 ? "contoso" : "default",
      model: index % 2 === 0 ? "grok-4" : "grok-3",
      locale: index % 2 === 0 ? "de-DE" : "en",
      entity_types: entityTypes,
      token_count: decision === "PASS" ? 0 : tokenCount,
      decision,
    },
  };
});

export const ANONYMIZATION_EVENTS: AnonymizationEvent[] = FIXTURE_ROWS.map((row) => row.event);

export const CONFIG_HISTORY: ConfigHistoryItem[] = [
  {
    event_id: "cfg_01",
    timestamp: "2026-10-28T09:12:00.000Z",
    tenant_id: "default",
    change_type: "policy_update",
    operator_id: "ops-berlin",
    prev_value_hash: "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    new_value_hash: "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
  },
  {
    event_id: "cfg_02",
    timestamp: "2026-10-27T16:40:00.000Z",
    tenant_id: "default",
    change_type: "locale_bundle",
    operator_id: "ops-berlin",
    prev_value_hash: "60303ae22b998861bce3b28f33eec1be758a213c86c93c076dbe9f558c11c752",
    new_value_hash: "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
  },
  {
    event_id: "cfg_03",
    timestamp: "2026-10-26T11:05:00.000Z",
    tenant_id: "contoso",
    change_type: "model_alias",
    operator_id: "auditor",
    prev_value_hash: "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
    new_value_hash: "6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b",
  },
  {
    event_id: "cfg_04",
    timestamp: "2026-10-24T08:20:00.000Z",
    tenant_id: "default",
    change_type: "policy_update",
    operator_id: "auditor",
    prev_value_hash: "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d",
    new_value_hash: "e7f6c011776e8db7cd330b54174fd76f7d0216b612387a5ffcfb81e6f0919683",
  },
];

function inRange(timestamp: string, from?: string, to?: string): boolean {
  const value = Date.parse(timestamp);
  if (Number.isNaN(value)) {
    return false;
  }
  if (from && value < Date.parse(from)) {
    return false;
  }
  if (to && value > Date.parse(to)) {
    return false;
  }
  return true;
}

export function filterFixtureRows(
  rows: FixtureRow[],
  query: Pick<AnonymizationEventQuery, "date_from" | "date_to" | "entity_type">,
  callerTenant?: string,
): FixtureRow[] {
  return rows.filter((row) => {
    if (callerTenant && row.event.tenant_id !== callerTenant) {
      return false;
    }
    if (query.entity_type && !row.event.entity_types.some((entity) => entity.type === query.entity_type)) {
      return false;
    }
    return inRange(row.event.timestamp, query.date_from, query.date_to);
  });
}

export interface ConfigFixture {
  rowId: number;
  item: ConfigHistoryItem;
}

export const CONFIG_FIXTURES: ConfigFixture[] = CONFIG_HISTORY.map((item, index) => ({
  rowId: index + 1,
  item,
}));

export function filterConfig(
  rows: ConfigFixture[],
  query: Pick<ConfigHistoryQuery, "event_type" | "operator_id" | "date_from" | "date_to">,
  callerTenant?: string,
): ConfigFixture[] {
  return rows.filter((row) => {
    if (callerTenant && row.item.tenant_id !== callerTenant) {
      return false;
    }
    if (query.event_type && row.item.change_type !== query.event_type) {
      return false;
    }
    if (query.operator_id && row.item.operator_id !== query.operator_id) {
      return false;
    }
    return inRange(row.item.timestamp, query.date_from, query.date_to);
  });
}

export function toCsv(events: AnonymizationEvent[]): string {
  const headers = [
    "request_id",
    "timestamp",
    "tenant_id",
    "model",
    "locale",
    "decision",
    "token_count",
    "entity_types",
  ];
  const lines = [headers.join(",")];
  for (const event of events) {
    const types = [...event.entity_types].sort((a, b) => a.type.localeCompare(b.type));
    const cells = [
      event.request_id ?? "",
      event.timestamp,
      event.tenant_id,
      event.model ?? "",
      event.locale ?? "",
      event.decision ?? "",
      event.token_count == null ? "" : String(event.token_count),
      JSON.stringify(types),
    ];
    lines.push(cells.map(csvCell).join(","));
  }
  return `${lines.join("\n")}\n`;
}

function csvCell(value: string): string {
  if (/[",\n\r]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}
