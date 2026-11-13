import { notFound } from "next/navigation";
import { connection } from "next/server";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { StaffChat } from "@/components/staff-chat";
import { isAppLocale } from "@/i18n/routing";
import { isMockMode } from "@/lib/gateway";
import {
  AUDIT_EXPORT_HREF,
  negotiateGatewayLocale,
  resolveBgGptAlias,
  staffAdminSectionVisible,
  staffDetectionLocale,
} from "@/lib/staff-config";

export const dynamic = "force-dynamic";

function mockModeOrFalse(): boolean {
  try {
    return isMockMode();
  } catch {
    // Mock refused (e.g. production): treat as live, which is the stricter path.
    return false;
  }
}

export default async function StaffPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isAppLocale(locale)) {
    notFound();
  }
  setRequestLocale(locale);
  // Read ANONREQ_* per request, not at build time.
  await connection();
  const t = await getTranslations("staff");
  // Server-side only: the browser cannot claim admin context.
  const showAdmin = staffAdminSectionVisible(process.env.ANONREQ_UI_ADMIN);
  const bggpt = resolveBgGptAlias(process.env.ANONREQ_BGGPT_ALIAS);
  const detectionLocale = staffDetectionLocale(locale);
  const negotiation = negotiateGatewayLocale(detectionLocale, {
    mock: mockModeOrFalse(),
    gatewayLocales: process.env.ANONREQ_GATEWAY_LOCALES,
  });

  return (
    <main id="main" className="mx-auto max-w-7xl px-4 py-8">
      <p className="font-mono text-xs uppercase tracking-[0.12em] text-[#9a3412]">{t("eyebrow")}</p>
      <h1 className="mt-2 max-w-4xl text-balance font-serif text-3xl leading-tight sm:text-4xl">{t("title")}</h1>
      <p className="mt-3 max-w-3xl text-lg leading-7 text-muted-foreground">{t("lede")}</p>
      <StaffChat
        bggptAlias={bggpt.alias}
        aliasConfirmed={bggpt.accepted}
        detectionLocale={detectionLocale}
        localeRefusal={negotiation.ok ? null : { locale: negotiation.locale, supported: negotiation.supported }}
        isAdmin={showAdmin}
        exportHref={AUDIT_EXPORT_HREF}
      />
    </main>
  );
}
