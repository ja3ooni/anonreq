import { IBM_Plex_Mono, Newsreader, PT_Serif, Source_Sans_3 } from "next/font/google";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations, setRequestLocale } from "next-intl/server";
import { AssistiveNotice } from "@/components/assistive-notice";
import { SiteHeader } from "@/components/site-header";
import { isAppLocale, routing } from "@/i18n/routing";
import "../globals.css";

// Cyrillic subsets so Bulgarian renders in the brand fonts instead of a system fallback.
const sourceSans = Source_Sans_3({
  subsets: ["latin", "latin-ext", "cyrillic"],
  variable: "--font-source",
  display: "swap",
});

const newsreader = Newsreader({
  subsets: ["latin", "latin-ext"],
  variable: "--font-newsreader",
  display: "swap",
  // No metric fallback face: it would claim Cyrillic glyphs before PT Serif in the stack.
  adjustFontFallback: false,
});

// Newsreader has no Cyrillic glyphs. PT Serif (designed for Cyrillic) follows it in the
// --font-serif stack, so Bulgarian headings fall back per glyph to a matching serif.
const ptSerif = PT_Serif({
  subsets: ["latin", "cyrillic", "cyrillic-ext"],
  weight: ["400", "700"],
  variable: "--font-pt-serif",
  display: "swap",
});

const plex = IBM_Plex_Mono({
  subsets: ["latin", "latin-ext", "cyrillic"],
  weight: ["400", "500"],
  variable: "--font-plex",
  display: "swap",
});

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isAppLocale(locale)) {
    return {};
  }
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "meta" });
  return {
    title: t("title"),
    description: t("description"),
  };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!isAppLocale(locale)) {
    notFound();
  }
  setRequestLocale(locale);
  const messages = await getMessages();
  const footer = await getTranslations("footer");

  return (
    <html lang={locale} className={`${sourceSans.variable} ${newsreader.variable} ${ptSerif.variable} ${plex.variable}`}>
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        <NextIntlClientProvider messages={messages}>
          <SiteHeader />
          <AssistiveNotice />
          {children}
          <footer className="mx-auto max-w-6xl px-4 py-8 text-sm text-muted-foreground">{footer("note")}</footer>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
