# BastionFed — Data Plane Mapping (Zero-Cost Demo Stack)

Single-project view: treat **Firebase** as the control plane (Auth, console, rules) while **Supabase (PostgreSQL + Storage)**, **Firestore**, and **Upstash (Redis)** are the data planes attached to this project.

---

## Zero-Cost Demo Stack Summary

| Service | Provider | Cost | Notes |
|---------|----------|------|-------|
| **Auth** | Firebase Auth | Free (Spark plan) | Already configured |
| **User profiles (NoSQL)** | Cloud Firestore | Free (Spark plan) | `users/{uid}` mirror |
| **Blob / object storage** | **Supabase Storage** | Free forever | 1 GB storage, 50 MB max per file, no card |
| **Relational SQL** | **Supabase PostgreSQL** | Free forever | Raw `DATABASE_URL` for FastAPI |
| **Redis (SSE pub/sub)** | **Upstash** | Free forever | `REDIS_URL` + REST token |

> ⚠️ **Firebase Storage is not used.** The Firebase console Storage setup fails on the Spark plan due to a GCP resource location conflict, and creating a bucket via GCP Console requires a billing account. Supabase Storage is the zero-friction, zero-cost replacement — it lives in the same Supabase project as PostgreSQL, so no extra signup is needed.

---

## Firebase-family options (by "database type")

| Type | Product | Role in this stack |
|------|---------|-------------------|
| **Relational SQL** | **Supabase PostgreSQL** (free, external) | System of record for structured entities, joins, filters, audit chains, reporting. Replaces Cloud SQL — same `DATABASE_URL` interface, zero cost. |
| **NoSQL (document)** | **Cloud Firestore** (Firebase Spark) | Small documents — client-side profile mirror only. Not for weights or huge nested forensics blobs as primary store. |
| **NoSQL (JSON tree)** | **Realtime Database** | Not used (`getFirestore` is what you ship); avoid duplicating Firestore. |
| **Object / blob** | **Supabase Storage** (free, external) | Binaries and large artifacts: malware samples, model checkpoints, exports. Replaces Firebase/GCP Storage — same S3-compatible pattern, zero cost. Metadata (hashes, paths) belongs in SQL. |
| **Cache / pub-sub** | **Upstash Redis** (free, external) | SSE pub/sub for `/api/events` and `/api/fl-events`. Replaces GCP Memorystore — same Redis protocol, zero cost. |

---

## Implementation alignment (FastAPI — read with Blue Team + verification docs)

The tables below name **Supabase PostgreSQL** as the backing service. In the unified backend, FastAPI persists like this:

| Topic | Actual code path |
|-------|------------------|
| **Operational data** (users, tenants, memberships, alerts, incidents, devices, FL metadata, forensics metadata, audit log chain, ingest config, raw ingest events) | Normalized tenant-scoped SQL tables via `app/db/migrations/*.sql` and `app/store/tenant_store.py`. |
| **BastionBot** | **`bot_conversations`**, **`bot_messages`**, **`bot_user_memory`** in the same Postgres DB when the pooler connection succeeds (`app/bastionbot/pg_store.py`). |
| **Object uploads** | **HTTP** via **`httpx`** + service role to Storage REST (`app/services/supabase_storage.py`) — **not** the `supabase-py` client. |
| **API auth** | Client sends **`Authorization: Bearer …`** (Firebase ID token in normal use). FastAPI verifies Firebase JWTs against signing keys in `app/auth/firebase.py`. Runtime still requires `PyJWT[crypto]` to be installed in the deployed `.venv` or container. |
| **Strict startup** | Set **`BASTIONFED_STRICT_DATA_PLANE=1`** in `backend/.env` to **require** Postgres + Redis + Supabase Storage env vars and **pass live probes** at startup. No silent fallback to SQLite/in-memory when the database is misconfigured. |
| **Readiness** | **`GET /health/ready`** runs **`SELECT 1`**, Redis **`PING`**, and Storage bucket list for configured services; returns **503** if any configured service fails. |
| **Signed downloads** | **`GET /api/forensics/samples/{id}/signed-download-url`** issues a time-limited URL for the object in private Storage (TTL from **`STORAGE_SIGNED_URL_EXPIRES_S`**, default 3600). |

**Legacy note:** `app/db/persistence.py` and `bf_bundle` remain in the repo only as historical helpers and should not be used for new runtime wiring.

---

## Map: surface → service

### Frontend

