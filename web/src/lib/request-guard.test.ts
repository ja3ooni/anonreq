import assert from "node:assert/strict";
import test from "node:test";

import { checkApiRequest, resolveAllowedHosts } from "./request-guard.ts";

const allowed = resolveAllowedHosts(undefined, undefined);
const base = { method: "GET", host: "localhost:3000", origin: null, secFetchSite: null, allowedHosts: allowed };

test("default allowlist is localhost and 127.0.0.1 on the port", () => {
  assert.deepEqual([...allowed], ["localhost:3000", "127.0.0.1:3000"]);
  assert.deepEqual([...resolveAllowedHosts("", "4000")], ["localhost:4000", "127.0.0.1:4000"]);
  assert.deepEqual([...resolveAllowedHosts(" Demo.local:3000 , x:1 ", "3000")], ["demo.local:3000", "x:1"]);
});

test("allowed host and same-origin requests pass", () => {
  assert.equal(checkApiRequest(base).ok, true);
  assert.equal(checkApiRequest({ ...base, host: "127.0.0.1:3000", secFetchSite: "same-origin" }).ok, true);
  assert.equal(
    checkApiRequest({ ...base, method: "POST", origin: "http://localhost:3000", secFetchSite: "same-origin" }).ok,
    true,
  );
});

test("unknown or missing Host is rejected (DNS rebinding)", () => {
  for (const host of ["evil.example:3000", "localhost:3001", "", null]) {
    const r = checkApiRequest({ ...base, host });
    assert.equal(r.ok, false);
    if (!r.ok) {
      assert.equal(r.status, 403);
      assert.match(r.message, /Host/);
    }
  }
});

test("cross-site and same-site fetches are rejected", () => {
  for (const site of ["cross-site", "same-site"]) {
    const r = checkApiRequest({ ...base, secFetchSite: site });
    assert.equal(r.ok, false);
  }
  assert.equal(checkApiRequest({ ...base, secFetchSite: "none" }).ok, true);
});

test("mismatched Origin is rejected on any method", () => {
  assert.equal(checkApiRequest({ ...base, origin: "http://evil.example" }).ok, false);
  assert.equal(checkApiRequest({ ...base, method: "POST", origin: "http://127.0.0.1:3000" }).ok, false);
  assert.equal(checkApiRequest({ ...base, method: "POST", origin: "not a url" }).ok, false);
});

test("state-changing methods require an Origin", () => {
  for (const method of ["POST", "PUT", "PATCH", "DELETE"]) {
    const r = checkApiRequest({ ...base, method });
    assert.equal(r.ok, false);
    if (!r.ok) assert.match(r.message, /Origin/);
  }
  assert.equal(checkApiRequest({ ...base, method: "POST", origin: "null" }).ok, false);
  assert.equal(checkApiRequest({ ...base, method: "HEAD" }).ok, true);
});
