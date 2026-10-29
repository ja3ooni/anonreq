import { GatewayRequestError } from "@/lib/gateway-error";
import { fromGatewayError, jsonOk } from "@/lib/http";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
    if (!body || typeof body !== "object") {
      throw new GatewayRequestError("Telemetry payload must be JSON", 400);
    }

    const riusEndpoint = process.env.GLASSFLOW_RIUS_OTLP_ENDPOINT?.trim() || "";
    const riusApiKey = process.env.GLASSFLOW_RIUS_API_KEY?.trim() || "";
    const taresWebhook = process.env.GLASSFLOW_TARES_WEBHOOK_URL?.trim() || "";
    const taresToken = process.env.GLASSFLOW_TARES_TOKEN?.trim() || "";

    let riusDelivered = false;
    let taresDelivered = false;
    let riusStatus: number | null = null;
    let taresStatus: number | null = null;

    if (riusEndpoint && body.rius) {
      try {
        const res = await fetch(riusEndpoint, {
          method: "POST",
          headers: {
            "content-type": "application/json",
            ...(riusApiKey ? { authorization: `Bearer ${riusApiKey}` } : {}),
          },
          body: JSON.stringify(body.rius),
          signal: AbortSignal.timeout(5_000),
        });
        riusStatus = res.status;
        riusDelivered = res.ok;
      } catch {
        riusStatus = 0;
      }
    }

    if (taresWebhook && body.tares) {
      try {
        const res = await fetch(taresWebhook, {
          method: "POST",
          headers: {
            "content-type": "application/json",
            ...(taresToken ? { authorization: `Bearer ${taresToken}` } : {}),
          },
          body: JSON.stringify(body.tares),
          signal: AbortSignal.timeout(5_000),
        });
        taresStatus = res.status;
        taresDelivered = res.ok;
      } catch {
        taresStatus = 0;
      }
    }

    return jsonOk({
      ok: true,
      mode: riusEndpoint || taresWebhook ? "live_webhook" : "local_inspector",
      riusConfigured: Boolean(riusEndpoint),
      taresConfigured: Boolean(taresWebhook),
      riusDelivered,
      taresDelivered,
      riusStatus,
      taresStatus,
    });
  } catch (error) {
    return fromGatewayError(error);
  }
}

