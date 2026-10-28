# AnonReq xAI demo runbook (Friday Oct 30, 2026)

For Abdullah, running alone on a **Mac mini M4 (16 GB)** or a **Windows PC (Ryzen 5, 40 GB, WSL2)**.
No GPU is needed.

Tags used below:
- **[verified]**: the command or behaviour was run and checked on the DevOps box on 2026-10-28, against this branch merged with main 8f8e215.
- **[not yet verified]**: this has not been run end to end. The box can't build the app image (its Debian mirror is blocked) and has no bridge networking, so `make demo` there was only partly attempted.

---

## 1. Prerequisites

| | Mac mini M4 | Windows PC |
|---|---|---|
| Docker Compose | **>= 2.24** (`docker compose version`; the demo overlay uses `ports: !override`). Current Docker Desktop ships newer. | same |
| Docker | Docker Desktop, **Memory ≥ 6 GB** (8 GB is fine). Settings › General: enable *"Use Rosetta for x86_64/amd64 emulation on Apple Silicon"*. | Docker Desktop with the **WSL 2 backend**. Settings › Resources › WSL integration: enable for *Ubuntu*. |
| Disk | ≥ 25 GB free: the Presidio image alone is ~9.65 GB, plus the app image, build cache, and headroom. | Same, on the WSL disk. |
| Tools | `git`, `make`, `python3`. `xcode-select --install` provides `make`. | Inside Ubuntu (WSL): `sudo apt update && sudo apt install -y make git python3 curl` |
| xAI key | An `XAI_API_KEY` with access to `grok-4` | same |

**Apple Silicon note:** the Presidio base image `mcr.microsoft.com/presidio-analyzer:2.2.354` is published for **linux/amd64 only**. I checked this with `docker buildx imagetools inspect` [verified]. The demo overlay therefore pins `platform: linux/amd64` on `presidio-analyzer`, and on the M4 it runs under Rosetta. Expect:
- a slower first build and a slower first start (model load) than on x86;
- detection results identical to x86.

Every other image in the stack is multi-arch (amd64 + arm64) [verified]: python:3.12-slim (app), valkey 8.0, postgres:16-alpine, postgres-exporter, prometheus, grafana, redis_exporter, and node:22-bookworm-slim (frontend). The spaCy model wheels are `py3-none-any`, so they install on any CPU architecture.

**Windows only, once:**
```bash
# in the Ubuntu (WSL) shell — clone INSIDE the Linux filesystem, not /mnt/c
git config --global core.autocrlf input
mkdir -p ~/Develop && cd ~/Develop
git clone https://github.com/ja3ooni/anonreq.git annon && cd annon
```
The repo's `.gitattributes` forces LF line endings on `*.sh`, `Makefile`, `*.yml`, `*.yaml`, `Dockerfile` and `*.py`. A CRLF line ending breaks `scripts/demo.sh`.

If WSL is short on memory, create `C:\Users\<you>\.wslconfig` containing the lines below, then run `wsl --shutdown` in PowerShell and reopen Ubuntu:
```
[wsl2]
memory=12GB
```

**Mac:** `cd` into your existing clone (shown as `<repo-dir>`).
```bash
cd <repo-dir> && git pull
```

## 2. `.env` setup

`make demo` creates `.env` itself. It is gitignored and `chmod 600`. The script generates every missing secret (gateway key, admin key, KMS master key, signing key, DB and MinIO passwords) and sets `ANONREQ_ADMIN_TENANT_ID=default`. MinIO and Postgres get random credentials; `<...>` placeholders and `minioadmin` are replaced, never used and `ANONREQ_DEMO_MODEL=grok-4`. The only thing you supply is the xAI key:

```bash
export XAI_API_KEY='<your-xai-api-key>'     # or put XAI_API_KEY=<...> in .env
```
To choose your own admin key instead of the generated one, add these lines to `.env` before the first run (placeholders shown):
```
ANONREQ_ADMIN_API_KEY=<long-random-admin-key>
ANONREQ_ADMIN_TENANT_ID=default
```
Later steps need the keys in your shell:
```bash
set -a; . ./.env; set +a
```

## 3. One-command start  [not yet verified end to end]

