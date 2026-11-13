/**
 * GlassFlow forwarding (Rius OTLP + Tares), used by POST /api/glassflow.
 *
 * - Targets and credentials come from server env only (GlassFlowConfig); the body cannot pick them.
 * - Only the allowlisted bundle from glassflow-payload.ts (parseGlassFlowBundle) is forwarded.
 * - Responses never contain a token, an ingest key or a URL path: only delivered flags, HTTP
 *   statuses and the target host.
 * - Upstream bodies are never passed back (no /read rows, no health JSON, no error detail).
 * - Redirects are not followed (redirect: "manual"), so credentials never go to another origin.
 *
 * Type-only imports and an injectable fetch, so tests run it under `node --experimental-strip-types`.
 */
import type { GlassFlowConfig } from "./glassflow-config";
import type { SanitizedBundle } from "./glassflow-payload";

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

export async function forwardToGlassFlow(
  bundle: SanitizedBundle,
  config: GlassFlowConfig,
  fetchImpl: FetchLike = fetch,
  timeoutMs = 5_000,
): Promise<ForwardResult> {
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

  if (riusEndpoint && bundle.rius && riusApiKey) {
    const res = await send(riusEndpoint, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${riusApiKey}`, "x-api-key": riusApiKey },
      body: JSON.stringify(bundle.rius),
    });
    summary.riusStatus = res ? res.status : 0;
    summary.riusDelivered = delivered(res);
    await discard(res);
  }

  if (taresWebhook && bundle.tares) {
    const headers: Record<string, string> = {
      "content-type": "application/json",
      ...(taresToken ? { authorization: `Bearer ${taresToken}`, "x-api-key": taresToken } : {}),
    };
    const tares = bundle.tares;
    const payload = JSON.stringify(tares);

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
          key: tares.correlation_key,
          content: `[AnonReq ${tares.decision}] scenario=${tares.scenario} classification=${tares.classification} highest_entity=${tares.highest_entity} prompt="${tares.data.sanitized_prompt_preview}"`,
          memory_type: "observation",
          source: "anonreq_gateway",
          fields: {
            correlation_key: tares.correlation_key,
            tenant_id: tares.tenant_id,
            scenario: tares.scenario,
            decision: tares.decision,
            classification: tares.classification,
            highest_entity: tares.highest_entity,
            preview_redacted: tares.data.preview_redacted,
            raw_pii_leaked: tares.data.raw_pii_leaked,
          },
        }),
      });
      if (rem) {
        if (!summary.taresDelivered) summary.taresStatus = rem.status;
        if (delivered(rem)) summary.taresDelivered = true;
      }
      await discard(rem);
    }
  }

  return { status: 200, body: summary };
}
