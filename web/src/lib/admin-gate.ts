/**
 * Admin gate for every /api/audit/* route, enforced in middleware.
 * Runtime-agnostic (Edge middleware and Node): no node:crypto or Buffer. No Next.js or
 * path-alias imports, so tests can load it.
 */

import { resolveAdminContext } from "./staff-config.ts";

export type AdminAccess = { ok: true } | { ok: false; status: 401 | 403; message: string };

/** True for /api/audit and anything below it (events, export, config-history, verify, …). */
export function isAuditApiPath(pathname: string): boolean {
  return pathname === "/api/audit" || pathname.startsWith("/api/audit/");
}

/**
 * - ANONREQ_UI_ADMIN off → 403.
 * - ANONREQ_UI_ADMIN_TOKEN set → HTTP Basic auth is required; the password must equal the
 *   token (any user name). Missing or wrong credentials → 401 (caller adds the challenge).
 */
export function checkAdminAccess(input: {
  adminFlag: string | undefined;
  adminToken: string | undefined;
  authorization: string | null;
}): AdminAccess {
  if (!resolveAdminContext(input.adminFlag)) {
    return { ok: false, status: 403, message: "Audit routes are admin only. ANONREQ_UI_ADMIN is off." };
  }
  const token = input.adminToken?.trim() ?? "";
  if (!token) {
    return { ok: true };
  }
  const password = basicPassword(input.authorization);
  if (password === null || !constantTimeEqual(password, token)) {
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

function constantTimeEqual(a: string, b: string): boolean {
  const left = new TextEncoder().encode(a);
  const right = new TextEncoder().encode(b);
  let diff = left.length ^ right.length;
  const length = Math.max(left.length, right.length);
  for (let index = 0; index < length; index += 1) {
    diff |= (left[index] ?? 0) ^ (right[index] ?? 0);
  }
  return diff === 0;
}
