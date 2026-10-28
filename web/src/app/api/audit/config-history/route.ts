import { getConfigClient } from "@/lib/audit-client";
import { fromGatewayError, jsonError, jsonOk } from "@/lib/http";
import { defaultTenant, optionalDate, optionalToken, queryInt } from "@/lib/validate";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Keyset page. Admin key and X-AnonReq-Tenant-ID. Limit default 100, max 1000. */
export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const cursor = url.searchParams.get("cursor")?.trim() || undefined;
    if (cursor && cursor.length > 512) {
      return jsonError("Cursor is not valid", 400);
    }
    const query = {
      event_type: optionalToken(url.searchParams.get("event_type"), "Change type"),
      operator_id: optionalToken(url.searchParams.get("operator_id"), "Operator"),
      date_from: optionalDate(url.searchParams.get("date_from")),
      date_to: optionalDate(url.searchParams.get("date_to")),
      limit: queryInt(url.searchParams.get("limit"), 100, 1000),
      cursor,
    };
    const page = await getConfigClient().list(query, defaultTenant());
    return jsonOk(page);
  } catch (error) {
    return fromGatewayError(error);
  }
}
