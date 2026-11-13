import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { NextIntlClientProvider } from "next-intl";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { StaffChat, type StaffChatProps } from "@/components/staff-chat";

const bg = JSON.parse(readFileSync(new URL("../messages/bg.json", import.meta.url), "utf8")) as Record<string, unknown>;

function render(overrides: Partial<StaffChatProps>): string {
  const props: StaffChatProps = {
    bggptAlias: "bggpt",
    aliasConfirmed: false,
    detectionLocale: "bg",
    localeRefusal: null,
    isAdmin: false,
    exportHref: "/api/audit/export?sort=timestamp:desc",
    ...overrides,
  };
  return renderToStaticMarkup(
    createElement(NextIntlClientProvider, { locale: "bg", messages: bg, timeZone: "Europe/Sofia" }, createElement(StaffChat, props)),
  );
}

test("staff view hides the admin block and export link when not in admin context", () => {
  const html = render({ isAdmin: false });
  assert.equal(html.includes('data-testid="staff-admin"'), false);
  assert.equal(html.includes('data-testid="audit-export-link"'), false);
  assert.equal(html.includes("/api/audit/export"), false);
  assert.ok(html.includes('data-testid="masking-view"'));
});

test("staff view shows the admin block with the export link in admin context", () => {
  const html = render({ isAdmin: true });
  assert.ok(html.includes('data-testid="staff-admin"'));
  assert.ok(html.includes('href="/api/audit/export?sort=timestamp:desc"'));
  assert.ok(html.includes("Изтегли одитен CSV"));
});

test("staff view renders the BG refusal and disables Send when the locale is refused", () => {
  const html = render({ localeRefusal: { locale: "bg", supported: ["en", "de-DE"] } });
  assert.ok(html.includes('data-testid="locale-refused"'));
  assert.ok(html.includes("все още не се поддържа от шлюза"));
  assert.match(html, /<button[^>]*disabled=""[^>]*data-testid="staff-send"/);
});

test("prompt lang follows the detection locale, not a hard-coded bg", () => {
  assert.match(render({ detectionLocale: "de-DE" }), /<textarea[^>]*lang="de"/);
  assert.match(render({ detectionLocale: "bg" }), /<textarea[^>]*lang="bg"/);
});
