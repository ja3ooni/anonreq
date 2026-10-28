import {
  gatewayErrorMessage,
  gatewayRequest,
  isMockMode,
  mockPreviewDisabled,
  readGatewayJson,
} from "@/lib/gateway";
import { GatewayRequestError } from "@/lib/gateway-error";
import { parsePreview } from "@/lib/parse";
import { redactText } from "@/lib/redact";
import type { AnonymizePreviewRequest, AnonymizePreviewResponse } from "@/lib/types";

export interface PreviewCallContext {
  tenantId: string;
  locale: string;
}

export type PreviewClientResult =
  | { ok: true; data: AnonymizePreviewResponse }
  | { ok: false; reason: "disabled"; status: 404; message: string }
  | { ok: false; reason: "invalid" | "error"; status: number; message: string };

/**
 * Client for POST /v1/debug/anonymize-preview.
 * Admin only. The gateway returns 404 while the flag is off.
 * The UI depends on this interface, so the route can drop in unchanged.
 */
export interface AnonymizePreviewClient {
  preview(input: AnonymizePreviewRequest, context: PreviewCallContext): Promise<PreviewClientResult>;
}

const DISABLED =
  "POST /v1/debug/anonymize-preview returned 404. It stays off until ANONREQ_DEBUG_PREVIEW_ENABLED=true and an admin credential is accepted.";

function sourceText(input: AnonymizePreviewRequest): string {
  if (typeof input.prompt === "string") {
    return input.prompt;
  }
  return (input.messages ?? [])
    .filter((message) => message.role === "user")
    .map((message) => message.content)
    .join("\n\n");
}

export function buildMockPreview(
  input: AnonymizePreviewRequest,
  locale: string,
  requestId: string,
): AnonymizePreviewResponse {
  if (typeof input.prompt === "string" && input.prompt.trim()) {
    const redacted = redactText(input.prompt, null);
    return {
      request_id: requestId,
      locale,
      classification: redacted.classification,
      highest_entity: redacted.highest_entity,
      anonymized_text: redacted.anonymized_text,
      anonymized_messages: null,
      entities: redacted.entities,
    };
  }
  const entities: AnonymizePreviewResponse["entities"] = [];
  let classification = "PUBLIC";
  let highest = "";
  const anonymizedMessages = (input.messages ?? []).map((message, index) => {
    const redacted = redactText(message.content, index);
    entities.push(...redacted.entities);
    if (rank(redacted.classification) > rank(classification)) {
      classification = redacted.classification;
      highest = redacted.highest_entity;
    }
    return { role: message.role, content: redacted.anonymized_text, message_index: index };
  });
  return {
    request_id: requestId,
    locale,
    classification,
    highest_entity: highest,
    anonymized_text: null,
    anonymized_messages: anonymizedMessages,
    entities,
  };
}

function rank(name: string): number {
  return ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED", "HIGHLY_RESTRICTED"].indexOf(name);
}

function mockClient(): AnonymizePreviewClient {
  return {
    async preview(input, context) {
      if (mockPreviewDisabled()) {
        return { ok: false, reason: "disabled", status: 404, message: DISABLED };
      }
      return {
        ok: true,
        data: buildMockPreview(input, context.locale, `req_${crypto.randomUUID().replace(/-/g, "").slice(0, 24)}`),
      };
    },
  };
}

function liveClient(): AnonymizePreviewClient {
  return {
    async preview(input, context) {
      const response = await gatewayRequest({
        path: "/v1/debug/anonymize-preview",
        method: "POST",
        auth: "admin",
        tenantId: context.tenantId,
        locale: context.locale,
        jsonBody:
          typeof input.prompt === "string" && input.prompt.length > 0
            ? { prompt: input.prompt }
            : { messages: input.messages },
        timeoutMs: 20_000,
      });
      const body = await readGatewayJson(response);
      if (response.status === 404) {
        return { ok: false, reason: "disabled", status: 404, message: DISABLED };
      }
      if (!response.ok) {
        return {
          ok: false,
          reason: "error",
          status: response.status,
          message: gatewayErrorMessage(response.status, body.json),
        };
      }
      const data = parsePreview(body.json);
      if (!data) {
        return {
          ok: false,
          reason: "invalid",
          status: 502,
          message: "Preview response did not match the expected shape",
        };
      }
      return { ok: true, data };
    },
  };
}

export function getPreviewClient(): AnonymizePreviewClient {
  return isMockMode() ? mockClient() : liveClient();
}

export function assertPreviewInput(input: AnonymizePreviewRequest): void {
  const source = sourceText(input);
  if (!source.trim()) {
    throw new GatewayRequestError("Prompt is empty", 400);
  }
}
