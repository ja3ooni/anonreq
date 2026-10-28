# AnonReq demo UI

Next.js console for the anonymization gateway. One screen shows the raw prompt, the masked prompt, and the re-identified answer. Another lists anonymization events and exports CSV. English and German.

API calls go through Next.js route handlers. `ANONREQ_API_KEY` and `ANONREQ_ADMIN_API_KEY` never reach the browser.

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

`ANONREQ_MOCK=true` serves fixtures. Set `ANONREQ_MOCK_PREVIEW=404` to show the middle-column placeholder.

Checks:

```bash
npm run typecheck
npm run lint
npm test
```

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

The UI sends the alias name (default `grok`). Chat completions use `Authorization: Bearer $ANONREQ_API_KEY`. Every admin route (`/v1/admin/*`, including events, export, and config history) and the preview use `Authorization: Bearer $ANONREQ_ADMIN_API_KEY`. The gateway key is rejected with 403 on those routes.

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