```bash
make demo
```
1. Checks Docker memory (>= 4 GB), builds the app + German Presidio images, `docker compose up -d --wait` (gateway, Presidio, Valkey), warms Presidio. The gateway runs `alembic upgrade head` before uvicorn (fresh volume otherwise 500s on every chat).
2. **Then starts the UI** (`web/docker-compose.demo.yml`, PR #12) once the gateway is healthy, on the shared network `anonreq_anonreq-net`, talking to `anonreq-gateway:8080`. If that file is missing (#12 not merged) it prints `NOTE: ... skipping the UI` and you get the API only.
3. Prints `Demo UI ready: http://localhost:3000`.

Everything is published on **127.0.0.1 only**: UI 3000, gateway 8080 (Grafana 3001 / Prometheus 9090 only with the observability profile). Nothing is reachable from the LAN.

**Port 3000 must be free before `make demo`** (see Troubleshooting: "port 3000 in use").

## 4. Health check

```bash
docker compose -f docker-compose.yml -f docker-compose.germany.yml -f docker-compose.demo.yml ps   # all "healthy"
curl -s -o /dev/null -w "%{http_code}\n" localhost:8080/health -H "Authorization: Bearer $ANONREQ_API_KEY"   # 200
```

## 5. Demo: API click-through  [verified on box, gateway outside Docker]

```bash
curl -s localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer $ANONREQ_API_KEY" -H 'X-AnonReq-Tenant-ID: default' \
  -H 'X-AnonReq-Locale: de-DE' -H 'Content-Type: application/json' \
  -d '{"model":"grok-4","messages":[{"role":"user","content":"Bitte bestätige Hans Müller, Hauptstraße 12, 60311 Frankfurt, IBAN DE89370400440532013000, Tel. +49 69 12345678."}]}'
```
Expected: **200**, with headers `x-anonreq-entity-count: 5` and `x-anonreq-processed: true`. The answer contains the real name, address, IBAN and phone, restored by the gateway. xAI only received `[PERSON_NAME_DE_…]`, `[IBAN_DE_…]` and similar tokens.

| Check | Command | Expect |
|---|---|---|
| Anonymized preview (what xAI receives) | `curl -s localhost:8080/v1/debug/anonymize-preview -H "Authorization: Bearer $ANONREQ_ADMIN_API_KEY" -H 'X-AnonReq-Locale: de-DE' -H 'Content-Type: application/json' -d '{"model":"grok-4","messages":[{"role":"user","content":"Hans Müller, Hauptstraße 12"}]}'` | 200 + tokens |
| Audit log (admin) | `curl -s localhost:8080/v1/admin/anonymization-events -H "Authorization: Bearer $ANONREQ_ADMIN_API_KEY"` | **200**, one row per request (types and counts only) |
| Audit log (gateway key) | same, with `$ANONREQ_API_KEY` + `-H 'X-AnonReq-Tenant-ID: default'` | **403** |
| Audit log (no key) | same, with no Authorization header + tenant header | **401** |
| CSV export | `curl -s -D - localhost:8080/v1/admin/anonymization-events/export -H "Authorization: Bearer $ANONREQ_ADMIN_API_KEY"` | **200**, `text/csv`, no raw PII |

## 6. Demo: three-column UI (raw / anonymized / restored)

Demo URL: **<http://localhost:3000>** (started by `make demo` when PR #12's `web/` is present).
Container start via compose: [not yet verified]. Same UI run with `next dev` against the gateway: [verified] (chat 200 restored, preview 200, audit 200, CSV 200).

Click-through:
1. Open <http://localhost:3000/de>. Model `grok-4`, detection locale *Deutsch (de-DE)*.
2. Paste: `Bitte bestätige Hans Müller, Hauptstraße 12, 60311 Frankfurt, IBAN DE89370400440532013000, Tel. +49 69 12345678.`
3. Send. Columns: **raw** (your text) · **anonymized** (`[PERSON_NAME_DE_…]`, `[STREET_ADDRESS_DE_…]`, `[POSTCODE_CITY_DE_…]`, `[IBAN_DE_…]`, phone token = what xAI saw) · **restored** (Grok's answer with real values back).
4. **Audit** tab: new row, `de-DE`, token count 5, entity types.
5. **Export CSV**: downloads the row; no names/IBANs/phones in it.

Fallback without Docker for the UI (from `web/`):
```bash
npm ci && ANONREQ_GATEWAY_URL=http://127.0.0.1:8080 ANONREQ_API_KEY=$ANONREQ_API_KEY \
ANONREQ_ADMIN_API_KEY=$ANONREQ_ADMIN_API_KEY ANONREQ_TENANT_ID=default npx next dev -H 127.0.0.1 --port 3100
```
then use <http://127.0.0.1:3100/de>.

## 7. Stop / reset

```bash
make demo-down                     # stop UI + gateway stack, keep data
make demo-down && docker compose -f docker-compose.yml -f docker-compose.germany.yml -f docker-compose.demo.yml down -v   # also wipe volumes (audit DB, Valkey)
```
`down -v` deletes the audit history. After it, the next `make demo` re-creates the tables.

## 8. Troubleshooting

- **Port 3000 in use** (UI fails to start, "port is already allocated"): `lsof -i :3000` (Windows/WSL: `sudo ss -ltnp | grep :3000`, or in PowerShell `netstat -ano | findstr :3000`) to find the owner, stop it, `make demo` again. Same for 8080 (gateway). Last resort: run the UI with the `next dev --port 3100` fallback in section 6.
- **UI shows gateway errors / "network anonreq_anonreq-net not found"**: the gateway stack is not up; run `make demo` (not the web compose alone). The network name is fixed in `docker-compose.demo.yml`, independent of the clone folder name.
- **Slow first Presidio start**: the two large spaCy models load on the first request. The compose start window is 120 s, and on the M4 under Rosetta it is slower. `make demo` warms Presidio before printing `Demo UI ready: http://localhost:3000` (or only `Gateway API: ...` when the UI is skipped). If chats are slow at first, wait and retry. Watch progress with `docker compose ... logs -f presidio-analyzer`.
- **"Docker has N MiB RAM"**: raise Docker Desktop memory to 6 GB or more. On Windows, also raise `.wslconfig`.
- **401 vs 403 vs 400**:
  - 401 means no key or an unknown key.
  - 403 means a valid key without the right role, e.g. the gateway key on admin routes, or a tenant mismatch.
  - 400 `missing_tenant` means the gateway key was sent without `X-AnonReq-Tenant-ID: default`. Only the admin key may omit it (single-tenant mode).
- **Gateway unhealthy, logs show `sqlite3.OperationalError: unable to open database file`**: `.env` (copied from an old `.env.example`) sets `ANONREQ_DATABASE_URL=sqlite+aiosqlite:///./anonreq.db`, a relative path outside the `anonreq_data` volume. Fixed three ways: the demo overlay pins `sqlite+aiosqlite:////app/data/anonreq.db`, `make demo` comments out any other sqlite URL in `.env` (prints a `NOTE:`), and the image creates `/app/data` owned by the app user so a fresh volume is writable. If you still see it: `grep DATABASE_URL .env` (remove/comment the line), then `make demo-down && docker volume rm anonreq_anonreq_data && make demo` (this deletes the audit history). Verify: `docker compose -f docker-compose.yml -f docker-compose.germany.yml -f docker-compose.demo.yml config | grep DATABASE_URL` shows `/app/data/anonreq.db`.
- **Startup fails with `Provider API key missing for: anthropic, gemini`**: the gateway loaded the base `config/model_aliases.yaml` (which also routes to Anthropic and Gemini) instead of the demo file. The demo overlay now sets `ANONREQ_MODEL_ALIASES_PATH=config/model_aliases.demo.yaml` (only `grok-4` via the xAI key; file is baked into the image), so only `XAI_API_KEY` is needed and no Anthropic/Gemini placeholder keys. Check: `docker compose -f docker-compose.yml -f docker-compose.germany.yml -f docker-compose.demo.yml config | grep MODEL_ALIASES_PATH`. If it is missing you are on an old checkout or not using `make demo`; `git pull`, then `make demo` (it rebuilds the image).
- **`/app/data` missing or no volume on the gateway**: check with `docker inspect anonreq-gateway --format '{{json .Mounts}}'`; it must list volume `anonreq_anonreq_data` at `/app/data`. If not, the container was not started by `make demo` (or by an old image): `make demo-down && make demo`. The image creates `/app/data` owned by the app user (uid 1001), so a new volume is writable.
- **Chat returns 500 on a fresh install**: the migrations didn't run. Check `docker compose ... logs anonreq | grep alembic`.
- **`$'\r': command not found` (Windows)**: the clone was checked out with CRLF line endings. Re-clone inside WSL after `git config --global core.autocrlf input`.
- **`XAI_API_KEY not set`**: export it, or add it to `.env`, and re-run.
