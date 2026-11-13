/**
 * Staff-assistant pilot configuration. No Next.js or path-alias imports, so tests can load it.
 */

/**
 * OPEN QUESTION (DevOps): the BgGPT model alias is not in config/model_aliases*.yaml on main
 * or in any open PR yet. "bggpt" is a placeholder. Set ANONREQ_BGGPT_ALIAS once DevOps
 * publishes the real alias name.
 */
export const BGGPT_ALIAS_PLACEHOLDER = "bggpt";

const MODEL = /^[\w.:-]{1,128}$/;

export interface BgGptAlias {
  alias: string;
  /**
   * True only when ANONREQ_BGGPT_ALIAS was set, passed validation, and differs from the
   * placeholder. Setting it to "bggpt" explicitly does not confirm anything.
   */
  accepted: boolean;
}

export function resolveBgGptAlias(envValue: string | undefined): BgGptAlias {
  const value = envValue?.trim() ?? "";
  if (!MODEL.test(value)) {
    return { alias: BGGPT_ALIAS_PLACEHOLDER, accepted: false };
  }
  return { alias: value, accepted: value !== BGGPT_ALIAS_PLACEHOLDER };
}

/**
 * Moves the BgGPT alias to the front when the model list contains it. Never injects it:
 * outside mock mode the alias appears only if the gateway's /v1/models lists it.
 */
export function staffModelOptions(bggptAlias: string, models: readonly string[]): string[] {
  if (!models.includes(bggptAlias)) {
    return [...models];
  }
  return [bggptAlias, ...models.filter((model) => model !== bggptAlias)];
}

/** Model list for mock mode: the BgGPT alias is offered first so the pilot can be demoed. */
export function mockModelList(bggptAlias: string, fallback: readonly string[]): string[] {
  return [bggptAlias, ...fallback.filter((model) => model !== bggptAlias)];
}

/**
 * Admin context for the staff view and the audit export. The demo has no login, so the
 * operator sets ANONREQ_UI_ADMIN=true on the server for admin sessions.
 */
export function resolveAdminContext(flag: string | undefined): boolean {
  const value = flag?.trim().toLowerCase();
  return value === "1" || value === "true" || value === "yes";
}

/** The staff page renders the admin block (audit CSV export link) only in admin context. */
export function staffAdminSectionVisible(flag: string | undefined): boolean {
  return resolveAdminContext(flag);
}

/**
 * Locales the gateway ships bundles for (config/locales/*.yaml on main). There is no
 * gateway endpoint that lists them, so this is the default; override with
 * ANONREQ_GATEWAY_LOCALES (comma-separated) when the gateway gains a locale, e.g. bg.
 */
export const DEFAULT_GATEWAY_LOCALES = ["ar", "de-DE", "en", "es", "fr-FR", "it-IT", "nl-NL", "pt-BR"] as const;

export function resolveGatewayLocales(envValue: string | undefined): string[] {
  const list = (envValue ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter((item) => /^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$/.test(item));
  return list.length > 0 ? list : [...DEFAULT_GATEWAY_LOCALES];
}

export type LocaleNegotiation =
  | { ok: true; locale: string }
  | { ok: false; reason: "unsupported_locale"; locale: string; supported: string[] };

function primary(tag: string): string {
  return tag.split("-")[0]?.toLowerCase() ?? "";
}

/**
 * Decide whether a detection locale may be sent to the gateway.
 * The requested locale is never rewritten (bg is never mapped to en) and the header is
 * never dropped: an unsupported locale is refused instead. Mock mode supports every
 * locale its demo recognizers handle, including bg.
 */
export function negotiateGatewayLocale(
  requested: string,
  options: { mock: boolean; gatewayLocales: string | undefined },
): LocaleNegotiation {
  if (options.mock) {
    return { ok: true, locale: requested };
  }
  const supported = resolveGatewayLocales(options.gatewayLocales);
  const wanted = requested.toLowerCase();
  const match = supported.some((item) => item.toLowerCase() === wanted || primary(item) === primary(wanted));
  return match ? { ok: true, locale: requested } : { ok: false, reason: "unsupported_locale", locale: requested, supported };
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

/** Existing gateway export, proxied by /api/audit/export (admin only, see checkExportAccess). */
export const AUDIT_EXPORT_HREF = "/api/audit/export?sort=timestamp:desc";
