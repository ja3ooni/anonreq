import type { AnonymizePreviewResponse, ChatCompletionResult } from "@/lib/types";

export interface GlassFlowTelemetryInput {
  mode: "scan_only" | "full_chat";
  scenarioId: string;
  filename?: string | null;
  tenantId: string;
  locale: string;
  model: string;
  latencyMs: number;
  preview: AnonymizePreviewResponse | null;
  chat: ChatCompletionResult | null;
  errorStatus?: number | null;
}

export interface RiusOtlpSpan {
  traceId: string;
  spanId: string;
  parentSpanId?: string;
  name: string;
  kind: "SERVER" | "INTERNAL" | "CLIENT";
  startTimeUnixNano: string;
  endTimeUnixNano: string;
  status: { code: "STATUS_CODE_OK" | "STATUS_CODE_ERROR"; message?: string };
  attributes: Record<string, string | number | boolean>;
}

export interface GlassFlowRiusPayload {
  resource: {
    attributes: {
      "service.name": "anonreq-gateway";
      "service.namespace": "frankfurt-eu-edge";
      "deployment.environment": string;
    };
  };
  spans: RiusOtlpSpan[];
}

export interface GlassFlowTaresEvent {
  specversion: "1.0";
  id: string;
  source: "urn:anonreq:gateway:de-frankfurt";
  service: "anonreq-gateway";
  type: "ai.anonreq.context.sanitized" | "ai.anonreq.gateway.fail_closed";
  time: string;
  subject: string;
  correlation_key: string;
  tenant_id: string;
  scenario: string;
  decision: "ANONYMIZE" | "PASS" | "BLOCK" | "FAIL_CLOSED";
  classification: string;
  highest_entity: string;
  data: {
    request_id: string;
    tenant_id: string;
    locale: string;
    scenario: string;
    source_file: string | null;
    decision: "ANONYMIZE" | "PASS" | "BLOCK" | "FAIL_CLOSED";
    classification: string;
    highest_entity: string;
    entity_counts: Record<string, number>;
    non_reversible_masked: number;
    sanitized_context: string;
    agent_wake_allowed: boolean;
    upstream_model: string | null;
  };
}

export interface GlassFlowBundle {
  rius: GlassFlowRiusPayload;
  tares: GlassFlowTaresEvent;
}

function deterministicHex(seed: string, length: number): string {
  let hash = 2166136261;
  let out = "";
  let i = 0;
  while (out.length < length) {
    const ch = seed.charCodeAt(i % seed.length) || 42;
    hash ^= ch + i * 31;
    hash = Math.imul(hash, 16777619) >>> 0;
    out += hash.toString(16).padStart(8, "0");
    i += 1;
  }
  return out.slice(0, length);
}

