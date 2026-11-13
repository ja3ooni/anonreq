import assert from "node:assert/strict";
import test from "node:test";

import { resolveGlassFlowConfig, safeEnvUrl, taresBaseFrom } from "./glassflow-config.ts";

test("no env means no forwarding target (no hard-coded external default)", () => {
  const config = resolveGlassFlowConfig({});
  assert.equal(config.taresWebhook, "");
  assert.equal(config.riusEndpoint, "");
  assert.equal(config.taresToken, "");
});

test("targets come from env only and must be plain http(s) URLs", () => {
  const config = resolveGlassFlowConfig({
    GLASSFLOW_TARES_WEBHOOK_URL: "https://cell.example.com/ingest/abc/",
    GLASSFLOW_TARES_TOKEN: "t0k",
  });
  assert.equal(config.taresWebhook, "https://cell.example.com/ingest/abc");
  assert.equal(config.taresToken, "t0k");
  assert.equal(config.riusEndpoint, "https://cell.example.com/v1/traces");
  assert.equal(config.riusApiKey, "t0k");
  for (const bad of ["file:///etc/passwd", "gopher://x", "https://user:pw@cell.example.com/", "not a url", "  "]) {
    assert.equal(safeEnvUrl(bad), "", bad);
  }
});

test("tares base strips known suffixes", () => {
  assert.equal(taresBaseFrom("https://c.example.com/read"), "https://c.example.com");
  assert.equal(taresBaseFrom("https://c.example.com/ingest/key-1"), "https://c.example.com");
});

test("legacy token aliases (GLASSFLOW_API, glassflow_API) are not read", () => {
  const config = resolveGlassFlowConfig({ GLASSFLOW_TARES_WEBHOOK_URL: "https://cell.example.com", GLASSFLOW_API: "a", glassflow_API: "b" });
  assert.equal(config.taresToken, "");
  assert.equal(config.riusApiKey, "");
});
