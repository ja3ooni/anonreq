/**
 * Staff-assistant pilot configuration. No Next.js or path-alias imports, so tests can load it.
 */

/**
 * OPEN QUESTION (DevOps): the BgGPT model alias is not in config/model_aliases*.yaml on main
 * or in any open PR yet. "bggpt" is a placeholder. Override it with ANONREQ_BGGPT_ALIAS once
 * DevOps publishes the real alias name, and update this default.
 */
export const BGGPT_ALIAS_PLACEHOLDER = "bggpt";
export const BGGPT_ALIAS_CONFIRMED = false;

const MODEL = /^[\w.:-]{1,128}$/;

export function resolveBgGptAlias(envValue: string | undefined): string {
  const value = envValue?.trim() ?? "";
  return MODEL.test(value) ? value : BGGPT_ALIAS_PLACEHOLDER;
}

/** BgGPT first, then the gateway's other aliases, without duplicates. */
export function staffModelOptions(bggptAlias: string, gatewayModels: readonly string[]): string[] {
  return [bggptAlias, ...gatewayModels.filter((model) => model !== bggptAlias)];
}

/**
 * Admin context for the staff view. The demo has no login, so the operator sets
 * ANONREQ_UI_ADMIN=true on the server for admin sessions. It only controls whether
 * the audit CSV export link is shown; the gateway still enforces the admin key.
 */
export function resolveAdminContext(flag: string | undefined): boolean {
  const value = flag?.trim().toLowerCase();
  return value === "1" || value === "true" || value === "yes";
}

/** Detection locale sent as X-AnonReq-Locale from the staff view, per UI language. */
export const STAFF_DETECTION_LOCALE: Record<string, string> = {
  bg: "bg",
  en: "en",
  de: "de-DE",
};

export function staffDetectionLocale(uiLocale: string): string {
  return STAFF_DETECTION_LOCALE[uiLocale] ?? "en";
}

/** Existing gateway export, proxied by /api/audit/export. */
export const AUDIT_EXPORT_HREF = "/api/audit/export?sort=timestamp:desc";
