/**
 * GlassFlow forwarding targets come from server env only. The request body can never choose
 * a URL or credential (SSRF + credential exfiltration). No Next.js imports, so tests can load it.
 */

export interface GlassFlowConfig {
  /** Tares webhook from GLASSFLOW_TARES_WEBHOOK_URL, or "" when unset/invalid (no forwarding). */
  taresWebhook: string;
  taresToken: string;
  riusEndpoint: string;
  riusApiKey: string;
}

/** Body fields older UIs sent to pick the target. Now refused. */
export const CLIENT_TARGET_FIELDS = ["taresUrl", "taresToken", "riusEndpoint", "riusApiKey", "url", "token"] as const;

export function clientTargetFields(body: Record<string, unknown>): string[] {
  return CLIENT_TARGET_FIELDS.filter((field) => field in body);
}

/** Only absolute http(s) URLs without embedded credentials are usable targets. */
export function safeEnvUrl(value: string | undefined): string {
  const raw = value?.trim() ?? "";
  if (!raw) {
    return "";
  }
  try {
    const url = new URL(raw);
    if ((url.protocol !== "https:" && url.protocol !== "http:") || url.username || url.password) {
      return "";
    }
    return raw.replace(/\/+$/, "");
  } catch {
    return "";
  }
}

export function resolveGlassFlowConfig(env: Record<string, string | undefined>): GlassFlowConfig {
  const taresWebhook = safeEnvUrl(env.GLASSFLOW_TARES_WEBHOOK_URL);
  const taresToken = env.GLASSFLOW_TARES_TOKEN?.trim() || env.GLASSFLOW_API?.trim() || env.glassflow_API?.trim() || "";
  const taresBase = taresBaseFrom(taresWebhook);
  const riusEndpoint = safeEnvUrl(env.GLASSFLOW_RIUS_OTLP_ENDPOINT) || (taresBase ? `${taresBase}/v1/traces` : "");
  const riusApiKey = env.GLASSFLOW_RIUS_API_KEY?.trim() || taresToken;
  return { taresWebhook, taresToken, riusEndpoint, riusApiKey };
}

/** Clean Tares base URL (strip trailing /read, /remember, /health, /v1/*, or /ingest/<key>). */
export function taresBaseFrom(webhook: string): string {
  return webhook
    .replace(/\/+$/, "")
    .replace(/\/(read|remember|health|v1\/traces|v1\/logs)$/i, "")
    .replace(/\/ingest\/[^/]+$/i, "");
}
