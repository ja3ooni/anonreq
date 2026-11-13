# AnonReq demo UI

Next.js console for the anonymization gateway. The playground shows four stages of one request (**01 Raw prompt** · **02 Anonymized prompt** · **03 Model reply before restore** · **04 Re-identified answer**), a multi-format file upload & readiness check (`.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.json`, `.log`, `.eml`), five Frankfurt EU buyer scenarios, and a GlassFlow Rius/Tares + Pilot PoC panel. The Audit page lists anonymization events, verifies the hash chain, and exports DPO CSVs. English (`/en`) and German (`/de`).

**This demo has no login.** The route handlers attach `ANONREQ_API_KEY` and `ANONREQ_ADMIN_API_KEY`. Anyone who can reach the process can export audit logs, see raw PII through the preview, and spend provider credits. It must not be exposed. A real login comes after the demo.

`npm run dev` and `npm run start` are `next dev` and `next start` with `-H 127.0.0.1`. That is the whole bind for a process on the host. To listen somewhere else you must opt in with `HOST=… npm run dev:host` or `start:host`, which prints a warning.

Docker is different. Inside the container the server listens on `0.0.0.0` (`HOSTNAME=0.0.0.0`) so the published port can reach it. Binding to `127.0.0.1` in the container would only hit the container's own loopback, and the host publish would connect to nothing. What keeps the dockerized app local is the compose publish `127.0.0.1:3000:3000`. **Never publish `0.0.0.0:3000`.** That would put the demo, and the keys its route handlers attach, on every interface of the machine.

API calls go through Next.js route handlers. The keys never reach the browser. The tenant is `ANONREQ_TENANT_ID` on the server. A tenant id sent by the browser is ignored.

## Run

