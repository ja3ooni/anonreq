import { getConfigClient } from "@/lib/audit-client";
import { fromGatewayError, jsonOk } from "@/lib/http";
import {
  defaultTenant,
  optionalDate,
  optionalTenant,
  optionalToken,
  queryInt,
} from "@/lib/validate";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const tenantFilter = optionalTenant(url.searchParams.get("tenant_id"));
    const query = {
      tenant_id: tenantFilter,
      event_type: optionalToken(url.searchParams.get("event_type"), "Change type"),
      operator_id: optionalToken(url.searchParams.get("operator_id"), "Operator"),
      date_from: optionalDate(url.searchParams.get("date_from")),
      date_to: optionalDate(url.searchParams.get("date_to")),
      limit: queryInt(url.searchParams.get("limit"), 25, 100),
      offset: queryInt(url.searchParams.get("offset"), 0, 100_000),
    };
    const page = await getConfigClient().list(query, tenantFilter ?? defaultTenant());
    return jsonOk(page);
  } catch (error) {
    return fromGatewayError(error);
  }
}
