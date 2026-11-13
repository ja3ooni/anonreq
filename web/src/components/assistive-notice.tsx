import { getTranslations } from "next-intl/server";

/**
 * Persistent "assistive only" notice, rendered by the locale layout on every page and
 * kept visible while scrolling. Text comes from the active locale (bg / en / de).
 */
export async function AssistiveNotice() {
  const t = await getTranslations("notice");
  return (
    <aside
      role="note"
      aria-label={t("label")}
      data-testid="assistive-notice"
      className="sticky top-0 z-40 border-b-2 border-[#9a3412] bg-[#fff4e5] text-[#1a1814]"
    >
      <div className="mx-auto flex max-w-7xl flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-2 leading-snug">
        <strong className="text-sm font-semibold">
          <span aria-hidden="true" className="mr-1.5">⚠</span>
          {t("assistive")}
        </strong>
        <span className="text-sm text-[#4e4942]">{t("detail")}</span>
      </div>
    </aside>
  );
}
