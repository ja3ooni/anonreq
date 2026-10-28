import { getVerifyClient } from "@/lib/audit-client";
import { fromGatewayError, jsonOk } from "@/lib/http";
import { optionalTenant, defaultTenant } from "@/lib/validate";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const tenantId = optionalTenant(url.searchParams.get("tenant_id")) ?? defaultTenant();
    const result = await getVerifyClient().verify(tenantId);
    return jsonOk(result);
  } catch (error) {
    return fromGatewayError(error);
  }
}
