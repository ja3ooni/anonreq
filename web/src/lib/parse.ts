import { headerOrNull } from "@/lib/gateway";
import type {
  AnonymizationEvent,
  AnonymizationEventPage,
  AnonymizePreviewResponse,
  ChainVerification,
  ChatCompletionResult,
  ConfigHistoryPage,
  PreviewEntity,
} from "@/lib/types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function stringField(record: Record<string, unknown>, key: string): string | null {
  const value = record[key];
  return typeof value === "string" ? value : null;
}

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function integerOrNull(value: unknown): number | null | undefined {
  if (value == null) {
    return null;
  }
  if (typeof value === "number" && Number.isInteger(value)) {
    return value;
  }
  return undefined;
}

function requiredInteger(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) ? value : null;
}

export function parsePreview(json: unknown): AnonymizePreviewResponse | null {
  if (!isRecord(json) || !Array.isArray(json.entities)) {
    return null;
  }
  const requestId = stringField(json, "request_id");
  if (!requestId) {
    return null;
  }
  if (json.anonymized_text != null && typeof json.anonymized_text !== "string") {
    return null;
  }
  let anonymizedMessages: AnonymizePreviewResponse["anonymized_messages"] = null;
  if (json.anonymized_messages != null) {
    if (!Array.isArray(json.anonymized_messages)) {
      return null;
    }
    anonymizedMessages = [];
    for (const message of json.anonymized_messages) {
      if (!isRecord(message) || typeof message.role !== "string" || typeof message.content !== "string") {
        return null;
      }
      const messageIndex = requiredInteger(message.message_index);
      if (messageIndex == null) {
        return null;
      }
      anonymizedMessages.push({
        role: message.role,
        content: message.content,
        message_index: messageIndex,
      });
    }
  }
  const entities: PreviewEntity[] = [];
  for (const item of json.entities) {
    if (!isRecord(item)) {
      return null;
    }
    const entityType = stringField(item, "entity_type");
    const span = stringField(item, "span");
    const token = stringField(item, "token");
    const score = numberOrNull(item.score);
    const start = requiredInteger(item.start);
    const end = requiredInteger(item.end);
    const startUtf16 = requiredInteger(item.start_utf16);
    const endUtf16 = requiredInteger(item.end_utf16);
    const tokenStart = requiredInteger(item.token_start);
    const tokenEnd = requiredInteger(item.token_end);
    const tokenStartUtf16 = requiredInteger(item.token_start_utf16);
    const tokenEndUtf16 = requiredInteger(item.token_end_utf16);
    const messageIndex = integerOrNull(item.message_index);
    if (
      !entityType ||
      span == null ||
      !token ||
      score == null ||
      start == null ||
      end == null ||
      startUtf16 == null ||
      endUtf16 == null ||
      tokenStart == null ||
      tokenEnd == null ||
      tokenStartUtf16 == null ||
      tokenEndUtf16 == null ||
      messageIndex === undefined
    ) {
      return null;
    }
    entities.push({
      entity_type: entityType,
      span,
      token,
      score,
      start,
      end,
      start_utf16: startUtf16,
      end_utf16: endUtf16,
      token_start: tokenStart,
      token_end: tokenEnd,
      token_start_utf16: tokenStartUtf16,
      token_end_utf16: tokenEndUtf16,
      message_index: messageIndex,
    });
  }
  return {
    request_id: requestId,
    locale: stringField(json, "locale") ?? "",
    classification: stringField(json, "classification") ?? "",
    highest_entity: stringField(json, "highest_entity") ?? "",
    anonymized_text: typeof json.anonymized_text === "string" ? json.anonymized_text : null,
    anonymized_messages: anonymizedMessages,
    entities,
  };
}

export function parseEvent(json: unknown): AnonymizationEvent | null {
  if (!isRecord(json)) {
    return null;
  }
  const requestId = json.request_id == null ? null : stringField(json, "request_id");
  const timestamp = stringField(json, "timestamp");
  const tenantId = stringField(json, "tenant_id");
  if (json.request_id != null && requestId == null) {
    return null;
  }
  if (!timestamp || !tenantId || !Array.isArray(json.entity_types)) {
    return null;
  }
  const entityTypes = [];
  for (const entity of json.entity_types) {
    if (!isRecord(entity) || typeof entity.type !== "string" || typeof entity.count !== "number") {
      return null;
    }
    entityTypes.push({ type: entity.type, count: entity.count });
  }
  return {
    request_id: requestId,
    timestamp,
    tenant_id: tenantId,
    model: stringField(json, "model"),
    locale: stringField(json, "locale"),
    decision: stringField(json, "decision"),
    token_count: numberOrNull(json.token_count),
    entity_types: entityTypes,
  };
}

