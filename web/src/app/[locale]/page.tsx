import { getTranslations, setRequestLocale } from "next-intl/server";
import { Playground } from "@/components/playground";
import { isAppLocale } from "@/i18n/routing";

export default async function PlaygroundPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isAppLocale(locale)) {
    return null;
  }
  setRequestLocale(locale);
  const t = await getTranslations("playground");

  return (
    <main id="main" className="mx-auto max-w-6xl px-4 py-8">
      <p className="font-mono text-xs uppercase tracking-[0.16em] text-[#9a3412]">{t("eyebrow")}</p>
      <h1 className="mt-2 max-w-3xl text-balance font-serif text-4xl leading-tight sm:text-5xl">{t("title")}</h1>
      <p className="mt-3 max-w-3xl text-lg leading-7 text-muted-foreground">{t("lede")}</p>
      <Playground />
    </main>
  );
}
