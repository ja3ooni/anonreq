/**
 * Host and Origin checks for /api/*. No Next.js imports, so tests can load it.
 *
 * The demo has no login, so the route handlers must only answer requests
 * that come from the app itself on loopback:
 * - Host allowlist blocks DNS rebinding (evil.example resolving to 127.0.0.1).
 * - Sec-Fetch-Site / Origin checks block cross-site requests from a browser.
 */

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export type GuardResult = { ok: true } | { ok: false; status: 403; message: string };

/** Default allowlist: localhost and 127.0.0.1 on the configured port. */
export function resolveAllowedHosts(allowedHostsEnv: string | undefined, portEnv: string | undefined): Set<string> {
  const configured = (allowedHostsEnv ?? "")
    .split(",")
    .map((h) => h.trim().toLowerCase())
    .filter(Boolean);
  if (configured.length > 0) {
    return new Set(configured);
  }
  const port = portEnv?.trim() || "3000";
  return new Set([`localhost:${port}`, `127.0.0.1:${port}`]);
}

function originHost(origin: string): string | null {
  try {
    const url = new URL(origin);
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    return url.host.toLowerCase();
  } catch {
    return null;
  }
}

export function checkApiRequest(input: {
  method: string;
  host: string | null;
  origin: string | null;
  secFetchSite: string | null;
  allowedHosts: Set<string>;
}): GuardResult {
  const host = input.host?.trim().toLowerCase() ?? "";
  if (!host || !input.allowedHosts.has(host)) {
    return {
      ok: false,
      status: 403,
      message: "Forbidden: Host is not allowed. Set ANONREQ_ALLOWED_HOSTS to change the allowlist.",
    };
  }

  const site = input.secFetchSite?.trim().toLowerCase();
  if (site && site !== "same-origin" && site !== "none") {
    return {
      ok: false,
      status: 403,
      message: "Forbidden: cross-site request. The API only accepts requests from this app.",
    };
  }

  const origin = input.origin?.trim();
  const method = input.method.toUpperCase();
  if (origin && origin !== "null") {
    const oh = originHost(origin);
    if (oh !== host) {
      return {
        ok: false,
        status: 403,
        message: "Forbidden: Origin does not match Host.",
      };
    }
  } else if (!SAFE_METHODS.has(method)) {
    return {
      ok: false,
      status: 403,
      message: `Forbidden: ${method} requests must send an Origin header matching the Host.`,
    };
  }
  return { ok: true };
}
