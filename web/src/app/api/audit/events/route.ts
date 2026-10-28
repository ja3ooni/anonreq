import { getEventsClient } from "@/lib/audit-client";
import { fromGatewayError, jsonError, jsonOk } from "@/lib/http";
import { defaultTenant, optionalDate, optionalEntityType, queryInt, querySort } from "@/lib/validate";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Cursor page. Tenant is the caller header, not a query filter. */
export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const cursor = url.searchParams.get("cursor")?.trim() || undefined;
    if (cursor && cursor.length > 512) {
      return jsonError("Cursor is not valid", 400);
    }
    const query = {
      date_from: optionalDate(url.searchParams.get("date_from")),
      date_to: optionalDate(url.searchParams.get("date_to")),
      entity_type: optionalEntityType(url.searchParams.get("entity_type")),
      limit: queryInt(url.searchParams.get("limit"), 10, 200),
      cursor,
      sort: querySort(url.searchParams.get("sort")),
    };
    const page = await getEventsClient().list(query, defaultTenant());
    return jsonOk(page);
  } catch (error) {
    return fromGatewayError(error);
  }
}
