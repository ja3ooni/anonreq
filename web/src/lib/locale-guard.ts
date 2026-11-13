import { isMockMode } from "@/lib/gateway";
import { negotiateGatewayLocale } from "@/lib/staff-config";

/**
 * Refuses a detection locale the gateway has no bundle for (live mode). The locale is never
 * rewritten and the X-AnonReq-Locale header is never dropped. Returns a 422 response or null.
 */
export function refuseUnsupportedLocale(locale: string): Response | null {
  const result = negotiateGatewayLocale(locale, {
    mock: isMockMode(),
    gatewayLocales: process.env.ANONREQ_GATEWAY_LOCALES,
  });
  if (result.ok) {
    return null;
  }
  return Response.json(
    {
      error: {
        message: `The gateway has no locale bundle for "${result.locale}". Supported: ${result.supported.join(", ")}.`,
        status: 422,
      },
      code: "unsupported_locale",
      locale: result.locale,
      supported: result.supported,
    },
    { status: 422, headers: { "cache-control": "no-store" } },
  );
}