| Concern | Service type | Concrete product | Notes |
|--------|-------------|-----------------|-------|
| Sign-in / tokens | Auth | **Firebase Auth** | Client obtains ID tokens; FastAPI expects `Authorization: Bearer …` and verifies Firebase JWTs on the API. The implementation uses signing keys via `PyJWT[crypto]`; it does **not** depend on the Firebase Admin SDK specifically. |
| User profile mirror on login | NoSQL | **Firestore** `users/{uid}` | Implemented in `auth-context.tsx` via `setDoc` / `merge`. |
| All app data (alerts, incidents, FL UI) | API contract | **FastAPI** → reads/writes **Supabase PostgreSQL** | Not the browser. |
| Large uploads from browser | Object | **Supabase Storage** | Backend uploads to Supabase Storage via service key; stores resulting path in SQL. |

### Backend + `BACKEND_PRD.md`

| Domain / endpoint area | Service type | Concrete product | Notes (this repo) |
|------------------------|-------------|-----------------|-------------------|
| `POST /api/auth/session`, users | SQL + NoSQL mirror | **Supabase PostgreSQL** + **Firestore** | Server source of truth is normalized SQL (`users`, `tenants`, `memberships`); Firestore remains `users/{uid}` profile mirror from the client. |
| Alerts, incidents, devices, nested playbooks/timelines | SQL | **Supabase PostgreSQL** | Normalized tenant-scoped tables with provenance fields and ingest linkage. |
| FL: `/api/fl/status`, rounds, clients, drift, model zoo list (metadata only) | SQL | **Supabase PostgreSQL** | Tenant-scoped tables plus explicit research/demo labeling where telemetry is synthetic. |
| `POST /api/fl/models/.../activate` | Orchestration | **FastAPI + FL/inference** | In-process activation; large artifacts may use **Supabase Storage** `models/` when uploaded. |
| Audit logs + `/api/audit/verify` chain + export | SQL | **Supabase PostgreSQL** | Dedicated tenant-scoped `audit_log` table with verify and export endpoints. |
| BastionBot conversations | SQL (tables) | **Supabase PostgreSQL** | **`bot_*`** tables when Postgres path active. |
| Forensics samples binary + RCA rich text | Object + SQL | **Supabase Storage** + **Supabase PostgreSQL** | Binary in **`forensics/`** bucket via **`httpx`**; metadata tracks scan/quarantine/retention/custody states in SQL. |
| Ingest sources + external event normalization | SQL + HTTP API | **Supabase PostgreSQL** + **FastAPI** | `ingest_sources`, `ingest_events`, and `/api/ingest/*` support tenant-scoped push connectors. |
| SSE `/api/events`, `/api/fl-events` | Ephemeral / cache | **Upstash Redis** | Tenant-scoped pub/sub channels when Redis URL set. |

### `backend/data/models` + `FL/` (notebooks / CSVs)

| Artifact | Service type | Concrete product | Notes |
|---------|-------------|-----------------|-------|
| Local `*.csv`, notebooks under `FL/` | Local / ad hoc | None | Training/experiment inputs only. |
| Published global checkpoints under **`backend/data/models/`** (gitignored locally), client bundle artifacts | Object + SQL metadata | **Supabase Storage** `models/` bucket + **Supabase PostgreSQL** | Canonical on-disk layout: `backend/DATA_DIRECTORY.md`. Active model metadata in tenant-scoped SQL. ⚠️ 50 MB per-file limit on free tier. |
| Aggregator round logs / metrics | SQL | **Supabase PostgreSQL** | Round/client lists in normalized tables; per-client drift is still labeled demo/research unless real telemetry is attached. |

---

## Consolidated picture

- **Firebase Auth**: frontend sign-in; tokens sent to API and verified on FastAPI against Firebase signing keys.
- **Firestore**: client user profile documents (`users/{uid}`) only — **not** the main platform DB.
- **Supabase Storage**: malware binaries, model weights/artifacts, any large files; referenced by path from state / metadata. Same Supabase project as PostgreSQL; uploads use **REST + `httpx`**.
- **Supabase PostgreSQL**: durable store for tenant-scoped normalized tables + **`bot_*`** (BastionBot).
- **Upstash Redis**: SSE pub/sub — ephemeral, serverless, zero cost.

---

## Provisioning Guide (Zero-Cost, Console-Only)

### 1. 🟠 Cloud Firestore (Firebase Spark — Free)

**Purpose:** `users/{uid}` profile mirror written by `auth-context.tsx`.

