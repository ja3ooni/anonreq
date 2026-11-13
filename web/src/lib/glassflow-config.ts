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

// The refused body fields (taresUrl, taresToken, …) live in glassflow-forward.ts (single source).

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]", "::1", "host.docker.internal"]);

/** True for loopback / Docker-host targets, the only ones allowed over plain http. */
export function isLocalHost(hostname: string): boolean {
  return LOCAL_HOSTS.has(hostname.toLowerCase());
}

/**
 * Usable targets: absolute https URLs without embedded credentials. Plain http only for a local
 * target (loopback, host.docker.internal), so the token never crosses a network in cleartext.
 */
export function safeEnvUrl(value: string | undefined): string {
  const raw = value?.trim() ?? "";
  if (!raw) {
    return "";
  }
  try {
    const url = new URL(raw);
    if (url.username || url.password) {
      return "";
    }
    if (url.protocol === "https:" || (url.protocol === "http:" && isLocalHost(url.hostname))) {
      return raw.replace(/\/+$/, "");
    }
    return "";
  } catch {
    return "";
  }
}

/** Host only (e.g. "cell.example.com:8443") for display. Never the path, which can hold an ingest key. */
export function targetHost(url: string): string | null {
  try {
    return url ? new URL(url).host : null;
  } catch {
    return null;
  }
}

export function resolveGlassFlowConfig(env: Record<string, string | undefined>): GlassFlowConfig {
  const taresWebhook = safeEnvUrl(env.GLASSFLOW_TARES_WEBHOOK_URL);
  // Canonical names only. The legacy aliases GLASSFLOW_API / glassflow_API are no longer read.
  const taresToken = env.GLASSFLOW_TARES_TOKEN?.trim() || "";
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
