import assert from "node:assert/strict";
import test from "node:test";

import { DemoPolicyError, resolveMockMode, resolveServerTenant } from "./runtime-policy.ts";

test("mock mode is off unless ANONREQ_MOCK is explicitly true", () => {
  assert.equal(resolveMockMode(undefined, "development"), false);
  assert.equal(resolveMockMode("", "development"), false);
  assert.equal(resolveMockMode("false", "development"), false);
  assert.equal(resolveMockMode("true", "development"), true);
  assert.equal(resolveMockMode("1", "test"), true);
});

test("mock mode is refused in production", () => {
  assert.throws(() => resolveMockMode("true", "production"), DemoPolicyError);
  assert.equal(resolveMockMode("false", "production"), false);
});

test("the server tenant ignores anything but ANONREQ_TENANT_ID", () => {
  assert.equal(resolveServerTenant("default"), "default");
  assert.throws(() => resolveServerTenant(undefined), DemoPolicyError);
  assert.throws(() => resolveServerTenant("  "), DemoPolicyError);
  assert.throws(() => resolveServerTenant("bad tenant"), DemoPolicyError);
});