**Status:** ✅ Already provisioned in `us-central1`.

**Rules** — go to Firebase Console → **Firestore Database** → **Rules** tab → publish:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

**No new env vars needed** — your existing `NEXT_PUBLIC_FIREBASE_*` vars cover this.

---

### 2. 🔷 Supabase PostgreSQL (Free Forever — No Credit Card)

**Purpose:** Primary relational store for users, alerts, incidents, FL metadata, audit logs, BastionBot.

**Free tier limits:** 500 MB database, no credit card, no time limit. ⚠️ Project pauses after 7 days of inactivity — unpause it from the dashboard before a demo session.

**Setup:**
1. Go to [supabase.com](https://supabase.com) → click **"Start your project"** → sign up with GitHub or email (no card required).
2. Click **"New project"** → fill in:
   - **Project name:** `bastionfed`
   - **Database password:** choose a strong password — **copy and save it now**
   - **Region:** pick the closest to you (e.g. `us-east-1`)
3. Click **"Create new project"** — provisioning takes ~2 minutes.
4. Once ready, click the **"Connect"** button at the top of the dashboard.
5. Choose the connection method that matches how you connect (see below — **do not mix** session-style usernames with transaction-style hosts).
6. Copy the URI **exactly** from the dashboard and paste into `backend/.env` as `DATABASE_URL` or `SUPABASE_DATABASE_URL`.

**Supabase URI shapes (from [Connect to Postgres](https://supabase.com/docs/guides/database/connecting-to-postgres)):**

| Mode | Typical URI pattern | Notes |
|------|---------------------|--------|
| **Transaction pooler** | `postgres://postgres:[PASSWORD]@db.<project-ref>.supabase.co:6543/postgres` | User is **`postgres`** (not `postgres.<ref>`). Host is **`db.<ref>.supabase.co`**. Good for pooled / many short queries. |
| **Transaction pooler (regional pooler host)** | `postgres://postgres.<ref>:[PASSWORD]@aws-<n>-<region>.pooler.supabase.com:6543/postgres` | Dashboard **Transaction** mode sometimes shows this shape: user **`postgres.<ref>`**, port **6543**, host **`aws-*-<region>.pooler.supabase.com`**. The **`<region>` segment must match your project’s pooler region** (copy from Connect — do not substitute another region). |
| **Session pooler (Supavisor)** | `postgres://postgres.<ref>:[PASSWORD]@aws-0-<region>.pooler.supabase.com:5432/postgres` | User is **`postgres.<ref>`**. Port **5432**. Use if you need session semantics or hit IPv4 pooler. |

⚠️ Using **`postgres.<ref>`** with **`aws-…pooler.supabase.com:6543`** from the **wrong region** (e.g. a `us-east-1` pooler hostname for a project whose pooler is `ap-south-1`) yields **`FATAL: Tenant or user not found`**. Paste the URI **exactly** from the Connect modal for **this** project.

**Psycopg:** Transaction mode does not support server-side prepared statements the same way; if you see related errors, set `prepare_threshold=None` on the connection (see [Supabase discussion on prepared statements](https://github.com/orgs/supabase/discussions/28239)).

**Add to your backend `.env` (example — use your dashboard copy, not this literal):**
```
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.<project-ref>.supabase.co:6543/postgres
```

If connection still fails after a password reset, see [Supabase issue #42581](https://github.com/supabase/supabase/issues/42581) (pooler sync / support ticket).

> **Alternative — Neon (if you prefer auto-resume on connection):**
> Go to [neon.tech](https://neon.tech) → sign up (no card) → create a project → copy the connection string from the dashboard. Same `DATABASE_URL` format. 0.5 GB free, never pauses — scales to zero and auto-resumes on connection.

---

### 3. 🟢 Supabase Storage (Free Forever — No Credit Card)

**Purpose:** Malware sample binaries, FL model checkpoints. Lives inside the same Supabase project as PostgreSQL — no extra signup.

**Free tier limits:** 1 GB total file storage, **50 MB max per individual file**, no credit card. Sufficient for demo malware samples and model checkpoints.

**Setup (inside your existing Supabase project):**
1. In your Supabase project dashboard, click **"Storage"** in the left nav.
2. Click **"New bucket"** → create the following two buckets:
   - **Name:** `forensics` → keep **Public** toggle **OFF** (private) → click **Create bucket**
   - **Name:** `models` → keep **Public** toggle **OFF** (private) → click **Create bucket**
3. For each bucket, click the **three dots (⋮)** → **"Edit bucket"** → confirm **Public** is off (backend accesses via service key, not public URLs).
4. To get your API credentials, go to **Project Settings** (gear icon) → **API**:
   - Copy the **Project URL** — looks like `https://[ref].supabase.co`
   - Copy the **`service_role`** key (under "Project API keys") — this is what your backend uses to upload files. **Keep this secret — never expose it client-side.**

**Add to your backend `.env`:**
```
SUPABASE_URL=https://[ref].supabase.co
SUPABASE_SERVICE_KEY=[your-service-role-key]
```

> **How your backend uses it:** The FastAPI backend uses **direct HTTP** (`httpx`) with the **service role** key against the Storage REST API to upload to the `forensics/` or `models/` bucket, then stores the returned object path in tenant-scoped SQL metadata. You may add `supabase-py` later for convenience; it is **not** required for the current upload path.

---

### 4. 🔴 Upstash Redis (Free Forever — No Credit Card)

**Purpose:** SSE pub/sub for `/api/events` and `/api/fl-events` endpoints.

**Free tier limits:** 256 MB data, 500K commands/month, 10 GB bandwidth — more than sufficient for demo SSE workloads.

**Setup:**
1. Go to [upstash.com](https://upstash.com) → click **"Start for free"** → sign up with GitHub or Google (no card required).
2. In the console, click **"Create Database"**.
3. Fill in:
   - **Name:** `bastionfed-redis`
   - **Type:** `Regional` (sufficient for demo)
   - **Region:** pick the closest (e.g. `us-east-1`)
   - **TLS:** enabled (leave on)
4. Click **"Create"**.
5. On the database details page, scroll to the **"Connect"** section. You'll find:
   - **`UPSTASH_REDIS_URL`** — the standard `rediss://...` TCP URL (use this for `redis-py`)
   - **`UPSTASH_REDIS_REST_URL`** — the REST endpoint (for HTTP-based clients)
   - **`UPSTASH_REDIS_REST_TOKEN`** — the REST auth token

**Add to your backend `.env`:**
```
REDIS_URL=rediss://default:[PASSWORD]@[your-db].upstash.io:6379
```

> **Note:** For a standard FastAPI backend using `redis-py`, use `REDIS_URL` (the `rediss://` TCP string). For serverless/edge environments, use `UPSTASH_REDIS_REST_URL` + `UPSTASH_REDIS_REST_TOKEN` instead.

---

## Backend `.env` — Complete Reference

```env
# --- Firebase Auth (frontend + optional Admin SDK) ---
NEXT_PUBLIC_FIREBASE_API_KEY=<your-web-api-key>
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=<project>.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=<project-id>
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=<project>.firebasestorage.app
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=<sender-id>
NEXT_PUBLIC_FIREBASE_APP_ID=<app-id>
NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID=<measurement-id>

# --- Supabase PostgreSQL ---
# Paste EXACTLY from Dashboard → Connect (transaction or session tab). Do not mix user/host/region — see §2 table.
# Examples:
#   postgresql://postgres:[PWD]@db.<project-ref>.supabase.co:6543/postgres
#   postgresql://postgres.<ref>:[PWD]@aws-<n>-<region>.pooler.supabase.com:6543/postgres
DATABASE_URL=postgresql://...
# (alias) SUPABASE_DATABASE_URL=... same value

# --- Supabase Storage (same project) ---
SUPABASE_URL=https://[ref].supabase.co
SUPABASE_PROJECT_URL=https://[ref].supabase.co
SUPABASE_SERVICE_KEY=<service-role-secret>

# --- Upstash Redis ---
REDIS_URL=rediss://default:[PASSWORD]@[host].upstash.io:6379
# (alias) UPSTASH_REDIS_URL=...

# --- Optional: fail startup if any data-plane service is missing or unhealthy ---
# BASTIONFED_STRICT_DATA_PLANE=1
# STORAGE_SIGNED_URL_EXPIRES_S=3600
```

---

## Related docs

- [`BACKEND_PRD.md`](./BACKEND_PRD.md) — API and environment expectations (`DATABASE_URL`, object storage, Redis, Firebase).
- [`DATA_PLANE_VERIFICATION.md`](./DATA_PLANE_VERIFICATION.md) — Verification commands and findings.
- [`BLUE_TEAM_APPLICATION_SPEC.md`](./BLUE_TEAM_APPLICATION_SPEC.md) — Reviewer-facing claims vs implementation (incl. API auth stub).
