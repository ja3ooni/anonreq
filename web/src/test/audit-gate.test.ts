import assert from "node:assert/strict";
import { readdirSync } from "node:fs";
import { afterEach, beforeEach, test } from "node:test";

import { NextRequest } from "next/server";

import middleware from "@/middleware";

const ORIGIN = "http://127.0.0.1:3000";
const AUDIT_ROUTES = readdirSync(new URL("../app/api/audit/", import.meta.url), { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name);
const KEYS = ["ANONREQ_UI_ADMIN", "ANONREQ_UI_ADMIN_TOKEN", "ANONREQ_ALLOWED_HOSTS", "NODE_ENV", "PORT"] as const;
const env = process.env as Record<string, string | undefined>;
let saved: Record<string, string | undefined> = {};

beforeEach(() => {
  saved = Object.fromEntries(KEYS.map((key) => [key, env[key]]));
  for (const key of KEYS) {
    delete env[key];
  }
  env.NODE_ENV = "test";
});

afterEach(() => {
  for (const key of KEYS) {
    if (saved[key] === undefined) {
      delete env[key];
    } else {
      env[key] = saved[key];
    }
  }
});

const get = (path: string, headers: Record<string, string> = {}) =>
  new NextRequest(`${ORIGIN}${path}`, { headers: { host: "127.0.0.1:3000", ...headers } });
const basic = (user: string, password: string) => `Basic ${Buffer.from(`${user}:${password}`).toString("base64")}`;

test("every /api/audit/* route: 403 while ANONREQ_UI_ADMIN is off", async () => {
  assert.ok(AUDIT_ROUTES.length >= 4);
  for (const route of AUDIT_ROUTES) {
    assert.equal((await middleware(get(`/api/audit/${route}`, { authorization: basic("a", "x") }))).status, 403, route);
  }
});

test("every /api/audit/* route: 401 + Basic challenge without the right token, pass-through with it", async () => {
  env.ANONREQ_UI_ADMIN = "true";
  env.ANONREQ_UI_ADMIN_TOKEN = "s3cret";
  for (const route of AUDIT_ROUTES) {
    for (const headers of [{}, { authorization: basic("ops", "nope") }]) {
      const response = await middleware(get(`/api/audit/${route}`, headers));
      assert.equal(response.status, 401, route);
      assert.match(response.headers.get("www-authenticate") ?? "", /^Basic /);
    }
    const ok = await middleware(get(`/api/audit/${route}`, { authorization: basic("ops", "s3cret") }));
    assert.equal(ok.headers.get("x-middleware-next"), "1", route);
  }
});

test("production without a token fails closed on every audit route", async () => {
  env.ANONREQ_UI_ADMIN = "true";
  env.NODE_ENV = "production";
  for (const route of AUDIT_ROUTES) {
    assert.equal((await middleware(get(`/api/audit/${route}`))).status, 403, route);
  }
});

test("env is read per request: flipping it between calls changes the answer", async () => {
  assert.equal((await middleware(get("/api/audit/events"))).status, 403);
  env.ANONREQ_UI_ADMIN = "true";
  assert.equal((await middleware(get("/api/audit/events"))).headers.get("x-middleware-next"), "1");
  env.ANONREQ_UI_ADMIN_TOKEN = "t";
  assert.equal((await middleware(get("/api/audit/events"))).status, 401);
});

test("non-audit API routes are not admin gated", async () => {
  assert.equal((await middleware(get("/api/status"))).headers.get("x-middleware-next"), "1");
});
