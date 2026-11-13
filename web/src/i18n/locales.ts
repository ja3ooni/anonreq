/**
 * Locale constants with no Next.js imports, so node:test can load them.
 * `routing.ts` builds the next-intl routing from this list.
 */

export const LOCALES = ["en", "de", "bg"] as const;

export type AppLocale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: AppLocale = "en";

export function isAppLocale(value: string): value is AppLocale {
  return LOCALES.some((locale) => locale === value);
}

/** Order of the header language switch: BG / EN / DE. */
export const SWITCH_ORDER: readonly AppLocale[] = ["bg", "en", "de"];

/** Each language names itself, so a reader finds their own language in any UI. */
export const LOCALE_ENDONYMS: Record<AppLocale, string> = {
  bg: "Български",
  en: "English",
  de: "Deutsch",
};

/** BCP 47 tag for Intl date/number formatting. */
export const INTL_LOCALE: Record<AppLocale, string> = {
  bg: "bg-BG",
  en: "en-GB",
  de: "de-DE",
};

export function intlLocaleFor(locale: string): string {
  return isAppLocale(locale) ? INTL_LOCALE[locale] : INTL_LOCALE[DEFAULT_LOCALE];
}

export interface LanguageSwitchOption {
  code: AppLocale;
  label: string;
  endonym: string;
  hrefLang: AppLocale;
  lang: AppLocale;
  current: boolean;
}

export function languageSwitchOptions(current: string): LanguageSwitchOption[] {
  return SWITCH_ORDER.map((code) => ({
    code,
    label: code.toUpperCase(),
    endonym: LOCALE_ENDONYMS[code],
    hrefLang: code,
    lang: code,
    current: code === current,
  }));
}
