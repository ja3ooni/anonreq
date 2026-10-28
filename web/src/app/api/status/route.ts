import { GatewayRequestError } from "@/lib/gateway-error";
import { gatewayRequest, isMockMode } from "@/lib/gateway";
import { jsonError, jsonOk } from "@/lib/http";
import { defaultTenant } from "@/lib/validate";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  try {
    const tenant = defaultTenant();
    if (isMockMode()) {
      return jsonOk({ mode: "mock", gateway: "skipped", defaultTenant: tenant });
    }
    if (!process.env.ANONREQ_GATEWAY_URL?.trim()) {
      return jsonError(
        "ANONREQ_GATEWAY_URL is not set. Set it for a live gateway, or set ANONREQ_MOCK=true for fixtures. Mock mode is not implied by an empty URL, and it is refused when NODE_ENV=production.",
        500,
      );
    }
    if (!process.env.ANONREQ_API_KEY?.trim()) {
      return jsonOk({ mode: "live", gateway: "unconfigured", defaultTenant: tenant });
    }
    const response = await gatewayRequest({
      path: "/health",
      auth: "user",
      tenantId: tenant,
      timeoutMs: 2500,
    });
    await response.arrayBuffer().catch(() => undefined);
    return jsonOk({
      mode: "live",
      gateway: response.status > 0 && response.status < 500 ? "up" : "down",
      defaultTenant: tenant,
    });
  } catch (error) {
    if (error instanceof GatewayRequestError) {
      return jsonError(error.message, error.status);
    }
    return jsonOk({ mode: "live", gateway: "down", defaultTenant: "unknown" });
  }
}
