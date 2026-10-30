import { GatewayRequestError } from "@/lib/gateway-error";
import { fromGatewayError, jsonOk } from "@/lib/http";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function dockerHostCandidates(rawUrl: string): string[] {
  const trimmed = rawUrl.trim().replace(/\/+$/, "");
  if (!trimmed) return [];
  const candidates = [trimmed];
  try {
    const parsed = new URL(trimmed);
    if (parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1") {
      const dockerUrl = new URL(trimmed);
      dockerUrl.hostname = "host.docker.internal";
      candidates.push(dockerUrl.toString().replace(/\/+$/, ""));
    }
  } catch {
    // ignore invalid URL parse; fetch will report status
  }
  return candidates;
}

async function fetchWithDockerFallback(
  rawUrl: string,
  init: RequestInit,
): Promise<{ res: Response | null; usedUrl: string }> {
  const candidates = dockerHostCandidates(rawUrl);
  let lastUsed = rawUrl;
  for (const url of candidates) {
    lastUsed = url;
    try {
      const res = await fetch(url, {
        ...init,
        signal: AbortSignal.timeout(5_000),
      });
      return { res, usedUrl: url };
    } catch {
      // try next candidate (e.g. host.docker.internal)
    }
  }
  return { res: null, usedUrl: lastUsed };
}

