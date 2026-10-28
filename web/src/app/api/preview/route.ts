import { assertPreviewInput, getPreviewClient } from "@/lib/preview-client";
import { fromGatewayError, jsonOk } from "@/lib/http";
import { GatewayRequestError } from "@/lib/gateway-error";
import { MAX_PROMPT_CHARS, requireLocale, requireTenant } from "@/lib/validate";
import type { ChatMessage } from "@/lib/types";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * Proxies POST /v1/debug/anonymize-preview.
 * A gateway 404 (flag off) is returned as `{ ok: false, reason: "disabled" }`
 * so the middle column can show its placeholder without a failed request in the UI.
 */
export async function POST(request: Request) {
  try {
    const body = await readJson(request);
    const prompt = typeof body.prompt === "string" ? body.prompt : undefined;
    const messages = parseMessages(body.messages);
    const source =
      prompt ??
      messages
        ?.filter((message) => message.role === "user")
        .map((message) => message.content)
        .join("\n\n") ??
      "";
    if (source.length > MAX_PROMPT_CHARS) {
      throw new GatewayRequestError("Prompt is too long", 400);
    }
    const input = prompt
      ? { prompt }
      : { messages: messages ?? [] };
    assertPreviewInput(input);
    const tenantId = requireTenant(body.tenantId);
    const locale = requireLocale(body.locale, "en");
    const result = await getPreviewClient().preview(input, { tenantId, locale });
    return jsonOk(result);
  } catch (error) {
    return fromGatewayError(error);
  }
}

function parseMessages(value: unknown): ChatMessage[] | undefined {
  if (value == null) {
    return undefined;
  }
  if (!Array.isArray(value) || value.length === 0 || value.length > 20) {
    throw new GatewayRequestError("Messages are not valid", 400);
  }
  return value.map((item) => {
    if (!item || typeof item !== "object") {
      throw new GatewayRequestError("Messages are not valid", 400);
    }
    const role = (item as { role?: unknown }).role;
    const content = (item as { content?: unknown }).content;
    if (role !== "system" && role !== "user" && role !== "assistant") {
      throw new GatewayRequestError("Message role is not valid", 400);
    }
    if (typeof content !== "string" || content.length > MAX_PROMPT_CHARS) {
      throw new GatewayRequestError("Message content is not valid", 400);
    }
    return { role, content };
  });
}

async function readJson(request: Request): Promise<Record<string, unknown>> {
  const body = await request.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw new GatewayRequestError("Request body must be JSON", 400);
  }
  return body as Record<string, unknown>;
}
