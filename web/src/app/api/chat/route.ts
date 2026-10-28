import { getChatClient } from "@/lib/chat-client";
import { fromGatewayError, jsonOk } from "@/lib/http";
import { GatewayRequestError } from "@/lib/gateway-error";
import { defaultTenant, requireLocale, requireModel, requirePrompt } from "@/lib/validate";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const body = await readJson(request);
    const prompt = requirePrompt(body.prompt);
    const model = requireModel(body.model);
    const tenantId = defaultTenant();
    const locale = requireLocale(body.locale, "en");
    const result = await getChatClient().complete({ model, prompt, tenantId, locale });
    return jsonOk(result);
  } catch (error) {
    return fromGatewayError(error);
  }
}

async function readJson(request: Request): Promise<Record<string, unknown>> {
  const body = await request.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw new GatewayRequestError("Request body must be JSON", 400);
  }
  return body as Record<string, unknown>;
}
