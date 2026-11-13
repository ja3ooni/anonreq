/**
 * GlassFlow forwarding (Rius OTLP + Tares), used by POST /api/glassflow.
 *
 * - Targets and credentials come from server env only (GlassFlowConfig); the body cannot pick them.
 * - Responses never contain a token, an ingest key or a URL path: only delivered flags, HTTP
 *   statuses and the target host.
 * - Upstream bodies are never passed back (no /read rows, no health JSON, no error detail).
 * - Redirects are not followed (redirect: "manual"), so credentials never go to another origin.
 *
 * Type-only imports and an injectable fetch, so tests run it under `node --experimental-strip-types`.
 */
import type { GlassFlowConfig } from "./glassflow-config";

export type FetchLike = (url: string, init: RequestInit) => Promise<Response>;

export interface GlassFlowSummary {
  ok: true;
  mode: "live_webhook" | "local_inspector";
  /** Host of the Tares cell (no scheme, no path). */
  taresHost: string | null;
  riusConfigured: boolean;
  taresConfigured: boolean;
  riusDelivered: boolean;
  taresDelivered: boolean;
  riusStatus: number | null;
  taresStatus: number | null;
  taresHealthy: boolean;
  taresHealthStatus: number | null;
}

export interface ForwardResult {
  status: number;
  body: GlassFlowSummary | { error: { message: string; status: number } };
}

/** Body fields older UIs sent to pick the target. Refused with 400. */
const CLIENT_TARGET_FIELDS = ["taresUrl", "taresToken", "riusEndpoint", "riusApiKey", "url", "token"];

const LOCAL = new Set(["localhost", "127.0.0.1"]);

function candidates(rawUrl: string): string[] {
  const trimmed = rawUrl.trim().replace(/\/+$/, "");
  if (!trimmed) return [];
  const list = [trimmed];
  try {
    const parsed = new URL(trimmed);
    if (LOCAL.has(parsed.hostname)) {
      parsed.hostname = "host.docker.internal";
      list.push(parsed.toString().replace(/\/+$/, ""));
    }
  } catch {
    // invalid URL: fetch reports it
  }
  return list;
}

function hostOf(url: string): string | null {
  try {
    return url ? new URL(url).host : null;
  } catch {
    return null;
  }
}

function badRequest(message: string): ForwardResult {
  return { status: 400, body: { error: { message, status: 400 } } };
}

