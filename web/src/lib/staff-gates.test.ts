import assert from "node:assert/strict";
import test from "node:test";

import { readdirSync } from "node:fs";

import { checkAdminAccess, checkExportAccess, isAuditApiPath } from "./admin-gate.ts";
import {
  DEFAULT_GATEWAY_LOCALES,
  negotiateGatewayLocale,
  resolveGatewayLocales,
  staffAdminSectionVisible,
  staffDetectionLocale,
} from "./staff-config.ts";

const basic = (user: string, password: string) => `Basic ${Buffer.from(`${user}:${password}`).toString("base64")}`;

test("staff admin section is hidden unless ANONREQ_UI_ADMIN is on", () => {
  for (const off of [undefined, "", "false", "0", "no", "admin"]) {
    assert.equal(staffAdminSectionVisible(off), false, String(off));
  }
  for (const on of ["true", "TRUE", "1", "yes"]) {
    assert.equal(staffAdminSectionVisible(on), true, on);
  }
});

test("audit export returns 403 while ANONREQ_UI_ADMIN is off, even with credentials", () => {
  for (const flag of [undefined, "false"]) {
    const result = checkExportAccess({ adminFlag: flag, adminToken: "s3cret", authorization: basic("admin", "s3cret") });
    assert.deepEqual(result.ok ? 200 : result.status, 403);
  }
});

test("audit export is open in admin context without a token", () => {
  assert.equal(checkExportAccess({ adminFlag: "true", adminToken: undefined, authorization: null }).ok, true);
  assert.equal(checkExportAccess({ adminFlag: "true", adminToken: "  ", authorization: null }).ok, true);
});

test("audit export requires Basic auth matching ANONREQ_UI_ADMIN_TOKEN when set", () => {
  const gate = (authorization: string | null) =>
    checkExportAccess({ adminFlag: "true", adminToken: "s3cret", authorization });
  const status = (result: ReturnType<typeof gate>) => (result.ok ? 200 : result.status);
  assert.equal(status(gate(null)), 401);
  assert.equal(status(gate("Bearer s3cret")), 401);
  assert.equal(status(gate(basic("admin", "wrong"))), 401);
  assert.equal(status(gate(basic("admin", "s3cret-longer"))), 401);
  assert.equal(status(gate("Basic !!!")), 401);
  assert.equal(status(gate(basic("admin", "s3cret"))), 200);
  assert.equal(status(gate(basic("anyone", "s3cret"))), 200);
});

test("live mode refuses bg by default and never rewrites the locale", () => {
  const result = negotiateGatewayLocale("bg", { mock: false, gatewayLocales: undefined });
  assert.equal(result.ok, false);
  if (!result.ok) {
    assert.equal(result.reason, "unsupported_locale");
    assert.equal(result.locale, "bg");
    assert.deepEqual(result.supported, [...DEFAULT_GATEWAY_LOCALES]);
    assert.equal(result.supported.includes("bg"), false);
  }
  const bgBG = negotiateGatewayLocale("bg-BG", { mock: false, gatewayLocales: "" });
  assert.equal(bgBG.ok, false);
});

test("live mode accepts locales the gateway ships, matching on primary language", () => {
  for (const ok of ["en", "de-DE", "de", "fr-FR", "ar", "pt-BR"]) {
    const result = negotiateGatewayLocale(ok, { mock: false, gatewayLocales: undefined });
    assert.deepEqual(result, { ok: true, locale: ok });
  }
  assert.equal(negotiateGatewayLocale(staffDetectionLocale("en"), { mock: false, gatewayLocales: undefined }).ok, true);
  assert.equal(negotiateGatewayLocale(staffDetectionLocale("de"), { mock: false, gatewayLocales: undefined }).ok, true);
  assert.equal(negotiateGatewayLocale(staffDetectionLocale("bg"), { mock: false, gatewayLocales: undefined }).ok, false);
});

test("ANONREQ_GATEWAY_LOCALES overrides the list, e.g. once bg.yaml ships", () => {
  assert.deepEqual(resolveGatewayLocales("en, bg ,de-DE"), ["en", "bg", "de-DE"]);
  assert.deepEqual(resolveGatewayLocales("not a locale!,"), [...DEFAULT_GATEWAY_LOCALES]);
  assert.deepEqual(negotiateGatewayLocale("bg", { mock: false, gatewayLocales: "en,bg" }), { ok: true, locale: "bg" });
  // The override replaces the default, it does not extend it.
  assert.equal(negotiateGatewayLocale("fr-FR", { mock: false, gatewayLocales: "en,bg" }).ok, false);
});

test("mock mode accepts bg because the mock recognizers handle it", () => {
  assert.deepEqual(negotiateGatewayLocale("bg", { mock: true, gatewayLocales: undefined }), { ok: true, locale: "bg" });
});

const AUDIT_ROUTE_DIRS = readdirSync(new URL("../app/api/audit/", import.meta.url), { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name);

test("every /api/audit/* route is covered by the middleware admin gate", () => {
  for (const expected of ["events", "export", "config-history", "verify"]) {
    assert.ok(AUDIT_ROUTE_DIRS.includes(expected), `missing route dir ${expected}`);
  }
  for (const dir of AUDIT_ROUTE_DIRS) {
    assert.equal(isAuditApiPath(`/api/audit/${dir}`), true, dir);
  }
  assert.equal(isAuditApiPath("/api/audit"), true);
  assert.equal(isAuditApiPath("/api/audit/anything/new"), true);
  for (const other of ["/api/auditx", "/api/chat", "/api/preview", "/api/models", "/api/status", "/bg/audit"]) {
    assert.equal(isAuditApiPath(other), false, other);
  }
});

test("all audit routes: 403 when admin is off, 401 without Basic auth when a token is set", () => {
  for (const dir of AUDIT_ROUTE_DIRS) {
    const path = `/api/audit/${dir}`;
    assert.equal(isAuditApiPath(path), true);
    const off = checkAdminAccess({ adminFlag: undefined, adminToken: undefined, authorization: null });
    assert.equal(off.ok ? 200 : off.status, 403, path);
    const noCreds = checkAdminAccess({ adminFlag: "true", adminToken: "t0ken", authorization: null });
    assert.equal(noCreds.ok ? 200 : noCreds.status, 401, path);
    const good = checkAdminAccess({ adminFlag: "true", adminToken: "t0ken", authorization: basic("ops", "t0ken") });
    assert.equal(good.ok, true, path);
    const open = checkAdminAccess({ adminFlag: "true", adminToken: undefined, authorization: null });
    assert.equal(open.ok, true, path);
  }
});

test("Basic auth decodes UTF-8 passwords and rejects malformed headers", () => {
  const gate = (authorization: string | null) => checkAdminAccess({ adminFlag: "yes", adminToken: "пароль-ä", authorization });
  assert.equal(gate(basic("u", "пароль-ä")).ok, true);
  assert.equal(gate(basic("u", "пароль-a")).ok, false);
  assert.equal(gate(`Basic ${Buffer.from("no-colon").toString("base64")}`).ok, false);
  assert.equal(gate("Basic ====").ok, false);
});
