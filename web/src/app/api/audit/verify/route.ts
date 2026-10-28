import { getVerifyClient } from "@/lib/audit-client";
import { fromGatewayError, jsonOk } from "@/lib/http";
import { defaultTenant } from "@/lib/validate";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Tenant comes from ANONREQ_TENANT_ID. A tenant_id query parameter is ignored. */
export async function GET() {
  try {
    const result = await getVerifyClient().verify(defaultTenant());
    return jsonOk(result);
  } catch (error) {
    return fromGatewayError(error);
  }
}