export async function forwardToGlassFlow(
  rawBody: unknown,
  config: GlassFlowConfig,
  fetchImpl: FetchLike = fetch,
  timeoutMs = 5_000,
): Promise<ForwardResult> {
  if (!rawBody || typeof rawBody !== "object" || Array.isArray(rawBody)) {
    return badRequest("Telemetry payload must be a JSON object");
  }
  const body = rawBody as Record<string, unknown>;
  const clientTargets = CLIENT_TARGET_FIELDS.filter((field) => field in body);
  if (clientTargets.length > 0) {
    return badRequest(
      `GlassFlow targets are server-configured (GLASSFLOW_TARES_WEBHOOK_URL, GLASSFLOW_TARES_TOKEN, GLASSFLOW_RIUS_OTLP_ENDPOINT). Remove: ${clientTargets.join(", ")}`,
    );
  }
  if (body.tares != null && (typeof body.tares !== "object" || Array.isArray(body.tares))) {
    return badRequest("tares must be a JSON object");
  }

  const { taresWebhook, taresToken, riusEndpoint, riusApiKey } = config;
  const taresBase = taresWebhook
    .replace(/\/+$/, "")
    .replace(/\/(read|remember|health|v1\/traces|v1\/logs)$/i, "")
    .replace(/\/ingest\/[^/]+$/i, "");

  // Manual redirects: a 3xx is a failed delivery, never a hop to another origin with our key.
  async function send(rawUrl: string, init: RequestInit): Promise<Response | null> {
    for (const url of candidates(rawUrl)) {
      try {
        return await fetchImpl(url, { ...init, redirect: "manual", signal: AbortSignal.timeout(timeoutMs) });
      } catch {
        // next candidate (host.docker.internal)
      }
    }
    return null;
  }
  const delivered = (res: Response | null) => Boolean(res && res.status >= 200 && res.status < 300);
  const discard = async (res: Response | null) => {
    await res?.body?.cancel().catch(() => undefined);
  };

  const summary: GlassFlowSummary = {
    ok: true,
    mode: taresToken || taresWebhook.includes("/ingest/") ? "live_webhook" : "local_inspector",
    taresHost: hostOf(taresBase),
    riusConfigured: Boolean(riusEndpoint),
    taresConfigured: Boolean(taresWebhook),
    riusDelivered: false,
    taresDelivered: false,
    riusStatus: null,
    taresStatus: null,
    taresHealthy: false,
    taresHealthStatus: null,
  };

  if (taresBase) {
    const health = await send(`${taresBase}/health`, { method: "GET" });
    summary.taresHealthStatus = health ? health.status : 0;
    summary.taresHealthy = delivered(health);
    await discard(health);
  }

  if (riusEndpoint && body.rius && riusApiKey) {
    const res = await send(riusEndpoint, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${riusApiKey}`, "x-api-key": riusApiKey },
      body: JSON.stringify(body.rius),
    });
    summary.riusStatus = res ? res.status : 0;
    summary.riusDelivered = delivered(res);
    await discard(res);
  }

  if (taresWebhook && body.tares) {
    const headers: Record<string, string> = {
      "content-type": "application/json",
      ...(taresToken ? { authorization: `Bearer ${taresToken}`, "x-api-key": taresToken } : {}),
    };
    const tares = body.tares as Record<string, unknown>;
    const data = (tares.data ?? {}) as Record<string, unknown>;
    const payload = JSON.stringify(body.tares);

    if (taresWebhook.includes("/ingest/")) {
      // 1. The configured URL is already an /ingest/<key> endpoint.
      const res = await send(taresWebhook, { method: "POST", headers, body: payload });
      summary.taresStatus = res ? res.status : 0;
      summary.taresDelivered = delivered(res);
      await discard(res);
    } else if (taresBase) {
      // 2. Register/fetch the 'anonreq_gateway' webhook source, then post to its ingest key.
      const src = await send(`${taresBase}/api/sources`, {
        method: "POST",
        headers,
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
      if (delivered(src)) {
        const srcData = (await src!.json().catch(() => null)) as { ingest_key?: unknown; token?: unknown } | null;
        const key = typeof srcData?.ingest_key === "string" ? srcData.ingest_key : typeof srcData?.token === "string" ? srcData.token : "";
        if (key) {
          const res = await send(`${taresBase}/ingest/${encodeURIComponent(key)}`, { method: "POST", headers, body: payload });
          summary.taresStatus = res ? res.status : 0;
          summary.taresDelivered = delivered(res);
          await discard(res);
        }
      } else {
        await discard(src);
      }

      // 3. POST /remember (works with workspace/project keys).
      const rem = await send(`${taresBase}/remember`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          key: String(tares.correlation_key ?? "frankfurt-build-days-demo"),
          content: `[AnonReq ${String(tares.decision ?? "ALLOW")}] scenario=${String(tares.scenario ?? "sepa-dispute")} classification=${String(
            tares.classification ?? "CONFIDENTIAL",
          )} highest_entity=${String(tares.highest_entity ?? "NONE")} prompt="${String(data.sanitized_prompt_preview ?? "")}"`,
          memory_type: "observation",
          source: "anonreq_gateway",
          fields: {
            correlation_key: tares.correlation_key ?? "frankfurt-build-days-demo",
            tenant_id: tares.tenant_id ?? "frankfurt-demo-eu",
            scenario: tares.scenario ?? "sepa-dispute",
            decision: tares.decision ?? "ALLOW",
            classification: tares.classification ?? "CONFIDENTIAL",
            highest_entity: tares.highest_entity ?? "NONE",
            raw_pii_leaked: false,
          },
        }),
      });
      if (rem) {
        if (!summary.taresDelivered) summary.taresStatus = rem.status;
        if (delivered(rem)) summary.taresDelivered = true;
      }
      await discard(rem);

      // 4. The token itself may be an /ingest/<token> credential.
      if (!summary.taresDelivered && taresToken) {
        const res = await send(`${taresBase}/ingest/${encodeURIComponent(taresToken)}`, { method: "POST", headers, body: payload });
        if (delivered(res)) {
          summary.taresStatus = res!.status;
          summary.taresDelivered = true;
        }
        await discard(res);
      }
    }
  }

  return { status: 200, body: summary };
}