export async function POST(request: Request) {
  try {
    const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
    if (!body || typeof body !== "object") {
      throw new GatewayRequestError("Telemetry payload must be JSON", 400);
    }

    const overrideTaresUrl = typeof body.taresUrl === "string" ? body.taresUrl.trim() : "";
    const overrideTaresToken = typeof body.taresToken === "string" ? body.taresToken.trim() : "";
    const envWebhook = process.env.GLASSFLOW_TARES_WEBHOOK_URL?.trim() || "";

    const taresWebhook =
      overrideTaresUrl.includes("/ingest/")
        ? overrideTaresUrl
        : envWebhook.includes("/ingest/")
          ? envWebhook
          : overrideTaresUrl ||
            envWebhook ||
            "https://sunny-ridge-aj.tares-glassflow.com/ingest/webhook-7be6b6c7";
    const taresToken =
      overrideTaresToken ||
      process.env.GLASSFLOW_TARES_TOKEN?.trim() ||
      process.env.glassflow_API?.trim() ||
      process.env.GLASSFLOW_API?.trim() ||
      "";

    // Extract clean Tares base URL (strip trailing /read, /remember, /health, or /ingest/...)
    const taresBase = taresWebhook
      .replace(/\/+$/, "")
      .replace(/\/(read|remember|health|v1\/traces|v1\/logs)$/i, "")
      .replace(/\/ingest\/[^/]+$/i, "");

    const riusEndpoint =
      process.env.GLASSFLOW_RIUS_OTLP_ENDPOINT?.trim() ||
      (taresBase ? `${taresBase}/v1/traces` : "");
    const riusApiKey = process.env.GLASSFLOW_RIUS_API_KEY?.trim() || taresToken;

    let riusDelivered = false;
    let taresDelivered = false;
    let riusStatus: number | null = null;
    let taresStatus: number | null = null;
    let resolvedIngestUrl: string | null = null;
    let readResult: unknown = null;
    let healthResult: unknown = null;

    if (taresBase) {
      const { res: healthRes } = await fetchWithDockerFallback(`${taresBase}/health`, {
        method: "GET",
      });
      if (healthRes?.ok) {
        healthResult = await healthRes.json().catch(() => null);
      }
    }

    if (riusEndpoint && body.rius && riusApiKey) {
      const { res } = await fetchWithDockerFallback(riusEndpoint, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          authorization: `Bearer ${riusApiKey}`,
          "x-api-key": riusApiKey,
        },
        body: JSON.stringify(body.rius),
      });
      riusStatus = res ? res.status : 0;
      riusDelivered = Boolean(res?.ok);
    }

    if (taresWebhook && body.tares) {
      const authHeaders: Record<string, string> = {
        "content-type": "application/json",
        ...(taresToken
          ? {
              authorization: `Bearer ${taresToken}`,
              "x-api-key": taresToken,
            }
          : {}),
      };

      const taresPayload = body.tares as Record<string, unknown>;
      const taresData = (taresPayload.data ?? {}) as Record<string, unknown>;

      // 1. If explicit /ingest/<token> URL was provided, post directly to it
      if (taresWebhook.includes("/ingest/")) {
        const { res } = await fetchWithDockerFallback(taresWebhook, {
          method: "POST",
          headers: authHeaders,
          body: JSON.stringify(body.tares),
        });
        taresStatus = res ? res.status : 0;
        taresDelivered = Boolean(res?.ok);
        if (taresDelivered) {
          resolvedIngestUrl = taresWebhook;
        }
      } else if (taresBase) {
        // 2. Try registering/fetching 'anonreq_gateway' webhook source on /api/sources
        const { res: srcRes } = await fetchWithDockerFallback(`${taresBase}/api/sources`, {
          method: "POST",
          headers: authHeaders,
          body: JSON.stringify({
            name: "anonreq_gateway",
            connector: "webhook",
            config: {
              event_type: "sanitized_interaction",
              labels: [
                { name: "correlation_key", field: "correlation_key", primary: true },
                { name: "scenario", field: "scenario", primary: false },
                { name: "decision", field: "decision", primary: false },
                { name: "classification", field: "classification", primary: false },
              ],
            },
          }),
        });
        if (srcRes && srcRes.ok) {
          const srcData = (await srcRes.json().catch(() => null)) as {
            ingest_key?: string;
            token?: string;
          } | null;
          const key = srcData?.ingest_key || srcData?.token;
          if (key) {
            const ingestUrl = `${taresBase}/ingest/${key}`;
            const { res: ingRes } = await fetchWithDockerFallback(ingestUrl, {
              method: "POST",
              headers: authHeaders,
              body: JSON.stringify(body.tares),
            });
            taresStatus = ingRes ? ingRes.status : 0;
            taresDelivered = Boolean(ingRes?.ok);
            if (taresDelivered) {
              resolvedIngestUrl = ingestUrl;
            }
          }
        }

        // 3. Also push to POST <taresBase>/remember (works with standard workspace/project keys)
        const { res: remRes } = await fetchWithDockerFallback(`${taresBase}/remember`, {
          method: "POST",
          headers: authHeaders,
          body: JSON.stringify({
            key: String(taresPayload.correlation_key ?? "frankfurt-build-days-demo"),
            content: `[AnonReq ${String(taresPayload.decision ?? "ALLOW")}] scenario=${String(
              taresPayload.scenario ?? "sepa-dispute",
            )} classification=${String(taresPayload.classification ?? "CONFIDENTIAL")} highest_entity=${String(
              taresPayload.highest_entity ?? "NONE",
            )} prompt="${String(taresData.sanitized_prompt_preview ?? "")}"`,
            memory_type: "observation",
            source: "anonreq_gateway",
            fields: {
              correlation_key: taresPayload.correlation_key ?? "frankfurt-build-days-demo",
              tenant_id: taresPayload.tenant_id ?? "frankfurt-demo-eu",
              scenario: taresPayload.scenario ?? "sepa-dispute",
              decision: taresPayload.decision ?? "ALLOW",
              classification: taresPayload.classification ?? "CONFIDENTIAL",
              highest_entity: taresPayload.highest_entity ?? "NONE",
              raw_pii_leaked: false,
            },
          }),
        });
        if (remRes) {
          if (!taresDelivered) {
            taresStatus = remRes.status;
          }
          if (remRes.ok) {
            taresDelivered = true;
          }
        }

        // 4. If token itself is an /ingest/<token> credential, try POST <taresBase>/ingest/<taresToken>
        if (!taresDelivered && taresToken) {
          const { res: tokIngRes } = await fetchWithDockerFallback(
            `${taresBase}/ingest/${encodeURIComponent(taresToken)}`,
            {
              method: "POST",
              headers: authHeaders,
              body: JSON.stringify(body.tares),
            },
          );
          if (tokIngRes?.ok) {
            taresStatus = tokIngRes.status;
            taresDelivered = true;
            resolvedIngestUrl = `${taresBase}/ingest/${taresToken}`;
          }
        }
      }

      // 5. Execute live POST <taresBase>/read so the UI can display live correlated rows from Tares
      if (taresBase) {
        const { res: readRes } = await fetchWithDockerFallback(`${taresBase}/read`, {
          method: "POST",
          headers: authHeaders,
          body: JSON.stringify({
            selector: {
              correlation_key: String(
                taresPayload.correlation_key ?? "frankfurt-build-days-demo",
              ),
            },
            window: "15m",
            client: "anonreq-gateway-ui",
            include_payload: true,
          }),
        });
        if (readRes) {
          if (!taresStatus) {
            taresStatus = readRes.status;
          }
          readResult = await readRes.json().catch(() => ({ status: readRes.status }));
        }
      }
    }

    return jsonOk({
      ok: true,
      mode: taresToken || taresWebhook.includes("/ingest/") ? "live_webhook" : "local_inspector",
      taresBase,
      riusConfigured: Boolean(riusEndpoint),
      taresConfigured: Boolean(taresWebhook),
      riusDelivered,
      taresDelivered,
      riusStatus,
      taresStatus,
      resolvedIngestUrl,
      healthResult,
      readResult,
    });
  } catch (error) {
    return fromGatewayError(error);
  }
}
