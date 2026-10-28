import { gatewayErrorMessage, gatewayRequest, isMockMode, readGatewayJson } from "@/lib/gateway";
import { GatewayRequestError } from "@/lib/gateway-error";
import { parseChatCompletion } from "@/lib/parse";
import { mockRestoredAnswer, redactText } from "@/lib/redact";
import type { AnonReqHeaders, ChatCompletionResult } from "@/lib/types";

export interface ChatRequestInput {
  model: string;
  prompt: string;
  tenantId: string;
  locale: string;
}

export interface ChatClient {
  complete(input: ChatRequestInput): Promise<ChatCompletionResult>;
}

export interface ModelListClient {
  list(tenantId: string): Promise<{ models: string[]; source: "gateway" | "fallback" | "mock" }>;
}

const FALLBACK_MODELS = ["grok", "grok-4", "grok-3"];

function headersFromRedaction(redaction: ReturnType<typeof redactText>, requestId: string): AnonReqHeaders {
  return {
    requestId,
    entityCount: String(redaction.entities.length),
    classification: redaction.classification,
    highestEntity: redaction.highest_entity || null,
    processed: redaction.entities.length > 0 ? "true" : "false",
  };
}

function mockChat(): ChatClient {
  return {
    async complete(input) {
      const redaction = redactText(input.prompt);
      const requestId = `req_${crypto.randomUUID().replace(/-/g, "").slice(0, 24)}`;
      return {
        answer: mockRestoredAnswer(redaction.entities, input.locale),
        model: input.model,
        completionId: `chatcmpl_mock_${requestId.slice(4, 12)}`,
        headers: headersFromRedaction(redaction, requestId),
      };
    },
  };
}

function liveChat(): ChatClient {
  return {
    async complete(input) {
      const response = await gatewayRequest({
        path: "/v1/chat/completions",
        method: "POST",
        auth: "user",
        tenantId: input.tenantId,
        locale: input.locale,
        timeoutMs: 60_000,
        jsonBody: {
          model: input.model,
          messages: [{ role: "user", content: input.prompt }],
          stream: false,
        },
      });
      const body = await readGatewayJson(response);
      if (!response.ok) {
        throw new GatewayRequestError(gatewayErrorMessage(response.status, body.json), response.status);
      }
      const parsed = parseChatCompletion(body.json, response.headers);
      if (!parsed) {
        throw new GatewayRequestError("Completion response did not include an assistant message", 502);
      }
      return parsed;
    },
  };
}

export function getChatClient(): ChatClient {
  return isMockMode() ? mockChat() : liveChat();
}

function mockModels(): ModelListClient {
  return {
    async list() {
      return { models: FALLBACK_MODELS, source: "mock" };
    },
  };
}

function liveModels(): ModelListClient {
  return {
    async list(tenantId) {
      try {
        const response = await gatewayRequest({
          path: "/v1/models",
          auth: "user",
          tenantId,
          timeoutMs: 8_000,
        });
        const body = await readGatewayJson(response);
        if (!response.ok || !body.json || typeof body.json !== "object") {
          return { models: FALLBACK_MODELS, source: "fallback" };
        }
        const data = (body.json as { data?: unknown }).data;
        if (!Array.isArray(data)) {
          return { models: FALLBACK_MODELS, source: "fallback" };
        }
        const models = data.flatMap((item) => {
          if (item && typeof item === "object" && "id" in item && typeof item.id === "string") {
            return [item.id];
          }
          return [];
        });
        return { models: models.length > 0 ? models : FALLBACK_MODELS, source: models.length > 0 ? "gateway" : "fallback" };
      } catch {
        return { models: FALLBACK_MODELS, source: "fallback" };
      }
    },
  };
}

export function getModelClient(): ModelListClient {
  return isMockMode() ? mockModels() : liveModels();
}
