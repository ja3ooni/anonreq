import { getEventsClient } from "@/lib/audit-client";
import { fromGatewayError } from "@/lib/http";
import { defaultTenant, optionalDate, optionalEntityType, querySort } from "@/lib/validate";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const query = {
      date_from: optionalDate(url.searchParams.get("date_from")),
      date_to: optionalDate(url.searchParams.get("date_to")),
      entity_type: optionalEntityType(url.searchParams.get("entity_type")),
      limit: 10_000,
      sort: querySort(url.searchParams.get("sort")),
    };
    const file = await getEventsClient().exportCsv(query, defaultTenant());
    return new Response(Buffer.from(file.body), {
      headers: {
        "content-type": "text/csv; charset=utf-8",
        "content-disposition": `attachment; filename="${file.filename}"`,
        "cache-control": "no-store",
        "x-anonreq-export-source": file.source,
      },
    });
  } catch (error) {
    return fromGatewayError(error);
  }
}
