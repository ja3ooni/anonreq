/**
 * Server-only admin gate for audit export. No Next.js or path-alias imports, so tests can load it.
 */

import { timingSafeEqual } from "node:crypto";
import { resolveAdminContext } from "./staff-config.ts";

export type ExportAccess = { ok: true } | { ok: false; status: 401 | 403; message: string };

/**
 * Server-side gate for /api/audit/export.
 * - ANONREQ_UI_ADMIN off → 403.
 * - ANONREQ_UI_ADMIN_TOKEN set → HTTP Basic auth is required; the password must equal the
 *   token (any user name). Missing or wrong credentials → 401 with a Basic challenge.
 */
export function checkExportAccess(input: {
  adminFlag: string | undefined;
  adminToken: string | undefined;
  authorization: string | null;
}): ExportAccess {
  if (!resolveAdminContext(input.adminFlag)) {
    return { ok: false, status: 403, message: "Audit export is admin only. ANONREQ_UI_ADMIN is off." };
  }
  const token = input.adminToken?.trim() ?? "";
  if (!token) {
    return { ok: true };
  }
  const password = basicPassword(input.authorization);
  if (password === null || !safeEqual(password, token)) {
    return { ok: false, status: 401, message: "Admin credentials required" };
  }
  return { ok: true };
}

function basicPassword(header: string | null): string | null {
  const match = /^Basic\s+([A-Za-z0-9+/=]+)$/i.exec(header?.trim() ?? "");
  if (!match?.[1]) {
    return null;
  }
  const decoded = Buffer.from(match[1], "base64").toString("utf8");
  const colon = decoded.indexOf(":");
  return colon === -1 ? null : decoded.slice(colon + 1);
}

function safeEqual(a: string, b: string): boolean {
  const left = Buffer.from(a, "utf8");
  const right = Buffer.from(b, "utf8");
  return left.length === right.length && timingSafeEqual(left, right);
}

