# Faheem stack & testing — gap remediation log

This document records **backend, test, frontend, and documentation** changes made to close gaps between **Faheem’s FastAPI** (`backend/faheem_implementation/`), **pytest**, **live Uvicorn**, and the **Next.js** client (duplicate fetches, missing routes for single-host dev).

**Related:** [`FAHEEM_BACKEND_TODO.md`](./FAHEEM_BACKEND_TODO.md) (§2 cross-team / monorepo dev), [`FAHEEM_LOCAL_TESTING.md`](./FAHEEM_LOCAL_TESTING.md), [`FAHEEM_BACKEND_IMPLEMENTATION.md`](./FAHEEM_BACKEND_IMPLEMENTATION.md).

---

## 1. Problem summary (gaps addressed)

| Gap | Issue | Remediation |
|-----|--------|-------------|
| **404 on FL / incidents** | Frontend called `GET /api/fl/clients`, `GET /api/fl-events`, `GET /api/incidents` while only detail/single-client routes existed on Faheem’s app. | Implemented list + FL SSE on `faheem_implementation` (same in-memory store). |
| **Pytest vs live server** | `TestClient` never opens TCP to Uvicorn; green pytest did not prove a running server. | Added optional **`LIVE_SERVER_URL`** integration tests (`test_live_server.py`). |
| **SSE in-process** | `TestClient.stream` + `iter_bytes()` on infinite `StreamingResponse` **hangs** (Starlette/httpx limitation). | Removed blocking stream tests; document limitation; assert SSE bodies via **live** httpx tests. |
| **Duplicate browser requests** | React 18 Strict Mode / effect remounts could double JSON fetches. | `AbortController` + `fetch` `signal`; ignore `AbortError` in catch. |
| **Docs drift** | Split doc said Hunain owned list/SSE; repo needed one-host manual QA story. | Updated FAHEEM docs: monorepo dev copies + test counts + `LIVE_SERVER_URL`. |

---

## 2. Backend (`backend/faheem_implementation/`)

### 2.1 New / extended routes

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/incidents` | Kanban list — `IncidentListResponse` (`items`, `nextCursor`, `total`). |
| `GET` | `/api/fl/clients` | FL grid seed — `FLClientsListResponse` (`clients`). **Registered before** `/api/fl/clients/{client_id}` so path matching is correct. |
| `GET` | `/api/fl-events` | FL client patch SSE (`text/event-stream`), `: keep-alive` + `data:` JSON with `id`, `participationPct`. |

**Ownership note:** [`API_ENDPOINTS_IMPLEMENTATION_SPLIT.md`](../API_ENDPOINTS_IMPLEMENTATION_SPLIT.md) still assigns list + FL SSE to **Hunain** for the long-term split; `faheem_implementation` holds **working monorepo copies** for single Uvicorn dev until backends merge.

### 2.2 Files touched (create or modify)

| File | Change |
|------|--------|
| [`app/main.py`](../../backend/faheem_implementation/app/main.py) | Import and `include_router(fl_events.router, prefix="/api")`. |
| [`app/routers/fl_events.py`](../../backend/faheem_implementation/app/routers/fl_events.py) | **New** — FL SSE stream (synthetic patches, tunable `_SSE_TICK_S`, `_KEEPALIVE_EVERY_S`). |
| [`app/routers/fl.py`](../../backend/faheem_implementation/app/routers/fl.py) | `GET /fl/clients` list before `/{client_id}` detail. |
| [`app/routers/incidents.py`](../../backend/faheem_implementation/app/routers/incidents.py) | `GET /incidents` list before `/{incident_id}` detail. |
| [`app/models/api.py`](../../backend/faheem_implementation/app/models/api.py) | `IncidentListResponse`, `FLClientsListResponse`. |
| [`app/store/memory.py`](../../backend/faheem_implementation/app/store/memory.py) | `list_incidents()`, `next_streaming_fl_patch()` for FL SSE payloads. |

### 2.3 Still not implemented on this app

- **`GET /api/audit/logs`** — audit **table** in the UI; verify endpoint remains `GET /api/audit/verify` on Faheem’s app.

---

## 3. Tests (`backend/faheem_implementation/tests/`)

### 3.1 `test_faheem_endpoints.py`

- OpenAPI path assertions extended: `/api/incidents`, `/api/fl/clients`, `/api/fl-events`.
- **New:** `test_incidents_list_guest`, `test_fl_clients_list_guest`.
- **New:** `test_fl_events_unauthenticated` (401 without auth).
- **SSE:** Removed `TestClient.stream` / `iter_bytes()` tests that hung; comment explains **live** coverage.
- **Kept:** `test_events_unauthenticated`, guest/auth coverage for the rest.

### 3.2 `test_live_server.py` (new)

- Runs only when **`LIVE_SERVER_URL`** is set (e.g. `http://127.0.0.1:8000`).
- **`@pytest.mark.integration`** (registered in `pytest.ini`).
- Tests: `GET /health`, OpenAPI includes core paths, **httpx** stream read of **`/api/events?guest=true`** and **`/api/fl-events?guest=true`** until buffer contains SSE framing + `data:`.