```bash
cd web
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000. The middleware sends `/` to `/en`. `/de` is the German copy.

Offline demo, no gateway:

```bash
ANONREQ_MOCK=true npm run dev
```

`ANONREQ_MOCK=true` is the only way to serve fixtures. An empty `ANONREQ_GATEWAY_URL` does not turn mock mode on; the next live call fails and says the URL is missing. `NODE_ENV=production` refuses `ANONREQ_MOCK=true`. Set `ANONREQ_MOCK_PREVIEW=404` to show the middle-column placeholder.

Checks:

```bash
npm run typecheck
npm run lint
npm test
npm run build
```

There is no web CI on GitHub yet. A ready workflow (`.github/workflows/web.yml`: the same four
steps on Node 22) is prepared but **not included in this branch**: pushing workflow files needs a
token with the `workflow` scope, which the current one lacks. Until someone with that scope adds it,
run the four steps locally.

## Admin gate on `/api/audit/*`

- Every `/api/audit/*` route (`events`, `export`, `config-history`, `verify`, and any added later) is
  gated in `src/middleware.ts` (`src/lib/admin-gate.ts`):
  - **403** while `ANONREQ_UI_ADMIN` is off.
  - With `ANONREQ_UI_ADMIN_TOKEN` set, **HTTP Basic auth** is required (any user name, password =
    the token); otherwise **401** with a `WWW-Authenticate: Basic` challenge. Both sides are hashed
    with SHA-256 and the digests compared in constant time (Web Crypto, Edge-safe).
  - **Production fails closed:** with `NODE_ENV=production` (the Docker runtime image) the token is
    required; the flag alone gives 403.
- Both variables are read from `process.env` inside the request path, so a built or standalone server
  picks them up at start-up; they are never `NEXT_PUBLIC_` or build-time constants.
- The `/audit` page and the playground's "Export DPO Audit CSV" use these routes. `make demo`
  (`scripts/demo.sh`) fills in `ANONREQ_UI_ADMIN=true` and a generated token when missing (never
  overwriting an explicit `false` or an existing token); `docker-compose.mock.yml` sets the flag for
  the dev-stage mock. See `docs/DEMO_RUNBOOK.md` for the browser login.
- This is a shared-secret gate for the demo, not user accounts. The gateway still enforces
  `ANONREQ_ADMIN_API_KEY` upstream.

## Docker

Real gateway, production image (Next standalone output, no devDependencies):

```bash
cd web
ANONREQ_GATEWAY_URL=http://host.docker.internal:8080 \
ANONREQ_API_KEY=... ANONREQ_ADMIN_API_KEY=... \
docker compose up --build
```

Offline fixtures. The override builds the `dev` target (`NODE_ENV=development`, `next dev`), so production still refuses `ANONREQ_MOCK=true`:

```bash
cd web
docker compose -f docker-compose.yml -f docker-compose.mock.yml up --build
curl -I http://127.0.0.1:3000
```

Both publish `127.0.0.1:3000:3000` with the container listening on `0.0.0.0`.

## GlassFlow forwarding (`POST /api/glassflow`)

- Targets and credentials come from server env only (`GLASSFLOW_TARES_WEBHOOK_URL`, `GLASSFLOW_TARES_TOKEN`,
  `GLASSFLOW_RIUS_OTLP_ENDPOINT`, `GLASSFLOW_RIUS_API_KEY`). A body that names a target or credential
  (`taresUrl`, `taresToken`, `riusEndpoint`, `riusApiKey`, `url`, `token`) gets 400 and nothing is fetched.
  There are no defaults in code or compose; set them in `.env` (`scripts/connect-tares.sh` writes them).
- Targets must be `https`, except loopback / `host.docker.internal`. URLs with embedded credentials are ignored.
- Upstream fetches use `redirect: "manual"`: a 3xx counts as not delivered, and credentials never go to another origin.
- The response holds only delivered flags, HTTP statuses and the target **host**. It never contains the
  token, an ingest key, a URL path or any upstream body (no `/read` rows, health JSON or error detail).
  The ingest key from `/api/sources` is URL-encoded.
- The body is capped at 64 KB (413). It is then rebuilt server-side from an allowlist
  (`src/lib/glassflow-payload.ts`): fixed fields only, enums for decision / classification / event type /
  span name, patterns and a max length per field; unknown fields are dropped and an invalid value is a 400.
  The full sanitized context is not forwarded, only `sanitized_prompt_preview` (max 280 chars). That
  preview must contain a `[TYPE_N]` token and match no PII pattern (email, IBAN, phone, EGN / tax ID / card
  or other long digit runs, API keys); otherwise it is replaced by `[redacted: …]`. File names that look
  personal are redacted the same way. `raw_pii_leaked` is computed from that check (true = the "sanitized"
  text still matched a PII pattern and was redacted before sending); it is never hard-coded.
- Delivery: an explicit `/ingest/<key>` URL, or `/api/sources` → `/ingest/<key>` plus `/remember`. The token
  is only sent as a header; it is never put into a URL path.
- Env names: only the four `GLASSFLOW_*` names above are read. The legacy aliases `GLASSFLOW_API` and
  `glassflow_API` were removed; rename them to `GLASSFLOW_TARES_TOKEN`. `GLASSFLOW_RIUS_API_KEY` falls back to
  `GLASSFLOW_TARES_TOKEN` when unset.
- The route has no auth beyond the loopback Host/Origin guard below, so keep the UI on 127.0.0.1.

## Request guard on /api/*

The middleware rejects with 403 and a JSON `error`:

- a `Host` header not in the allowlist (blocks DNS rebinding). Default: `localhost:$PORT` and `127.0.0.1:$PORT` (`PORT` defaults to 3000). Override with a comma-separated `ANONREQ_ALLOWED_HOSTS`, e.g. `ANONREQ_ALLOWED_HOSTS=localhost:4000,127.0.0.1:4000`.
  **Docker port remaps:** the default is built from the container `PORT`, not the host port. If you publish `127.0.0.1:3001:3000`, the browser sends `Host: 127.0.0.1:3001` and every `/api/*` call gets 403. Set `ANONREQ_ALLOWED_HOSTS=localhost:3001,127.0.0.1:3001` to match the host side.
- `Sec-Fetch-Site` other than `same-origin` or `none`.
- an `Origin` whose host does not match `Host`, on any method.
- `POST`, `PUT`, `PATCH` or `DELETE` without an `Origin`.

So `curl -X POST` against `/api/*` needs `-H "Origin: http://localhost:3000"`.

## Point the gateway at xAI Grok

The playground calls `POST /v1/chat/completions` on the gateway (OpenAI-compatible). The gateway’s `ProviderStage` posts to `{PROVIDER_BASE_URL}/v1/chat/completions`.

xAI’s public base is `https://api.x.ai/v1`. Because the gateway appends `/v1/chat/completions`, set:

```bash
PROVIDER_BASE_URL=https://api.x.ai
PROVIDER_API_KEY=<xAI key>
```

`PROVIDER_BASE_URL=https://api.x.ai/v1` would call `https://api.x.ai/v1/v1/chat/completions`.

Non-streaming chat resolves `model` through `config/model_aliases.yaml` and rewrites it to the alias’s upstream model id. Add an alias whose `model` is a Grok id, for example:

```yaml
model_aliases:
  grok:
    provider: openai
    model: grok-4
```

The UI sends the alias name (default `grok-4`). Chat completions use `Authorization: Bearer $ANONREQ_API_KEY`. Every admin route (`/v1/admin/*`, including events, export, and config history) and the preview use `Authorization: Bearer $ANONREQ_ADMIN_API_KEY`. The gateway key is rejected with 403 on those routes.

Every one of those calls also sends `X-AnonReq-Tenant-ID`. Set it with `ANONREQ_TENANT_ID` (seed tenant `default` in `config/tenants.yaml`). A `tenant_id` that is not that caller is HTTP 403.

## Preview

The masked column is `POST /v1/debug/anonymize-preview`. It does not call a provider. The gateway returns **404** unless `ANONREQ_DEBUG_PREVIEW_ENABLED=true` and the caller presents an admin credential (`ANONREQ_ADMIN_API_KEY`). This UI sends that key from the server.

The demo sends a prompt-only body: `{ "prompt": "..." }`. Then `anonymized_text` is set, and `anonymized_messages` and each entity’s `message_index` are null. Token offsets index `anonymized_text`. `start` / `end` are Unicode code points; `start_utf16` / `end_utf16` and `token_*_utf16` are UTF-16, which this UI uses for highlighting. The original text is the field `span`.

The completion is a separate `POST /v1/chat/completions`. Each call has its own `request_id`. The header strip shows `X-AnonReq-Request-ID` from the completion and the preview’s `request_id` beside it.

A 404 leaves a labeled placeholder in the middle column. The answer and the completion headers still render. HTTP 429, the per-admin preview limit, shows a retry message in English and German.

## Audit

The table calls `GET /v1/admin/anonymization-events` and expects `{ total, limit, next_cursor, items }`. `next_cursor` is the string `timestamp|id`, or null on the last page. The next page is `?cursor=<next_cursor>&limit=50&sort=timestamp:desc` or `timestamp:asc`. There is no offset. Tenant is the caller (`X-AnonReq-Tenant-ID`, from `ANONREQ_DEFAULT_TENANT`). A `tenant_id` that is not that caller is HTTP 403, and the table shows an error instead of rows. **Load more** appends the next cursor.

CSV is `GET /v1/admin/anonymization-events/export` (no `.csv` suffix). The `entity_types` cell is a JSON array. A trailer row with `request_id=#error` and `decision=export_failed` means the stream failed partway: the file drops that row and the page warns that the download may be incomplete.

If that route is missing (404), the UI falls back to `GET /v1/admin/audit/anonymization-export`. That dump has no cursor and no separate total. Chain verify (`GET /v1/governance/audit/verify`) stays on the gateway key.

`GET /v1/admin/audit/config-history` is keyset-paginated the same way: `{ total, limit, next_cursor, items }`, `?cursor=&limit=100` (max 1000), newest first, `next_cursor` null at the end. The panel uses **Load more** and builds a CSV in the browser from the rows it has loaded.

## Depends on the gateway PR

The preview route and the cursor events API are added in [PR #5](https://github.com/ja3ooni/anonreq/pull/5) (`cursor/demo-admin-endpoints-5306`), which is not merged. This UI is based on `main`. Until that PR lands, run with `ANONREQ_MOCK=true`, or expect 404s and the fallbacks above. The full three-column view and the cursor audit log need PR #5, `ANONREQ_DEBUG_PREVIEW_ENABLED=true`, and `ANONREQ_ADMIN_API_KEY`.

## With the #20 demo stack

```bash
make demo   # repo root: gateway, Presidio, Valkey; writes ../.env
cd web
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.demo.yml up -d --build
```

`--env-file` is only used for compose variable substitution. The UI container receives just `ANONREQ_API_KEY`, `ANONREQ_ADMIN_API_KEY`, the tenant and the gateway URL (`http://anonreq-gateway:8080` on `anonreq_anonreq-net`), never the provider or KMS secrets. It is published on `127.0.0.1:3000`.
