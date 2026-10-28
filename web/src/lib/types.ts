/**
 * Wire types for gateway calls the demo UI depends on.
 *
 * POST /v1/debug/anonymize-preview and GET /v1/admin/anonymization-events
 * are added in a separate change. This UI types them and does not implement
 * them in the Python gateway. A 404 means "not enabled yet".
 */

export interface ChatMessage {
  role: string;
  content: string;
}

/**
 * Body for POST /v1/debug/anonymize-preview.
 * Send `prompt` or `messages`, not a provider call. There is no `complete` flag.
 * A prompt-only body fills `anonymized_text` and leaves `anonymized_messages` null.
 */
export interface AnonymizePreviewRequest {
  messages?: ChatMessage[];
  prompt?: string;
}

/** Code-point offsets plus UTF-16 twins. Token offsets index the anonymized text. */
export interface PreviewEntity {
  entity_type: string;
  /** Original span text. The field name is `span`, not `original`. */
  span: string;
  token: string;
  score: number;
  /** Unicode code points into the source message or prompt. */
  start: number;
  end: number;
  /** UTF-16 code units. Use these for JavaScript highlighting. */
  start_utf16: number;
  end_utf16: number;
  /** Code points into the anonymized text (prompt or that message). */
  token_start: number;
  token_end: number;
  token_start_utf16: number;
  token_end_utf16: number;
  /** Null for prompt-only spans. Set when the source was `messages`. */
  message_index: number | null;
}

export interface AnonymizedMessage {
  role: string;
  content: string;
  message_index: number;
}

/**
 * POST /v1/debug/anonymize-preview.
 * Requires an admin credential and ANONREQ_DEBUG_PREVIEW_ENABLED=true.
 * Otherwise the gateway returns 404. The preview does not call a provider.
 */
export interface AnonymizePreviewResponse {
  request_id: string;
  locale: string;
  classification: string;
  highest_entity: string;
  anonymized_text: string | null;
  anonymized_messages: AnonymizedMessage[] | null;
  entities: PreviewEntity[];
}

export interface AnonReqHeaders {
  requestId: string | null;
  entityCount: string | null;
  classification: string | null;
  highestEntity: string | null;
  processed: string | null;
}

export interface ChatCompletionResult {
  answer: string;
  model: string;
  completionId: string | null;
  headers: AnonReqHeaders;
}

export interface EntityTypeCount {
  type: string;
  count: number;
}

/** One row of GET /v1/admin/anonymization-events. No separate id field. */
export interface AnonymizationEvent {
  request_id: string | null;
  timestamp: string;
  tenant_id: string;
  model: string | null;
  locale: string | null;
  decision: string | null;
  token_count: number | null;
  entity_types: EntityTypeCount[];
}

/** Query value accepted by the events list and export (`timestamp:asc|desc`). */
export type AnonymizationEventSort = "timestamp:desc" | "timestamp:asc";

/** Filters for the events list. Tenant is the caller header, not a query field. */
export interface AnonymizationEventQuery {
  date_from?: string;
  date_to?: string;
  entity_type?: string;
  limit: number;
  /** Opaque keyset cursor. Absent on the first page. */
  cursor?: string;
  sort: AnonymizationEventSort;
}

/**
 * One page of anonymization events.
 * `next_cursor` is null when there is no further page.
 * `totalExact` is false when the rows were cut from the legacy export.
 */
export interface AnonymizationEventPage {
  total: number;
  totalExact: boolean;
  limit: number;
  next_cursor: string | null;
  items: AnonymizationEvent[];
  source: "events" | "legacy-export";
}

export interface ConfigHistoryItem {
  event_id: string;
  timestamp: string;
  tenant_id: string;
  change_type: string | null;
  operator_id: string | null;
  prev_value_hash: string | null;
  new_value_hash: string | null;
}

export interface ConfigHistoryQuery {
  tenant_id?: string;
  event_type?: string;
  operator_id?: string;
  date_from?: string;
  date_to?: string;
  limit: number;
  offset: number;
}

export interface ConfigHistoryPage {
  items: ConfigHistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

/** GET /v1/governance/audit/verify */
export interface ChainVerification {
  is_intact: boolean;
  checked_count: number;
  broken_at: string | null;
}

export interface ApiErrorBody {
  error: {
    message: string;
    status: number;
  };
}
