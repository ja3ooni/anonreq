"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState, type ReactNode } from "react";
import { Link, usePathname } from "@/i18n/navigation";

type GatewayState = "loading" | "mock" | "up" | "down" | "unconfigured";

export function SiteHeader() {
  const t = useTranslations("nav");
  const status = useTranslations("status");
  const pathname = usePathname();
  const locale = useLocale();
  const [gateway, setGateway] = useState<GatewayState>("loading");

  useEffect(() => {
    let cancelled = false;
    fetch("/api/status")
      .then((response) => response.json())
      .then((body: { mode?: string; gateway?: string }) => {
        if (cancelled) {
          return;
        }
        if (body.mode === "mock") {
          setGateway("mock");
          return;
        }
        if (body.gateway === "up") {
          setGateway("up");
          return;
        }
        if (body.gateway === "unconfigured") {
          setGateway("unconfigured");
          return;
        }
        setGateway("down");
      })
      .catch(() => {
        if (!cancelled) {
          setGateway("down");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const statusLabel =
    gateway === "loading"
      ? status("loading")
      : gateway === "mock"
        ? status("mock")
        : gateway === "up"
          ? status("live")
          : gateway === "unconfigured"
            ? status("unconfigured")
            : status("down");

  const statusClass =
    gateway === "mock"
      ? "bg-[#f3d7a1] text-[#1a1814]"
      : gateway === "up"
        ? "bg-[#b7e0d6] text-[#1a1814]"
        : gateway === "loading"
          ? "bg-[#e7e0d4] text-[#1a1814]"
          : "bg-[#f3c1c1] text-[#1a1814]";

  return (
    <header className="border-b border-[#2a2622] bg-[#1a1814] text-[#f6f1e8]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-[#f6f1e8] focus:px-3 focus:py-2 focus:text-[#1a1814]"
      >
        {t("skip")}
      </a>
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-4">
        <Link
          href="/"
          className="flex items-center gap-2 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#e7a07a]"
        >
          <span className="grid h-8 w-8 place-items-center rounded-md bg-[#f3efe6] font-serif text-sm text-[#1a1814]">
            AR
          </span>
          <span className="font-serif text-xl tracking-tight">AnonReq</span>
        </Link>
        <nav aria-label={t("primary")} className="flex items-center gap-1">
          <NavLink href="/" current={pathname === "/"}>
            {t("playground")}
          </NavLink>
          <NavLink href="/audit" current={pathname.startsWith("/audit")}>
            {t("audit")}
          </NavLink>
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <p
            role="status"
            className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusClass}`}
          >
            {statusLabel}
          </p>
          <div role="group" aria-label={t("language")} className="flex rounded-md bg-[#2a2622] p-0.5">
            {(["en", "de"] as const).map((code) => (
              <Link
                key={code}
                href={pathname}
                locale={code}
                hrefLang={code}
                lang={code}
                aria-current={locale === code ? "true" : undefined}
                className={`rounded px-2 py-1 text-xs font-medium uppercase focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#e7a07a] ${
                  locale === code ? "bg-[#f6f1e8] text-[#1a1814]" : "text-[#f6f1e8]"
                }`}
              >
                {code}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </header>
  );
}

function NavLink({
  href,
  current,
  children,
}: {
  href: "/" | "/audit";
  current: boolean;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-current={current ? "page" : undefined}
      className={`rounded-sm px-2 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#e7a07a] ${
        current ? "border-b-2 border-[#e7a07a] text-[#f6f1e8]" : "text-[#d9d0c3]"
      }`}
    >
      {children}
    </Link>
  );
}
