import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  DEFAULT_LOCALE,
  LOCALES,
  intlLocaleFor,
  isAppLocale,
  languageSwitchOptions,
} from "../i18n/locales.ts";

type Messages = Record<string, Record<string, string>>;

function load(locale: string): Messages {
  return JSON.parse(readFileSync(new URL(`../messages/${locale}.json`, import.meta.url), "utf8")) as Messages;
}

function keys(messages: Messages): string[] {
  return Object.entries(messages)
    .filter(([namespace]) => !namespace.startsWith("_"))
    .flatMap(([namespace, entries]) => Object.keys(entries).map((key) => `${namespace}.${key}`))
    .sort();
}

const CYRILLIC = /[\u0400-\u04FF]/;
const en = load("en");
const de = load("de");
const bg = load("bg");

test("bg is a routed locale next to en and de", () => {
  assert.deepEqual([...LOCALES].sort(), ["bg", "de", "en"]);
  assert.equal(isAppLocale("bg"), true);
  assert.equal(isAppLocale("ru"), false);
  assert.equal(DEFAULT_LOCALE, "en");
  assert.equal(intlLocaleFor("bg"), "bg-BG");
  assert.equal(intlLocaleFor("xx"), "en-GB");
});

test("language switch offers BG / EN / DE with lang and hrefLang", () => {
  const options = languageSwitchOptions("bg");
  assert.deepEqual(
    options.map((option) => option.label),
    ["BG", "EN", "DE"],
  );
  for (const option of options) {
    assert.equal(option.lang, option.code);
    assert.equal(option.hrefLang, option.code);
  }
  assert.deepEqual(
    options.filter((option) => option.current).map((option) => option.code),
    ["bg"],
  );
  assert.equal(options[0]?.endonym, "Български");
  assert.equal(languageSwitchOptions("de").find((option) => option.current)?.code, "de");
});

test("bg, en and de message files have the same keys", () => {
  assert.deepEqual(keys(bg), keys(en));
  assert.deepEqual(keys(de), keys(en));
});

test("assistive-only notice is present in every language", () => {
  assert.equal(en.notice?.assistive, "Assistive only — a human must review");
  assert.match(de.notice?.assistive ?? "", /Mensch/);
  assert.equal(bg.notice?.assistive, "Само за помощ — човек трябва да прегледа отговора");
  for (const messages of [en, de, bg]) {
    assert.ok((messages.notice?.detail ?? "").length > 20);
  }
});

test("Bulgarian labels are Cyrillic, apart from technical names", () => {
  const technical = new Set(["meta.title", "common.missing", ...keys(bg).filter((key) => key.startsWith("headers."))]);
  const latinOnly = keys(bg).filter((key) => {
    const [namespace, entry] = key.split(".") as [string, string];
    return !technical.has(key) && !CYRILLIC.test(bg[namespace]?.[entry] ?? "");
  });
  assert.deepEqual(latinOnly, []);
});

test("every Bulgarian string is marked for native review by Ibtisam", () => {
  const meta = (bg as unknown as { _review?: { status?: string; reviewer?: string } })._review;
  assert.equal(meta?.reviewer, "Ibtisam");
  assert.match(meta?.status ?? "", /pending native review/);
  const review = readFileSync(new URL("../messages/REVIEW-bg.md", import.meta.url), "utf8");
  for (const key of keys(bg)) {
    const row = review.split("\n").find((line) => line.startsWith(`| \`${key}\` |`));
    assert.ok(row, `REVIEW-bg.md is missing ${key}`);
    assert.match(row, /\| (pending native review|approved|changed) \(Ibtisam\) \|$/);
  }
});
