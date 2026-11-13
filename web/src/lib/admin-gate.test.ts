import assert from "node:assert/strict";
import { readdirSync } from "node:fs";
import test from "node:test";

import { checkAdminAccess, isAuditApiPath, resolveAdminContext } from "./admin-gate.ts";

const basic = (user: string, password: string) => `Basic ${Buffer.from(`${user}:${password}`).toString("base64")}`;
const status = (result: Awaited<ReturnType<typeof checkAdminAccess>>) => (result.ok ? 200 : result.status);
const AUDIT_ROUTE_DIRS = readdirSync(new URL("../app/api/audit/", import.meta.url), { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name);

test("ANONREQ_UI_ADMIN parsing", () => {
  for (const off of [undefined, "", "false", "0", "no", "admin"]) {
    assert.equal(resolveAdminContext(off), false, String(off));
  }
  for (const on of ["true", "TRUE", " 1 ", "yes"]) {
    assert.equal(resolveAdminContext(on), true, on);
  }
});

test("every route dir under app/api/audit is an audit path; others are not", () => {
  for (const expected of ["events", "export", "config-history", "verify"]) {
    assert.ok(AUDIT_ROUTE_DIRS.includes(expected), expected);
  }
  for (const dir of AUDIT_ROUTE_DIRS) {
    assert.equal(isAuditApiPath(`/api/audit/${dir}`), true, dir);
  }
  assert.equal(isAuditApiPath("/api/audit"), true);
  for (const other of ["/api/auditx", "/api/chat", "/api/preview", "/api/status", "/en/audit"]) {
    assert.equal(isAuditApiPath(other), false, other);
  }
});

test("403 while ANONREQ_UI_ADMIN is off, even with valid credentials", async () => {
  const result = await checkAdminAccess({ adminFlag: "false", adminToken: "s3cret", authorization: basic("a", "s3cret"), nodeEnv: "test" });
  assert.equal(status(result), 403);
});

test("no token: open outside production, closed (403) in production", async () => {
  assert.equal(status(await checkAdminAccess({ adminFlag: "true", adminToken: undefined, authorization: null, nodeEnv: "development" })), 200);
  assert.equal(status(await checkAdminAccess({ adminFlag: "true", adminToken: "  ", authorization: null, nodeEnv: "test" })), 200);
  assert.equal(status(await checkAdminAccess({ adminFlag: "true", adminToken: undefined, authorization: null, nodeEnv: "production" })), 403);
});

test("token: Basic auth with the token as password, any user; else 401", async () => {
  const gate = async (authorization: string | null) =>
    status(await checkAdminAccess({ adminFlag: "true", adminToken: "s3cret", authorization, nodeEnv: "production" }));
  assert.equal(await gate(null), 401);
  assert.equal(await gate("Bearer s3cret"), 401);
  assert.equal(await gate(basic("a", "wrong")), 401);
  assert.equal(await gate(basic("a", "s3cret-longer")), 401);
  assert.equal(await gate(basic("a", "s3cre")), 401);
  assert.equal(await gate("Basic !!!"), 401);
  assert.equal(await gate("Basic ===="), 401);
  assert.equal(await gate(`Basic ${Buffer.from("no-colon").toString("base64")}`), 401);
  assert.equal(await gate(basic("admin", "s3cret")), 200);
  assert.equal(await gate(basic("anyone", "s3cret")), 200);
});

test("UTF-8 tokens compare correctly", async () => {
  const gate = async (password: string) =>
    (await checkAdminAccess({ adminFlag: "yes", adminToken: "пароль-ä", authorization: basic("u", password), nodeEnv: "test" })).ok;
  assert.equal(await gate("пароль-ä"), true);
  assert.equal(await gate("пароль-a"), false);
});
