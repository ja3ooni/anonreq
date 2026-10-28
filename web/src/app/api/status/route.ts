import { gatewayRequest, isMockMode } from "@/lib/gateway";
import { jsonOk } from "@/lib/http";
import { defaultTenant } from "@/lib/validate";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  const tenant = defaultTenant();
  if (isMockMode()) {
    return jsonOk({ mode: "mock", gateway: "skipped", defaultTenant: tenant });
  }
  if (!process.env.ANONREQ_API_KEY?.trim()) {
    return jsonOk({ mode: "live", gateway: "unconfigured", defaultTenant: tenant });
  }
  try {
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
  } catch {
    return jsonOk({ mode: "live", gateway: "down", defaultTenant: tenant });
  }
}
