import assert from "node:assert/strict";
import { readdirSync } from "node:fs";
import { afterEach, beforeEach, test } from "node:test";

import { NextRequest } from "next/server";

import middleware from "@/middleware";
import { POST as chatPOST } from "@/app/api/chat/route";
import { POST as previewPOST } from "@/app/api/preview/route";

const ORIGIN = "http://127.0.0.1:3000";
const AUDIT_ROUTES = readdirSync(new URL("../app/api/audit/", import.meta.url), { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name);

const KEYS = [
  "ANONREQ_MOCK",
  "ANONREQ_TENANT_ID",
  "ANONREQ_GATEWAY_URL",
  "ANONREQ_API_KEY",
  "ANONREQ_GATEWAY_LOCALES",
  "ANONREQ_UI_ADMIN",
  "ANONREQ_UI_ADMIN_TOKEN",
  "ANONREQ_ALLOWED_HOSTS",
  "NODE_ENV",
  "PORT",
] as const;
let saved: Record<string, string | undefined> = {};
const env = process.env as Record<string, string | undefined>;

beforeEach(() => {
  saved = Object.fromEntries(KEYS.map((key) => [key, env[key]]));
  for (const key of KEYS) {
    delete env[key];
  }
  env.ANONREQ_TENANT_ID = "default";
  // Unreachable on purpose: a refused request must never get as far as the gateway.
  env.ANONREQ_GATEWAY_URL = "http://127.0.0.1:9";
  env.ANONREQ_API_KEY = "test-gateway-key";
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

function jsonPost(path: string, body: unknown): Request {
  return new Request(`${ORIGIN}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json", origin: ORIGIN, host: "127.0.0.1:3000" },
    body: JSON.stringify(body),
  });
}

function auditGet(route: string, headers: Record<string, string> = {}): NextRequest {
  return new NextRequest(`${ORIGIN}/api/audit/${route}`, { headers: { host: "127.0.0.1:3000", ...headers } });
}

const basic = (user: string, password: string) => `Basic ${Buffer.from(`${user}:${password}`).toString("base64")}`;

test("POST /api/chat refuses bg in live mode with 422 unsupported_locale", async () => {
  const response = await chatPOST(jsonPost("/api/chat", { prompt: "Здравейте", model: "grok-4", locale: "bg" }));
  assert.equal(response.status, 422);
  const body = (await response.json()) as { code: string; locale: string; supported: string[] };
  assert.equal(body.code, "unsupported_locale");
  assert.equal(body.locale, "bg");
  assert.equal(body.supported.includes("bg"), false);
});

test("POST /api/preview refuses bg in live mode with 422", async () => {
  const response = await previewPOST(jsonPost("/api/preview", { prompt: "Здравейте", locale: "bg" }));
  assert.equal(response.status, 422);
  assert.equal(((await response.json()) as { code: string }).code, "unsupported_locale");
});

test("bg passes the locale guard once ANONREQ_GATEWAY_LOCALES lists it", async () => {
  env.ANONREQ_GATEWAY_LOCALES = "en,bg";
  const response = await chatPOST(jsonPost("/api/chat", { prompt: "Здравейте", model: "grok-4", locale: "bg" }));
  // Past the guard it tries the (unreachable) gateway, so anything but 422.
  assert.notEqual(response.status, 422);
});

test("mock mode accepts bg", async () => {
  env.ANONREQ_MOCK = "true";
  const response = await chatPOST(jsonPost("/api/chat", { prompt: "Молба от Иван Тестов Примеров", model: "bggpt", locale: "bg" }));
  assert.equal(response.status, 200);
});

test("middleware: every /api/audit/* route is 403 while ANONREQ_UI_ADMIN is off", async () => {
  assert.ok(AUDIT_ROUTES.length >= 4);
  for (const route of AUDIT_ROUTES) {
    const response = await middleware(auditGet(route, { authorization: basic("ops", "x") }));
    assert.equal(response.status, 403, route);
  }
});

test("middleware: every /api/audit/* route is 401 with a Basic challenge when the token is missing or wrong", async () => {
  env.ANONREQ_UI_ADMIN = "true";
  env.ANONREQ_UI_ADMIN_TOKEN = "s3cret";
  for (const route of AUDIT_ROUTES) {
    for (const headers of [{}, { authorization: basic("ops", "wrong") }]) {
      const response = await middleware(auditGet(route, headers));
      assert.equal(response.status, 401, route);
      assert.match(response.headers.get("www-authenticate") ?? "", /^Basic /);
    }
    const ok = await middleware(auditGet(route, { authorization: basic("ops", "s3cret") }));
    assert.equal(ok.status, 200, route);
    assert.equal(ok.headers.get("x-middleware-next"), "1", route);
  }
});

test("middleware: production without ANONREQ_UI_ADMIN_TOKEN fails closed (403)", async () => {
  env.ANONREQ_UI_ADMIN = "true";
  env.NODE_ENV = "production";
  for (const route of AUDIT_ROUTES) {
    const response = await middleware(auditGet(route));
    assert.equal(response.status, 403, route);
  }
});

test("middleware: non-audit API routes are not admin gated", async () => {
  const response = await middleware(new NextRequest(`${ORIGIN}/api/status`, { headers: { host: "127.0.0.1:3000" } }));
  assert.equal(response.status, 200);
});