export function parseEventPage(json: unknown): AnonymizationEventPage | null {
  if (!isRecord(json) || !Array.isArray(json.items)) {
    return null;
  }
  const total = numberOrNull(json.total);
  const limit = numberOrNull(json.limit);
  if (total == null || limit == null) {
    return null;
  }
  const items: AnonymizationEvent[] = [];
  for (const item of json.items) {
    const event = parseEvent(item);
    if (!event) {
      return null;
    }
    items.push(event);
  }
  let nextCursor: string | null = null;
  if ("next_cursor" in json) {
    if (json.next_cursor == null) {
      nextCursor = null;
    } else if (typeof json.next_cursor === "string" && json.next_cursor.length > 0) {
      nextCursor = json.next_cursor;
    } else {
      return null;
    }
  }
  return {
    total,
    totalExact: true,
    limit,
    next_cursor: nextCursor,
    items,
    source: "events",
  };
}

export function parseLegacyExport(json: unknown): AnonymizationEvent[] | null {
  if (!Array.isArray(json)) {
    return null;
  }
  const items: AnonymizationEvent[] = [];
  for (const row of json) {
    if (!isRecord(row)) {
      return null;
    }
    const timestamp = stringField(row, "timestamp");
    const tenantId = stringField(row, "tenant_id");
    if (!timestamp || !tenantId) {
      return null;
    }
    const requestId = stringField(row, "request_id");
    const typesRaw = stringField(row, "entity_types") ?? "";
    const tokenRaw = row.token_count;
    const tokenCount =
      typeof tokenRaw === "number"
        ? tokenRaw
        : typeof tokenRaw === "string" && tokenRaw.trim() && !Number.isNaN(Number(tokenRaw))
          ? Number(tokenRaw)
          : null;
    items.push({
      request_id: requestId,
      timestamp,
      tenant_id: tenantId,
      model: stringField(row, "model"),
      locale: stringField(row, "locale"),
      entity_types: typesRaw
        .split(",")
        .map((type) => type.trim())
        .filter(Boolean)
        .map((type) => ({ type, count: 1 })),
      token_count: tokenCount,
      decision: stringField(row, "decision"),
    });
  }
  return items;
}

export function parseConfigPage(json: unknown): ConfigHistoryPage | null {
  if (!isRecord(json) || !Array.isArray(json.items)) {
    return null;
  }
  const total = numberOrNull(json.total);
  const limit = numberOrNull(json.limit);
  if (total == null || limit == null) {
    return null;
  }
  let nextCursor: string | null = null;
  if ("next_cursor" in json) {
    if (json.next_cursor == null) {
      nextCursor = null;
    } else if (typeof json.next_cursor === "string" && json.next_cursor.length > 0) {
      nextCursor = json.next_cursor;
    } else {
      return null;
    }
  }
  const items = [];
  for (const item of json.items) {
    if (!isRecord(item) || typeof item.event_id !== "string" || typeof item.tenant_id !== "string") {
      return null;
    }
    const timestamp = item.timestamp;
    items.push({
      event_id: item.event_id,
      timestamp: typeof timestamp === "string" ? timestamp : "",
      tenant_id: item.tenant_id,
      change_type: typeof item.change_type === "string" ? item.change_type : null,
      operator_id: typeof item.operator_id === "string" ? item.operator_id : null,
      prev_value_hash: typeof item.prev_value_hash === "string" ? item.prev_value_hash : null,
      new_value_hash: typeof item.new_value_hash === "string" ? item.new_value_hash : null,
    });
  }
  return { items, total, limit, next_cursor: nextCursor };
}

export function parseVerification(json: unknown): ChainVerification | null {
  if (!isRecord(json) || typeof json.is_intact !== "boolean" || typeof json.checked_count !== "number") {
    return null;
  }
  return {
    is_intact: json.is_intact,
    checked_count: json.checked_count,
    broken_at: typeof json.broken_at === "string" ? json.broken_at : null,
  };
}

export function parseChatCompletion(json: unknown, headers: Headers): ChatCompletionResult | null {
  if (!isRecord(json) || !Array.isArray(json.choices) || !json.choices[0] || !isRecord(json.choices[0])) {
    return null;
  }
  const message = json.choices[0].message;
  if (!isRecord(message)) {
    return null;
  }
  let answer: string | null = null;
  if (typeof message.content === "string") {
    answer = message.content;
  } else if (Array.isArray(message.content)) {
    const parts = message.content.flatMap((part) => {
      if (isRecord(part) && typeof part.text === "string") {
        return [part.text];
      }
      return [];
    });
    answer = parts.length > 0 ? parts.join("") : null;
  }
  if (answer == null) {
    return null;
  }
  const rawAnswer = typeof message.anonreq_raw_content === "string" ? message.anonreq_raw_content : null;
  return {
    answer,
    rawAnswer,
    model: typeof json.model === "string" ? json.model : "",
    completionId: typeof json.id === "string" ? json.id : null,
    headers: {
      requestId: headerOrNull(headers, "x-anonreq-request-id"),
      entityCount: headerOrNull(headers, "x-anonreq-entity-count"),
      classification: headerOrNull(headers, "x-anonreq-classification"),
      highestEntity: headerOrNull(headers, "x-anonreq-highest-entity"),
      processed: headerOrNull(headers, "x-anonreq-processed"),
    },
  };
}
