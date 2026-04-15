# BastionFed — Data plane debugging & verification

Companion to [`FIREBASE_DATA_PLANE_MAPPING.md`](./FIREBASE_DATA_PLANE_MAPPING.md). Use this file to record **how** each artifact was verified, **what** failed, and **fixes** applied.

For **claims vs production reality** (operational scope, drift honesty, reviewer checklists), see [`BLUE_TEAM_APPLICATION_SPEC.md`](./BLUE_TEAM_APPLICATION_SPEC.md).

---

## 0. Cross-document index

| Document | Role |
|----------|------|
| [`FIREBASE_DATA_PLANE_MAPPING.md`](./FIREBASE_DATA_PLANE_MAPPING.md) | What to provision (consoles, env vars, URI shapes). Includes **§ Implementation alignment** — how that maps to actual FastAPI code. |
| **This file** | Commands and findings to prove each artifact responds. |
| [`BLUE_TEAM_APPLICATION_SPEC.md`](./BLUE_TEAM_APPLICATION_SPEC.md) | Blue-team matrix: what UI/API *implies* vs what is *enforced* (for example: verified JWTs are implemented, while FL federation and enterprise controls remain narrower). |

### 0.1 Env → code (single source of truth)

| Artifact | Env vars (`backend/.env` unless noted) | Code |
|----------|--------------------------------------|------|
| Postgres | `DATABASE_URL` / `SUPABASE_DATABASE_URL` | `app/db/migrate.py`, `app/store/tenant_store.py`, `app/bastionbot/pg_store.py`, `app/config.py` |
| Storage | `SUPABASE_URL` / `SUPABASE_PROJECT_URL`, `SUPABASE_SERVICE_KEY` | `app/services/supabase_storage.py` (`httpx`) |
| Redis | `REDIS_URL` / `UPSTASH_REDIS_URL` | `app/sse_bus.py`, `app/routers/events.py` |
| Readiness / strict | `BASTIONFED_STRICT_DATA_PLANE`, `STORAGE_SIGNED_URL_EXPIRES_S` | `app/data_plane_probes.py`, `app/main.py` (`/health/ready`) |
| Signed forensics GET | (uses same Storage env) | `app/services/supabase_storage.py`, `app/routers/forensics.py` |
| Firebase | `NEXT_PUBLIC_FIREBASE_*` in **`frontend/.env.local`** only | `frontend/lib/firebase.ts`, `frontend/contexts/auth-context.tsx` |

### 0.2 Sections in this log

| Artifact | Doc section | Primary env file | Verified in this log |
|----------|-------------|------------------|----------------------|
| Firebase Auth + config | Mapping § summary, §1 Firestore intro | `frontend/.env.local` (`NEXT_PUBLIC_FIREBASE_*`) | §1 below |
| Cloud Firestore (`users/{uid}`) | Mapping §1 rules + frontend map | Same + Firebase Console rules | §1 below |
| Supabase PostgreSQL | Mapping §2 | `backend/.env` (`DATABASE_URL` / `SUPABASE_DATABASE_URL`) | §2 below |
| Supabase Storage | Mapping §3 | `backend/.env` (`SUPABASE_*`) | §3 below |
| Upstash Redis (SSE) | Mapping §4 | `backend/.env` (`REDIS_URL` / `UPSTASH_REDIS_URL`) | §4 below |

**Important:** The **FastAPI backend does not load `frontend/.env.local`**. Only `backend/.env` is read by `app/config.py`. Firebase/Firestore run in the **browser** via the Next.js client.

---

## 1. Firebase Auth + Firestore (mapping doc lines 1–103)

### Expected behavior (from mapping doc)

- **Firebase Auth**: Google sign-in (and guest mode) in the SPA; ID tokens sent to FastAPI as `Authorization: Bearer …`.
- **Firestore**: On successful sign-in, `auth-context.tsx` writes **`users/{uid}`** with `setDoc(..., { merge: true })`.
- **Rules**: Only `users/{userId}` read/write when `request.auth.uid == userId`; all other paths denied.

### Codebase checks (static)

| Check | Location | Result |
|-------|----------|--------|
| Firebase app + Auth + Firestore initialized | `frontend/lib/firebase.ts` | `initializeApp`, `getAuth`, `getFirestore` |
| Profile mirror on login | `frontend/contexts/auth-context.tsx` | `setDoc(doc(db, "users", user.uid), …)` |
| Firebase SDK dependency | `frontend/package.json` | `firebase` present |