export function buildGlassFlowBundle(input: GlassFlowTelemetryInput): GlassFlowBundle {
  const nowMs = Date.now();
  const durationMs = Math.max(8, input.latencyMs || 42);
  const startNano = BigInt(nowMs - durationMs) * BigInt(1_000_000);
  const midNano = BigInt(nowMs - Math.floor(durationMs / 2)) * BigInt(1_000_000);
  const endNano = BigInt(nowMs) * BigInt(1_000_000);

  const requestId =
    input.chat?.headers.requestId ||
    input.preview?.request_id ||
    `req_${deterministicHex(`${nowMs}-${input.scenarioId}`, 20)}`;

  const traceId = deterministicHex(`trace-${requestId}`, 32);
  const rootSpanId = deterministicHex(`root-${requestId}`, 16);
  const detectSpanId = deterministicHex(`detect-${requestId}`, 16);
  const llmSpanId = deterministicHex(`llm-${requestId}`, 16);

  const entities = input.preview?.entities ?? [];
  const counts: Record<string, number> = {};
  let nonReversible = 0;
  for (const entity of entities) {
    counts[entity.entity_type] = (counts[entity.entity_type] ?? 0) + 1;
    if (entity.entity_type === "API_KEY" || entity.entity_type === "SECRET") {
      nonReversible += 1;
    }
  }

  const failedClosed = Boolean(input.errorStatus && input.errorStatus >= 500);
  const decision: "ANONYMIZE" | "PASS" | "BLOCK" | "FAIL_CLOSED" = failedClosed
    ? "FAIL_CLOSED"
    : entities.length > 0
      ? "ANONYMIZE"
      : "PASS";

  const classification =
    input.chat?.headers.classification ||
    input.preview?.classification ||
    (failedClosed ? "BLOCKED" : entities.length > 0 ? "CONFIDENTIAL" : "PUBLIC");

  const highestEntity =
    input.chat?.headers.highestEntity ||
    input.preview?.highest_entity ||
    "";

  const spans: RiusOtlpSpan[] = [
    {
      traceId,
      spanId: rootSpanId,
      name: "anonreq.gateway.handle_request",
      kind: "SERVER",
      startTimeUnixNano: startNano.toString(),
      endTimeUnixNano: endNano.toString(),
      status: {
        code: failedClosed ? "STATUS_CODE_ERROR" : "STATUS_CODE_OK",
        ...(failedClosed ? { message: "Fail-closed: detector unavailable or language unsupported" } : {}),
      },
      attributes: {
        "anonreq.request_id": requestId,
        "anonreq.tenant_id": input.tenantId,
        "anonreq.locale": input.locale,
        "anonreq.mode": input.mode,
        "anonreq.decision": decision,
        "anonreq.classification": classification,
        "anonreq.highest_entity": highestEntity || "NONE",
        "anonreq.entity_total": entities.length,
        "anonreq.non_reversible_entities": nonReversible,
        "anonreq.cleartext_pii_forwarded": false,
      },
    },
    {
      traceId,
      spanId: detectSpanId,
      parentSpanId: rootSpanId,
      name: "anonreq.pipeline.detect_and_tokenize",
      kind: "INTERNAL",
      startTimeUnixNano: startNano.toString(),
      endTimeUnixNano: midNano.toString(),
      status: {
        code: failedClosed ? "STATUS_CODE_ERROR" : "STATUS_CODE_OK",
      },
      attributes: {
        "anonreq.presidio.language": input.locale.startsWith("de") ? "de" : "en",
        "anonreq.entity_counts_json": JSON.stringify(counts),
        "anonreq.source_file": input.filename ?? "inline_prompt",
      },
    },
  ];

  if (input.mode === "full_chat" && !failedClosed) {
    spans.push({
      traceId,
      spanId: llmSpanId,
      parentSpanId: rootSpanId,
      name: "gen_ai.xai.chat.completions",
      kind: "CLIENT",
      startTimeUnixNano: midNano.toString(),
      endTimeUnixNano: endNano.toString(),
      status: {
        code: input.chat ? "STATUS_CODE_OK" : "STATUS_CODE_ERROR",
      },
      attributes: {
        "gen_ai.system": "xai",
        "gen_ai.request.model": input.model,
        "anonreq.tokens_restored_in_response": entities.length - nonReversible,
        "anonreq.secrets_kept_masked": nonReversible,
      },
    });
  }

  const tares: GlassFlowTaresEvent = {
    specversion: "1.0",
    id: `evt_${requestId.replace(/^req_/, "")}`,
    source: "urn:anonreq:gateway:de-frankfurt",
    service: "anonreq-gateway",
    type: failedClosed ? "ai.anonreq.gateway.fail_closed" : "ai.anonreq.context.sanitized",
    time: new Date(nowMs).toISOString(),
    subject: `tenant:${input.tenantId}:scenario:${input.scenarioId}`,
    correlation_key: `${input.tenantId}:${input.scenarioId}`,
    tenant_id: input.tenantId,
    scenario: input.scenarioId,
    decision,
    classification,
    highest_entity: highestEntity || "NONE",
    data: {
      request_id: requestId,
      tenant_id: input.tenantId,
      locale: input.locale,
      scenario: input.scenarioId,
      source_file: input.filename ?? null,
      decision,
      classification,
      highest_entity: highestEntity,
      entity_counts: counts,
      non_reversible_masked: nonReversible,
      sanitized_context: input.preview?.anonymized_text ?? "",
      agent_wake_allowed: !failedClosed,
      upstream_model: input.mode === "full_chat" ? input.model : null,
    },
  };

  return {
    rius: {
      resource: {
        attributes: {
          "service.name": "anonreq-gateway",
          "service.namespace": "frankfurt-eu-edge",
          "deployment.environment": "demo-frankfurt-ai-week",
        },
      },
      spans,
    },
    tares,
  };
}
