import { getModelClient } from "@/lib/chat-client";
import { fromGatewayError, jsonOk } from "@/lib/http";
import { defaultTenant } from "@/lib/validate";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  try {
    const result = await getModelClient().list(defaultTenant());
    return jsonOk(result);
  } catch (error) {
    return fromGatewayError(error);
  }
}