### Environment checks (`frontend/.env.local`)

Automated script should confirm **all** `NEXT_PUBLIC_FIREBASE_*` keys from the mapping doc are **defined** (values not printed).

### Network checks (`curl`)

| Probe | Purpose |
|-------|---------|
| `HEAD` / `GET` `https://<authDomain>` | Hosting/auth domain resolves (default `*.firebaseapp.com`). |
| `GET` Firestore REST root `.../projects/<projectId>/databases/(default)/documents` **without** token | Expect **401/403**, not **404** — confirms project id / API surface. |

### Pytest note

**There is no Firestore client in the unified Python backend.** Backend `tests/conftest.py` does not (and should not) call Firebase. Firestore verification is **frontend + manual browser + curl probes**, not `pytest` in `backend/tests`.

### Manual verification (recommended)

1. Open the app, **Sign in with Google**.
2. Firebase Console → **Firestore** → confirm document under **`users/<uid>`**.
3. If writes fail, re-publish **Rules** from the mapping doc and confirm **Authorized domains** include your dev origin.

### Findings log

**Run:** 2026-04-01 (local machine).

| Step | Command / check | Result |
|------|-----------------|--------|
| Backend regression | `cd backend && .venv/bin/python -m pytest tests/ -q` | **56 passed, 1 skipped** (includes live Supabase + Redis when `.env` present; as of 2026-04-04) — does **not** exercise Firestore (by design). |
| `NEXT_PUBLIC_FIREBASE_*` keys | Python parse of `frontend/.env.local` (keys only) | **OK** — required keys present: `API_KEY`, `AUTH_DOMAIN`, `PROJECT_ID`, `STORAGE_BUCKET`, `MESSAGING_SENDER_ID`, `APP_ID`. `MEASUREMENT_ID` also present (Analytics). |
| Firestore API surface | `curl` `GET https://firestore.googleapis.com/v1/projects/bastionfed/databases/(default)/documents/users` (no bearer) | **HTTP 403** `PERMISSION_DENIED` — project/database path is valid; unauthenticated access correctly blocked. |
| Identity Toolkit (Auth) | `POST …/v1/accounts:createAuthUri?key=<from env>` minimal payload | **HTTP 200** — web API key accepted for this Firebase project (proves Auth API is live for the configured key). |
| Auth domain | `GET https://bastionfed.firebaseapp.com/` | **HTTP 404** — default Firebase Hosting page often absent until a deploy; **not** proof that Auth is broken (OAuth `continueUri` and SDK still use this domain). |

**Not automated here:** Browser sign-in + Firestore write to `users/{uid}` + Console rules — still the definitive check for rules and `setDoc` behavior.

---

## 2. Supabase PostgreSQL (mapping doc §2, lines 105–143)

### Expected behavior

- **`SUPABASE_DATABASE_URL` or `DATABASE_URL`** in `backend/.env` — `app/config.py` loads either.
- **Transaction pooler:** `prepare_threshold=None` on `psycopg.connect` in the tenant store, migration runner, and BastionBot PG store.
- **Regional pooler:** If the dashboard gives `aws-<n>-<region>.pooler.supabase.com:6543` with user `postgres.<ref>`, the **region in the hostname must match the project** (wrong region → `FATAL: Tenant or user not found`). See updated table in [`FIREBASE_DATA_PLANE_MAPPING.md`](./FIREBASE_DATA_PLANE_MAPPING.md).

### Postgres schema objects (artifacts)

| Object | Purpose |
|--------|---------|
| `public.tenants`, `users`, `memberships`, `alerts`, `devices`, `incidents`, `incident_events`, `fl_*`, `model_registry`, `malware_samples`, `audit_log`, `ingest_*` | Tenant-scoped normalized application state. |
| `public.bot_conversations`, `bot_messages`, `bot_user_memory` | BastionBot when live Postgres is used. |

Created by `run_migrations()` in `app/db/migrate.py` (run at bootstrap when DB connects).

### Automated tests (live)

| File | Behavior |
|------|----------|
| `backend/tests/test_supabase_live.py` → `test_supabase_postgres_ping` | Skips if no DB URL in `.env`; else `SELECT 1` with `prepare_threshold=None`. |
| `test_supabase_persistence_tables_exist` | After `run_migrations()`, asserts normalized domain tables and `bot_conversations` exist (`to_regclass`). |
| `test_supabase_storage_signed_url` | Upload probe object → `create_signed_download_url` → assert HTTPS URL. |

