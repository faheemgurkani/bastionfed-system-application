# BastionFed Unified Backend

This directory is now the **default unified FastAPI backend entrypoint** for BastionFed.

The implementation here is promoted from the unified Hunain-based backend and is now the general backend source of truth for running the application on a single port.

## What stays intact

The contributor-specific backend directories are still present and still runnable independently:

- `backend/faheem_implementation/`
- `backend/hunain_implementation/`
- `backend/hammad_implementation/`

Use this top-level `backend/` directory when you want the single unified backend for the full application.

## Run the unified backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
.venv/bin/python dev_server.py
```

This is the recommended development command. It enables reload, but only watches `backend/app` and `backend/tests`, which prevents `.venv` from triggering endless reloads.

If you want to run Uvicorn manually with reload, use:

```bash
cd backend
uvicorn app.main:app --reload --reload-dir app --reload-dir tests --host 0.0.0.0 --port 8000
```

If you do not need reload, use:

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API serves at `http://localhost:8000`.

Set the frontend to use it with:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Environment variables

The unified backend loads environment variables from `backend/.env`.

Relevant BastionBot settings:

```env
GROQ_API_KEY=...
GROQ_MODEL=llama-3.1-8b-instant
BASTIONBOT_DB_PATH=data/runtime/bastionbot.sqlite3
```

(`data/` here means **`backend/data/`** when the process cwd is `backend/` — see **`DATA_DIRECTORY.md`**.)

Optional **data plane** (see `docs/FIREBASE_DATA_PLANE_MAPPING.md`): when set, the unified backend uses normalized Supabase Postgres tables for tenant-scoped product data + BastionBot, Upstash Redis for SSE pub/sub, and Supabase Storage for malware uploads.

```env
DATABASE_URL=postgresql://...          # or SUPABASE_DATABASE_URL
REDIS_URL=rediss://...                 # or UPSTASH_REDIS_URL
SUPABASE_URL=https://....supabase.co   # or SUPABASE_PROJECT_URL
SUPABASE_SERVICE_KEY=...
```

If `DATABASE_URL` / `SUPABASE_DATABASE_URL` is **unset**, behavior matches the previous demo: in-memory product state + SQLite BastionBot. Tests force this mode via `tests/conftest.py`.

The historical `app/db/persistence.py` / `bf_bundle` snapshot path is now **legacy only** and is not used by the unified runtime.

### Client provisioning limits and per-client data ingest

- Each **admin** Firebase user may provision at most **5** FL clients per tenant (person + device combined). Override with `MAX_CLIENTS_PER_ADMIN` in `.env`.
- `GET /api/onboarding/limits` returns remaining capacity for the signed-in admin.
- Drop JSON / dataset files under **`backend/data/batch_ingest/client_1`**, `client_2`, … (mapped to DEVICE-type `fl_clients` in `id` order) and run:

```bash
python scripts/ingest_client_data.py --tenant-slug YOUR_SLUG
# or --tenant-id TENANT_UUID
```

See **`DATA_DIRECTORY.md`** for the local `backend/data/` tree, 25% sampling summary, and payload pointers (`scripts/ingest_client_data.py` has the full rules). SQL migrations under `app/db/migrations/` apply automatically on startup when Postgres is configured.

## Vercel (experimental serverless)

Deploy this API as a **second Vercel project** (separate from the Next.js frontend) with **Root Directory** `backend` and framework **FastAPI** (or leave auto-detect).

- **ASGI entry:** root [`main.py`](./main.py) imports `app` from [`app/main.py`](./app/main.py), which matches the [Python runtime](https://vercel.com/docs/functions/runtimes/python) / [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi) layout.
- **Deploy bundle:** [`.vercelignore`](./.vercelignore) drops `hunain_implementation/` from the upload. That tree used to hold **symlinks** into `backend/data/` (not in git); Vercel would warn or fail when resolving those paths. The unified runtime uses `app/` and Supabase for weights.
- **Function limits:** Set **max duration** (and memory if needed) under Vercel **Project → Settings → Functions**. Do **not** use `vercel.json` → `functions` with a `"main.py"` key: Vercel only matches those patterns against **`api/`**, which breaks this repo’s root [`main.py`](./main.py) FastAPI entry. Shrink uploads with [`.vercelignore`](./.vercelignore); keep [`vercel.json`](./vercel.json) minimal (e.g. `$schema` only) unless you add unrelated config.
- **Python line:** [`.python-version`](./.python-version) pins the interpreter series for the build (change it if you standardize on 3.11 locally).
- **Environment:** Vercel does not use `backend/.env` on disk. Add the same keys from the [Environment variables](#environment-variables) section in the Vercel UI (or `vercel env`). `load_dotenv` in `app/config.py` is a no-op when the file is absent; process env still applies.
- **CORS:** set **`ALLOWED_ORIGINS`** to a comma-separated list including every browser origin that will call this API (for example `https://<your-frontend>.vercel.app`). The default in `app/config.py` is localhost only.
- **ML / size:** `requirements.txt` pulls in **PyTorch** and related stacks used by FL inference. Many projects exceed Vercel’s uncompressed [function size limits](https://vercel.com/docs/functions/limitations) or hit impractical cold starts. If the deploy or import step fails, plan on a **container** host (e.g. Cloud Run, Railway, Render) for this backend instead.

## Tests

Run the unified backend test suite from `backend/`:

```bash
cd backend
.venv/bin/python -m pytest -q
```

Run the live HTTP BastionBot integration test:

```bash
cd backend
export LIVE_SERVER_URL=http://127.0.0.1:8000
.venv/bin/python -m pytest tests/test_live_server.py -q
```

## Notes

- BastionBot remains signed-in only
- the unified backend includes the BastionBot Groq integration, SQLite (demo) or Postgres (when configured) BastionBot persistence, and all unified API routes
- the unified `/api/events` alert stream uses tenant-scoped Redis pub/sub when `REDIS_URL` is set; otherwise it falls back to tenant-scoped in-memory behavior in test/demo mode
- Firebase token verification requires `PyJWT[crypto]` in the runtime `.venv` or container, not only in `requirements.txt`
- top-level `backend/app` is the general unified backend codebase going forward
- the implementation folders remain available for independent contributor testing and historical isolation
