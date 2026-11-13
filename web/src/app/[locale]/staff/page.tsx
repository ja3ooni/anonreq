import { connection } from "next/server";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { StaffChat } from "@/components/staff-chat";
import { isAppLocale } from "@/i18n/routing";
import {
  AUDIT_EXPORT_HREF,
  BGGPT_ALIAS_CONFIRMED,
  resolveAdminContext,
  resolveBgGptAlias,
  staffDetectionLocale,
} from "@/lib/staff-config";

export const dynamic = "force-dynamic";

export default async function StaffPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isAppLocale(locale)) {
    return null;
  }
  setRequestLocale(locale);
  // Read ANONREQ_UI_ADMIN / ANONREQ_BGGPT_ALIAS per request, not at build time.
  await connection();
  const t = await getTranslations("staff");
  // Server-side only: the browser cannot claim admin context.
  const isAdmin = resolveAdminContext(process.env.ANONREQ_UI_ADMIN);
  const bggptAlias = resolveBgGptAlias(process.env.ANONREQ_BGGPT_ALIAS);
  const aliasConfirmed = BGGPT_ALIAS_CONFIRMED || Boolean(process.env.ANONREQ_BGGPT_ALIAS?.trim());

  return (
    <main id="main" className="mx-auto max-w-7xl px-4 py-8">
      <p className="font-mono text-xs uppercase tracking-[0.12em] text-[#9a3412]">{t("eyebrow")}</p>
      <h1 className="mt-2 max-w-4xl text-balance font-serif text-3xl leading-tight sm:text-4xl">{t("title")}</h1>
      <p className="mt-3 max-w-3xl text-lg leading-7 text-muted-foreground">{t("lede")}</p>
      <StaffChat
        bggptAlias={bggptAlias}
        aliasConfirmed={aliasConfirmed}
        detectionLocale={staffDetectionLocale(locale)}
        isAdmin={isAdmin}
        exportHref={AUDIT_EXPORT_HREF}
      />
    </main>
  );
}