```bash
cd backend && .venv/bin/python -m pytest tests/test_supabase_live.py -v
```

### Manual / one-shot checks

```bash
cd backend && .venv/bin/python -c "from app.db.migrate import run_migrations; run_migrations()"
```

### Findings log

**Run:** 2026-04-01.

| Step | Result |
|------|--------|
| Initial `SUPABASE_DATABASE_URL` | **`FATAL: Tenant or user not found`** — hostname used **`aws-0-us-east-1`…** while this project’s working pooler is **`aws-1-ap-south-1`…`** (transaction pooler, port 6543, user `postgres.<ref>`). |
| Fix | Set `SUPABASE_DATABASE_URL` to the **Connect** string for **this** project/region (see `.env` comment). |
| After fix | **`run_migrations()`** OK; **`SELECT 1`** OK. |
| Pytest | **`test_supabase_live.py`** (ping + schema tables) passes with corrected URL. |
| `/health` (Uvicorn) | **`"persistence":"postgres"`** (no longer `configured_unavailable_fallback`). |

---

## 3. Supabase Storage (mapping doc §3, lines 145–169)

### Expected behavior

- **`SUPABASE_PROJECT_URL` or `SUPABASE_URL`** + **`SUPABASE_SERVICE_KEY`** (service role) in `backend/.env`.
- Buckets **`forensics`** and **`models`** (private); uploads via **`httpx`** to Storage REST in `app/services/supabase_storage.py` (not `supabase-py`).

### Automated tests (live)

| File | Behavior |
|------|----------|
| `test_supabase_storage_buckets` | Lists `GET …/storage/v1/bucket`; asserts `forensics` and `models` exist. |

### Manual probe

Upload helper (creates an object in `forensics/`):

```bash
cd backend && .venv/bin/python -c "from app.services import supabase_storage; print(supabase_storage.upload_forensics_bytes(data=b'test', object_name='verify.txt'))"
```

### Findings log

**Run:** 2026-04-01.

| Step | Result |
|------|--------|
| List buckets (service key) | **`forensics`**, **`models`** present. |
| `upload_forensics_bytes` | Returns path `forensics/pytest_probe.txt` (probe file from verification run; safe to delete in dashboard if desired). |
| Pytest | **`test_supabase_storage_buckets`** passes. |

---

## 4. Upstash Redis (mapping doc §4, lines 171–230)

### Expected behavior

- **`backend/.env`:** `REDIS_URL=rediss://…` **or** `UPSTASH_REDIS_URL=…` (same TCP URL from Upstash **Connect**). `app/config.py` accepts either name via `AliasChoices`.
- **Runtime:** `settings.redis_enabled` is true when the URL is non-empty. Lifespan starts **alert** and **FL** publisher loops (`app/sse_bus.py`) publishing to `bastionfed:alerts` and `bastionfed:fl`.
- **SSE:** `GET /api/events` and `GET /api/fl-events` use Redis pub/sub when Redis is enabled (`app/routers/events.py`). `/health` includes `"sse_bus": "redis"` when the URL is configured (not a live ping — only that the app intends to use Redis).

**REST URL / token:** Optional for HTTP clients; this stack uses **redis-py over `rediss://`** only.

### Codebase checks (static)

| Check | Location |
|-------|----------|
| Settings aliases | `app/config.py` — `redis_url` ← `REDIS_URL` or `UPSTASH_REDIS_URL` |
| Async client | `app/sse_bus.py` — `redis.asyncio.from_url(..., decode_responses=True)` |
| SSE branch | `app/routers/events.py` — `_redis_*_stream` when `settings.redis_enabled` |
| Health flag | `app/main.py` — `payload["sse_bus"] = "redis"` |

### Automated tests (live TCP)

| File | Behavior |
|------|----------|
| `backend/tests/test_upstash_redis_live.py` | **Skipped** if `backend/.env` has no `UPSTASH_REDIS_URL` / `REDIS_URL`. Otherwise: `PING`, pub/sub round-trip on `bastionfed:pytest_verify`, assert `rediss://` scheme. |

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_upstash_redis_live.py -v
```

Full suite still clears Redis in `tests/conftest.py` for API tests; the live file reads the URL **directly from `.env`** via `dotenv_values`, so it does not depend on `settings` during those tests.

### curl checks (local Uvicorn)

With dependencies installed and `.env` loaded as usual:

```bash
cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8766
```

In another shell:

```bash
curl -sS http://127.0.0.1:8766/health
# Expect JSON including "sse_bus":"redis" when URL is set