### 3.3 `pytest.ini`

- `markers`: `integration` documented for live TCP tests.

### 3.4 Expected counts (default env)

```text
pytest tests -v   → 36 passed, 4 skipped   # integration skipped if LIVE_SERVER_URL unset
```

---

## 4. Frontend (`frontend/`)

### 4.1 `lib/api.ts`

- **`isAbortError(e)`** — detects `DOMException` + `AbortError` from aborted `fetch`.

### 4.2 AbortController + `signal` on JSON loads

Each effect cleanup calls **`ac.abort()`**; catches ignore abort so Strict Mode remounts do not surface false errors.

| File |
|------|
| `contexts/alerts-context.tsx` |
| `contexts/fl-clients-context.tsx` |
| `app/incidents/page.tsx` |
| `app/forensics/page.tsx` |
| `components/dashboard/KPICards.tsx` |
| `components/fl-health/RoundStatusBanner.tsx` |
| `components/fl-health/ClientGrid.tsx` (detail refresh) |
| `components/incidents/IncidentDetail.tsx` |
| `components/audit/AuditLogTable.tsx` |

**Unchanged:** `EventSource` for `/api/events` and `/api/fl-events` (browser-managed lifecycle).

### 4.3 Lint note

- **Pre-existing:** `RoundStatusBanner.tsx` may still trigger `react-hooks/set-state-in-effect` for syncing countdown from `status` (not introduced by abort work). Other repo lint errors may exist outside these files.

---

## 5. Documentation (`docs/`)

| File | Updates |
|------|---------|
| [`FAHEEM/FAHEEM_BACKEND_TODO.md`](./FAHEEM_BACKEND_TODO.md) | §2 rewritten: monorepo dev routes vs split-doc owners; dependency table simplified. |
| [`FAHEEM/FAHEEM_BACKEND_IMPLEMENTATION.md`](./FAHEEM_BACKEND_IMPLEMENTATION.md) | Monorepo extensions (incidents list, FL list, FL SSE); cross-team blurb. |
| [`FAHEEM/FAHEEM_LOCAL_TESTING.md`](./FAHEEM_LOCAL_TESTING.md) | `faheem_implementation` paths, **36** + **4 skipped**, **`LIVE_SERVER_URL`** + SSE live tests. |
| [`TODO.md`](../TODO.md) | Faheem bullet: pointer to FAHEEM_BACKEND_TODO §2 (from earlier session). |
| [`API_ENDPOINTS_IMPLEMENTATION_SPLIT.md`](../API_ENDPOINTS_IMPLEMENTATION_SPLIT.md) | Integration note after Faheem’s 12 routes (from earlier session). |

**This file:** [`FAHEEM/FAHEEM_GAP_REMEDIATION_LOG.md`](./FAHEEM_GAP_REMEDIATION_LOG.md) — full change log for the remediation described above.

---

## 6. Commands (copy-paste)

**In-process API tests (no server required):**

```bash
cd /path/to/bastionfed-system-application/backend/faheem_implementation
source .venv/bin/activate
pytest tests -v
# expect: 36 passed, 4 skipped (unless LIVE_SERVER_URL is set)
```

**Against running Uvicorn (real TCP + SSE bodies):**

```bash
# terminal A
cd backend/faheem_implementation && source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# terminal B
export LIVE_SERVER_URL=http://127.0.0.1:8000
cd backend/faheem_implementation && source .venv/bin/activate
pytest tests/test_live_server.py -v
```

**Full suite including integration (when env set):**

```bash
export LIVE_SERVER_URL=http://127.0.0.1:8000
pytest tests -v
# expect: 40 passed, 0 skipped
```

---

## 7. Version / scope

- **Scope:** Faheem monorepo FastAPI + Next client wiring for local full-stack QA; in-memory phase 1.
- **Out of scope:** Real Firebase Admin, Redis SSE, `GET /api/audit/logs` implementation, Hunain/Hammad duplicate implementations in their own `*_implementation` trees.

*Last aligned with repository state when this log was added.*
