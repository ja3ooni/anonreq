/**
 * Admin gate for every /api/audit/* route, enforced in middleware.
 * Runtime-agnostic (Edge middleware and Node): Web Crypto only, no node:crypto or Buffer. No Next.js or
 * path-alias imports, so tests can load it. Callers pass env values read per request
 * (process.env inside the handler), never module-level constants or NEXT_PUBLIC_ vars, so a
 * built/standalone server picks up ANONREQ_UI_ADMIN / ANONREQ_UI_ADMIN_TOKEN at runtime.
 */

/** ANONREQ_UI_ADMIN is on for "1", "true" or "yes" (case-insensitive). */
export function resolveAdminContext(flag: string | undefined): boolean {
  const value = flag?.trim().toLowerCase();
  return value === "1" || value === "true" || value === "yes";
}

export type AdminAccess = { ok: true } | { ok: false; status: 401 | 403; message: string };

/** True for /api/audit and anything below it (events, export, config-history, verify, …). */
export function isAuditApiPath(pathname: string): boolean {
  return pathname === "/api/audit" || pathname.startsWith("/api/audit/");
}

/**
 * - ANONREQ_UI_ADMIN off → 403.
 * - NODE_ENV=production without ANONREQ_UI_ADMIN_TOKEN → 403 (fail closed: production never
 *   serves audit data on the flag alone).
 * - ANONREQ_UI_ADMIN_TOKEN set → HTTP Basic auth is required; the password must equal the
 *   token (any user name). Missing or wrong credentials → 401 (caller adds the challenge).
 */
export async function checkAdminAccess(input: {
  adminFlag: string | undefined;
  adminToken: string | undefined;
  authorization: string | null;
  nodeEnv: string | undefined;
}): Promise<AdminAccess> {
  if (!resolveAdminContext(input.adminFlag)) {
    return { ok: false, status: 403, message: "Audit routes are admin only. ANONREQ_UI_ADMIN is off." };
  }
  const token = input.adminToken?.trim() ?? "";
  if (!token) {
    if (input.nodeEnv === "production") {
      return {
        ok: false,
        status: 403,
        message: "ANONREQ_UI_ADMIN_TOKEN is required when NODE_ENV=production. Audit routes are closed.",
      };
    }
    return { ok: true };
  }
  const password = basicPassword(input.authorization);
  if (password === null || !(await digestEqual(password, token))) {
    return { ok: false, status: 401, message: "Admin credentials required" };
  }
  return { ok: true };
}

/** Back-compat name used by the export tests. */
export const checkExportAccess = checkAdminAccess;

export const BASIC_CHALLENGE = 'Basic realm="AnonReq admin", charset="UTF-8"';

function basicPassword(header: string | null): string | null {
  const match = /^Basic\s+([A-Za-z0-9+/=]+)$/i.exec(header?.trim() ?? "");
  if (!match?.[1]) {
    return null;
  }
  let decoded: string;
  try {
    const binary = atob(match[1]);
    decoded = new TextDecoder().decode(Uint8Array.from(binary, (char) => char.charCodeAt(0)));
  } catch {
    return null;
  }
  const colon = decoded.indexOf(":");
  return colon === -1 ? null : decoded.slice(colon + 1);
}

async function sha256(value: string): Promise<Uint8Array> {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)));
}

/**
 * Hash both sides with SHA-256 (Web Crypto, works in Edge and Node), then compare the
 * fixed-length digests in constant time, so neither the content nor the length leaks.
 */
async function digestEqual(a: string, b: string): Promise<boolean> {
  const [left, right] = await Promise.all([sha256(a), sha256(b)]);
  let diff = 0;
  for (let index = 0; index < left.length; index += 1) {
    diff |= (left[index] ?? 0) ^ (right[index] ?? 0);
  }
  return diff === 0 && left.length === right.length;
}