curl -sS -N --max-time 8 "http://127.0.0.1:8766/api/events?guest=true"
# Expect immediate ": keep-alive" then periodic keep-alives; optional data lines when publishers fire
```

`require_sse_auth` allows `?guest=true` or `?token=…` (no Bearer header on SSE).

### Findings log

**Run:** 2026-04-01 (local machine).

| Step | Command / check | Result |
|------|-----------------|--------|
| Settings | `from app.config import settings` → `redis_enabled` | **True** with `UPSTASH_REDIS_URL` in `backend/.env`; URL scheme **`rediss://`**. |
| Pytest (full) | `pytest tests/ -q` | **56 passed, 1 skipped** when `.env` has DB + Redis URLs (includes live Supabase + Upstash tests). |
| Pytest live only | `tests/test_upstash_redis_live.py` | **PING OK**; **pub/sub OK**; TLS scheme asserted. |
| curl `/health` | Uvicorn `:8766` | **`sse_bus":"redis"`** present alongside persistence/storage flags. |
| curl SSE | `GET /api/events?guest=true` (~6 s) | **`: keep-alive`** received — subscriber path up (no data line required in short window; alert publisher interval default 60 s). |

---

## 5. Operational wiring (implemented)

| Mechanism | Purpose |
|-----------|---------|
| **`BASTIONFED_STRICT_DATA_PLANE=1`** | Startup **fails** if Postgres/Redis/Storage env is incomplete or live probes fail — no silent SQLite fallback. `app/main.py` + `app/data_plane_probes.py`. |
| **`GET /health/ready`** | Deep readiness: **`SELECT 1`**, Redis **`PING`**, Storage bucket list. **200** when all **configured** services pass; **503** if any configured service fails; **200** + **`status":"demo"`** when nothing is configured (e.g. CI). |
| **`GET /api/forensics/samples/{id}/signed-download-url`** | Returns **`signedUrl`** + **`expiresIn`** for private forensics objects (`app/services/supabase_storage.py`, `app/routers/forensics.py`). TTL: **`STORAGE_SIGNED_URL_EXPIRES_S`** (default 3600). |

```bash
curl -sS http://127.0.0.1:8000/health/ready
curl -sS -H "Authorization: Bearer <firebase-id-token>" \
  "http://127.0.0.1:8000/api/forensics/samples/<id>/signed-download-url"
```

---

## 6. Residual gaps (non–data-plane or future work)

| Topic | Notes |
|-------|--------|
| **Connector rollout / monitoring** | Ingest schema and `/api/ingest/*` exist, but production SIEM/EDR/ticket integrations still need real deployments, secret rotation operations, and monitoring. |
| **Forensics operating procedures** | Storage, lifecycle metadata, signed download, and custody audit are implemented, but scanning, isolation, legal handling, and retention enforcement still need independent evidence. |
| **FV drift semantics** | Review whether implemented FV drift math matches the documented statistical intent before making strong claims. |
| **Firestore E2E** (`users/{uid}` write) | Manual browser + Console; see §1. |

---

## Revision history

| Date | Notes |
|------|--------|
| 2026-04-01 | Initial template + §1 Firebase/Firestore procedure and first verification run (pytest + env + curl probes). |
| 2026-04-01 | §4 Upstash: live pytest module, `/health` + SSE curl procedure, findings. |
| 2026-04-01 | §2–§3 Supabase Postgres + Storage: pooler region fix, `test_supabase_live.py`, mapping table row for regional transaction pooler. |
| 2026-04-04 | §0 index, §0.1 env→code, Postgres table list, §5 residual gaps; pytest counts generalized; cross-links to Blue Team; mapping doc alignment (`httpx`, `bf_bundle`). |
| 2026-04-04 | §5 strict mode + `/health/ready` + forensics signed URL; §6 residual; `data_plane_probes.py`, pytest 56. |
| 2026-04-05 | Cross-doc alignment with tenant-scoped normalized SQL, verified Firebase JWT auth, ingest/forensics lifecycle, and removal of stale `X-BastionFed-UID` / `bf_bundle` runtime wording. |
