import assert from "node:assert/strict";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { after, before, beforeEach, test } from "node:test";

import { CLIENT_TARGET_FIELDS, resolveGlassFlowConfig, safeEnvUrl, targetHost } from "./glassflow-config.ts";
import { forwardToGlassFlow } from "./glassflow-forward.ts";

const TOKEN = "SECRET-TOK-123";
const INGEST_KEY = "ingest/key?with=chars&x";

interface Hit {
  method: string;
  url: string;
  headers: Record<string, string | string[] | undefined>;
}

let hits: Hit[] = [];
let otherHits: Hit[] = [];
let mode: "ok" | "redirect" | "error-body" = "ok";
let cell: Server;
let other: Server;
let cellUrl = "";
let otherUrl = "";

function listen(server: Server): Promise<string> {
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(`http://127.0.0.1:${(server.address() as AddressInfo).port}`)));
}

before(async () => {
  other = createServer((req, res) => {
    otherHits.push({ method: req.method ?? "", url: req.url ?? "", headers: req.headers });
    req.resume();
    res.writeHead(200, { "content-type": "application/json" });
    res.end("{}");
  });
  otherUrl = await listen(other);
  cell = createServer((req, res) => {
    hits.push({ method: req.method ?? "", url: req.url ?? "", headers: req.headers });
    req.resume();
    req.on("end", () => {
      if (mode === "redirect") {
        res.writeHead(307, { location: `${otherUrl}/stolen` });
        return res.end();
      }
      if (mode === "error-body") {
        res.writeHead(500, { "content-type": "application/json" });
        return res.end(JSON.stringify({ detail: `internal: token ${TOKEN} rejected`, rows: ["raw-row"] }));
      }
      res.setHeader("content-type", "application/json");
      if (req.url === "/api/sources") return res.end(JSON.stringify({ ingest_key: INGEST_KEY }));
      if (req.url === "/health") return res.end(JSON.stringify({ version: "v1.54.1", secret: TOKEN }));
      if (req.url === "/read") return res.end(JSON.stringify({ rows: [{ correlation_key: "k", raw: "row" }] }));
      return res.end(JSON.stringify({ ok: true, echo: TOKEN }));
    });
  });
  cellUrl = await listen(cell);
});

after(() => {
  cell.close();
  other.close();
});

beforeEach(() => {
  hits = [];
  otherHits = [];
  mode = "ok";
});

const bundle = { rius: { resourceSpans: [] }, tares: { correlation_key: "k1", decision: "ALLOW", data: {} } };
const base = () => resolveGlassFlowConfig({ GLASSFLOW_TARES_WEBHOOK_URL: cellUrl, GLASSFLOW_TARES_TOKEN: TOKEN });
const ingestCfg = () => resolveGlassFlowConfig({ GLASSFLOW_TARES_WEBHOOK_URL: `${cellUrl}/ingest/${encodeURIComponent("webhook-abc")}`, GLASSFLOW_TARES_TOKEN: TOKEN });

function assertNoSecrets(value: unknown, ...secrets: string[]) {
  const text = JSON.stringify(value);
  for (const secret of [TOKEN, INGEST_KEY, encodeURIComponent(INGEST_KEY), "webhook-abc", "/ingest/", ...secrets]) {
    assert.equal(text.includes(secret), false, `response leaks ${secret}: ${text}`);
  }
}

test("400: non-object body, array body, and every client target field; nothing is fetched", async () => {
  for (const body of [null, "x", 42, [], { tares: "nope" }]) {
    const result = await forwardToGlassFlow(body, base());
    assert.equal(result.status, 400, JSON.stringify(body));
  }
  for (const field of CLIENT_TARGET_FIELDS) {
    const result = await forwardToGlassFlow({ ...bundle, [field]: "http://169.254.169.254/" }, base());
    assert.equal(result.status, 400, field);
    assertNoSecrets(result.body);
  }
  assert.equal(hits.length, 0, "no upstream call for a refused body");
});

test("base URL path: delivers via /api/sources + URL-encoded ingest key; response has no token, key or URL path", async () => {
  const result = await forwardToGlassFlow(bundle, base());
  assert.equal(result.status, 200);
  const body = result.body as Record<string, unknown>;
  assert.equal(body.taresDelivered, true);
  assert.equal(body.riusDelivered, true);
  assert.equal(body.taresHost, new URL(cellUrl).host);
  assert.equal(body.taresHealthy, true);
  assert.equal("readResult" in body || "healthResult" in body || "resolvedIngestUrl" in body || "taresBase" in body, false);
  assertNoSecrets(body, "v1.54.1", "raw-row", "row");
  const ingest = hits.find((hit) => hit.url.startsWith("/ingest/"));
  assert.equal(ingest?.url, `/ingest/${encodeURIComponent(INGEST_KEY)}`);
  assert.equal(hits.some((hit) => hit.url === "/read"), false, "no /read passthrough");
});

test("explicit /ingest/<key> URL: delivered flag only, key never returned", async () => {
  const result = await forwardToGlassFlow(bundle, ingestCfg());
  assert.equal((result.body as { taresDelivered: boolean }).taresDelivered, true);
  assertNoSecrets(result.body);
});

test("upstream error bodies are not passed back (status only)", async () => {
  mode = "error-body";
  const result = await forwardToGlassFlow(bundle, base());
  assert.equal(result.status, 200);
  const body = result.body as Record<string, unknown>;
  assert.equal(body.taresDelivered, false);
  assert.equal(body.taresHealthStatus, 500);
  assertNoSecrets(body, "internal", "raw-row");
});

test("redirects are not followed: no request (and no key) reaches the redirect target", async () => {
  mode = "redirect";
  const result = await forwardToGlassFlow(bundle, base());
  const body = result.body as Record<string, unknown>;
  assert.equal(body.taresDelivered, false);
  assert.equal(body.riusDelivered, false);
  assert.equal(otherHits.length, 0, `followed a redirect: ${JSON.stringify(otherHits.map((hit) => hit.url))}`);
  assertNoSecrets(body);
});

test("https required except for local targets; host helper never returns a path", () => {
  assert.equal(safeEnvUrl("http://cell.example.com/ingest/k"), "");
  assert.equal(safeEnvUrl("https://cell.example.com/ingest/k"), "https://cell.example.com/ingest/k");
  for (const local of ["http://localhost:8080", "http://127.0.0.1:9", "http://host.docker.internal:7"]) {
    assert.notEqual(safeEnvUrl(local), "", local);
  }
  assert.equal(targetHost("https://cell.example.com:8443/ingest/secret"), "cell.example.com:8443");
  assert.equal(resolveGlassFlowConfig({ GLASSFLOW_TARES_WEBHOOK_URL: "http://cell.example.com/" }).taresWebhook, "");
});

test("route response carries no token or key in body or headers", async () => {
  // Mirrors app/api/glassflow/route.ts: JSON body + cache-control only.
  const result = await forwardToGlassFlow(bundle, base());
  const response = Response.json(result.body, { status: result.status, headers: { "cache-control": "no-store" } });
  const headerText = JSON.stringify([...response.headers.entries()]);
  assertNoSecrets(headerText);
  assertNoSecrets(await response.text());
});
