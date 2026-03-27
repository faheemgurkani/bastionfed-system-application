# Faheem Backend Implementation — Status & Runbook

This document describes what was implemented for **Faheem’s 12 endpoints** per [`API_ENDPOINTS_IMPLEMENTATION_SPLIT.md`](./API_ENDPOINTS_IMPLEMENTATION_SPLIT.md) (lines 65–83) and the implementation plan aligned with [`BACKEND_PRD.md`](./BACKEND_PRD.md).

**Scope (phase 1):** FastAPI service with **in-memory** persistence seeded from [`frontend/lib/mock-data.ts`](../frontend/lib/mock-data.ts), **stub auth** (no Firebase Admin verification yet), and Next.js wired to `http://localhost:8000` (or `NEXT_PUBLIC_API_URL`).

---

## Implemented endpoints (Faheem)

| Difficulty | Method | Path |
|------------|--------|------|
| Easy | GET | `/api/alerts` |
| Easy | GET | `/api/incidents/{incident_id}` |
| Easy | GET | `/api/fl/status` |
| Easy | GET | `/api/fl/clients/{client_id}` |
| Easy | GET | `/api/forensics/samples` |
| Easy | GET | `/api/forensics/rca/{rca_id}` |
| Medium | PATCH | `/api/alerts/{alert_id}` |
| Medium | GET | `/api/dashboard/kpis` |
| Medium | POST | `/api/auth/session` |
| Hard | GET | `/api/events` (SSE) |
| Hard | POST | `/api/devices/{device_id}/quarantine` |
| Hard | GET | `/api/audit/verify` |

Additional non-contract routes:

- `GET /health` — liveness

**Monorepo dev (single-stack manual testing):** this tree also implements **`GET /api/incidents`** (list), **`GET /api/fl/clients`** (list), and **`GET /api/fl-events`** (SSE) against the same `AppState` so Next.js does not 404 on those calls when only Faheem’s FastAPI is running. Long-term ownership for those paths remains with **Hunain** in [`API_ENDPOINTS_IMPLEMENTATION_SPLIT.md`](../API_ENDPOINTS_IMPLEMENTATION_SPLIT.md); the implementations here are the **integrated dev copy**.

Full API contracts remain defined in [`BACKEND_PRD.md`](./BACKEND_PRD.md).

### Cross-team dependencies (Faheem routes vs the rest of the UI)

Faheem’s **twelve** routes are enough for **pytest** and for clients that only exercise that surface. The **Next.js app** Faheem wired also calls endpoints owned by **Hunain** and **Hammad** — for example **`GET /api/incidents`** (Kanban list), **`GET /api/fl/clients`** (FL grid seed), **`GET /api/fl-events`** (FL SSE), and **`GET /api/audit/logs`** (audit table). Those must exist on the **same** `NEXT_PUBLIC_API_URL` host (or the client must use multiple bases) for full end-to-end behavior.

**Why:** [`API_ENDPOINTS_IMPLEMENTATION_SPLIT.md`](../API_ENDPOINTS_IMPLEMENTATION_SPLIT.md) assigns **list**, **SSE**, and **supplementary** reads to teammates while Faheem owns **detail**, selected **mutations**, and **audit verify** in the same domains. Typical UI flows need **both** (e.g. list incidents → open Faheem’s detail; seed FL clients → apply Hunain’s SSE patches).

**Integrator requirements:** One FastAPI app or gateway mounting all routers; consistent **guest / Bearer** rules; shared **IDs** aligned with [`frontend/lib/mock-data.ts`](../frontend/lib/mock-data.ts) in phase 1. A full dependency table and “why” per screen is in [`FAHEEM_BACKEND_TODO.md`](./FAHEEM_BACKEND_TODO.md) **§2**.

---

## Backend (`backend/faheem_implementation/`)

### Application entry

- **[`backend/faheem_implementation/app/main.py`](../backend/faheem_implementation/app/main.py)** — FastAPI app, CORS from `ALLOWED_ORIGINS` ([`backend/faheem_implementation/app/config.py`](../backend/faheem_implementation/app/config.py)), **lifespan** runs **`state.reset()`** on startup, mounts routers under `/api`, exposes `/health`.

### Data layer

- **[`backend/faheem_implementation/app/store/memory.py`](../backend/faheem_implementation/app/store/memory.py)** — **`AppState`**: in-memory lists/dicts for alerts, incidents, devices, FL rounds/clients, malware samples, RCA reports, audit logs, users.
- **[`backend/faheem_implementation/app/store/seed_data.py`](../backend/faheem_implementation/app/store/seed_data.py)** — Seed snapshots aligned with frontend mocks (`MOCK_DEVICES`, alerts, incidents, FL, forensics, RCA, etc.).

### Audit integrity

- Append-only audit rows with a **SHA-256 hash chain** (previous hash + timestamp + actor + action + target + result).
- **`GET /api/audit/verify`** — Recomputes the chain; returns `{ valid, totalLogs, checkedAt }` or, on failure, `{ valid: false, firstBreakAt, totalLogs, checkedAt }`.
- Automated tests include a **tampered chain** scenario.

### Authentication (stub)

- **[`backend/faheem_implementation/app/auth/deps.py`](../backend/faheem_implementation/app/auth/deps.py)**:
  - **GET** (non-SSE): `Authorization: Bearer <token>` **or** `?guest=true`.
  - **SSE** `/api/events`: `?token=<firebase_id_token>` **or** `?guest=true` (per PRD / `EventSource` constraints).
  - **Mutations** (PATCH/POST): require **Bearer**; **guest** receives **403** on those routes.
  - No call to Firebase Admin SDK yet; bearer presence is treated as an authenticated user for `actor` / dependency wiring.

### Server-Sent Events

- **`GET /api/events`** — `text/event-stream`; comment pings **`: keep-alive`**, periodic **`data: <Alert JSON>`** lines built from **`state.next_streaming_alert()`** (synthetic new ids/timestamps; no historical replay on connect per PRD intent).
- Event interval is a **short tick** in code for responsiveness; adjust in [`backend/faheem_implementation/app/routers/events.py`](../backend/faheem_implementation/app/routers/events.py) if you need production-like spacing.

### Routers (by file)

| Area | Module |
|------|--------|
| Alerts | [`backend/faheem_implementation/app/routers/alerts.py`](../backend/faheem_implementation/app/routers/alerts.py) |
| Incidents | [`backend/faheem_implementation/app/routers/incidents.py`](../backend/faheem_implementation/app/routers/incidents.py) |
| FL | [`backend/faheem_implementation/app/routers/fl.py`](../backend/faheem_implementation/app/routers/fl.py) |
| Forensics | [`backend/faheem_implementation/app/routers/forensics.py`](../backend/faheem_implementation/app/routers/forensics.py) |
| Devices | [`backend/faheem_implementation/app/routers/devices.py`](../backend/faheem_implementation/app/routers/devices.py) |
| Audit | [`backend/faheem_implementation/app/routers/audit.py`](../backend/faheem_implementation/app/routers/audit.py) |
| Auth | [`backend/faheem_implementation/app/routers/auth.py`](../backend/faheem_implementation/app/routers/auth.py) |
| Dashboard | [`backend/faheem_implementation/app/routers/dashboard.py`](../backend/faheem_implementation/app/routers/dashboard.py) |
| SSE | [`backend/faheem_implementation/app/routers/events.py`](../backend/faheem_implementation/app/routers/events.py) |

### Domain models

- **[`backend/faheem_implementation/app/models/domain.py`](../backend/faheem_implementation/app/models/domain.py)** — PRD-aligned Pydantic models (camelCase JSON via alias generator).
- **[`backend/faheem_implementation/app/models/api.py`](../backend/faheem_implementation/app/models/api.py)** — List/session/KPI helper schemas where useful.

### Tests

- **[`backend/faheem_implementation/tests/test_faheem_endpoints.py`](../backend/faheem_implementation/tests/test_faheem_endpoints.py)** — OpenAPI path checks; alerts filters / pagination / sort; PATCH **404** / **400** / auth errors; incidents, FL, forensics, RCA **404**s; KPI shape; auth session **401**/**403**; quarantine **404** + incident timeline side effect; audit verify + tamper; SSE **401** only (stream body not asserted in pytest—use **`curl`** / browser; see [`FAHEEM_LOCAL_TESTING.md`](./FAHEEM_LOCAL_TESTING.md)).
- **[`backend/faheem_implementation/pytest.ini`](../backend/faheem_implementation/pytest.ini)** — `pythonpath = .` for `app` imports.
- **Query params:** `GET /api/alerts` uses PRD names **`status`**, **`from`**, **`to`** (via FastAPI aliases). `GET /api/forensics/samples` uses **`status`** for sample status.

Run tests:

```bash
cd backend/faheem_implementation && source .venv/bin/activate && pytest tests/test_faheem_endpoints.py -q
```

**Step-by-step local stack + fuller test description:** see [`FAHEEM_LOCAL_TESTING.md`](./FAHEEM_LOCAL_TESTING.md).

### Run backend (development)

```bash
cd backend/faheem_implementation
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

See also [`backend/faheem_implementation/README.md`](../backend/faheem_implementation/README.md).

---

## Frontend wiring (`frontend/`)

### Configuration

- **[`frontend/lib/api.ts`](../frontend/lib/api.ts)** — `NEXT_PUBLIC_API_URL` (default **`http://localhost:8000`**), `apiUrl`, `apiFetchJson`, **`eventsSourceUrl`** for SSE query params.
- **[`frontend/.env.example`](../frontend/.env.example)** — Documents `NEXT_PUBLIC_API_URL`.

### Features using the FastAPI backend

| Feature | Integration |
|---------|----------------|
| Alerts | [`frontend/contexts/alerts-context.tsx`](../frontend/contexts/alerts-context.tsx) — `GET /api/alerts`, `EventSource` → FastAPI `/api/events` (`?guest=true` or `?token=…`). |
| Auth session | [`frontend/contexts/auth-context.tsx`](../frontend/contexts/auth-context.tsx) — After Firebase sign-in / Firestore profile upsert, `POST /api/auth/session` with **Bearer** (backend should be reachable). |
| Dashboard KPIs | [`frontend/components/dashboard/KPICards.tsx`](../frontend/components/dashboard/KPICards.tsx) — `GET /api/dashboard/kpis`. |
| FL banner | [`frontend/components/fl-health/RoundStatusBanner.tsx`](../frontend/components/fl-health/RoundStatusBanner.tsx) — `GET /api/fl/status`. |
| FL client detail | [`frontend/components/fl-health/ClientGrid.tsx`](../frontend/components/fl-health/ClientGrid.tsx) — `GET /api/fl/clients/{client_id}` when opening detail. |
| Forensics | [`frontend/app/forensics/page.tsx`](../frontend/app/forensics/page.tsx) — `GET /api/forensics/samples`. |
| Incident detail | [`frontend/components/incidents/IncidentDetail.tsx`](../frontend/components/incidents/IncidentDetail.tsx) — `GET /api/incidents/{incident_id}`. |
| Alert actions | [`frontend/components/alerts/AlertDetailDrawer.tsx`](../frontend/components/alerts/AlertDetailDrawer.tsx) — `PATCH /api/alerts/{id}`, `POST /api/devices/{id}/quarantine`. |
| Header | [`frontend/components/layout/Header.tsx`](../frontend/components/layout/Header.tsx) — Priority alerts from `useAlerts()` (live list). |
| Alerts page | [`frontend/app/alerts/page.tsx`](../frontend/app/alerts/page.tsx) — Uses `useAlertsContext()` for loading/error. |
| Audit | [`frontend/app/audit/page.tsx`](../frontend/app/audit/page.tsx) — “Verify chain” → `GET /api/audit/verify`; log preview → `GET /api/audit/logs` (**Hunain** — see [`FAHEEM_BACKEND_TODO.md`](./FAHEEM_BACKEND_TODO.md) §2). |

### Caveats

- **Next.js route** [`frontend/app/api/events/route.ts`](../frontend/app/api/events/route.ts) — **Not used** by the updated client: alert SSE targets **port 8000**.
- **`/api/fl-events`**, **`GET /api/fl/clients`**, **`GET /api/incidents`** — required for **full** FL/incident UX; **Hunain** per split. URLs use `NEXT_PUBLIC_API_URL` (see **§ Cross-team dependencies** above and **§2** in [`FAHEEM_BACKEND_TODO.md`](./FAHEEM_BACKEND_TODO.md)).

---

## Full stack (local)

1. **Backend** — Uvicorn on **port 8000** (command above).
2. **Frontend** — Copy `frontend/.env.example` → `frontend/.env.local`, set `NEXT_PUBLIC_API_URL=http://localhost:8000`, then:

   ```bash
   cd frontend && npm install && npm run dev
   ```

---

## Related docs

- [`FAHEEM_GAP_REMEDIATION_LOG.md`](./FAHEEM_GAP_REMEDIATION_LOG.md) — File-level change log for monorepo route extensions, pytest/live SSE, and frontend fetch aborts.
- [`FAHEEM_BACKEND_TODO.md`](./FAHEEM_BACKEND_TODO.md) — Cross-team dependencies (**§2**), decisions, pending UI validation, gaps vs plan, mutually decided follow-ups.
- [`BACKEND_PRD.md`](./BACKEND_PRD.md) — Full API specification.
- [`API_ENDPOINTS_IMPLEMENTATION_SPLIT.md`](./API_ENDPOINTS_IMPLEMENTATION_SPLIT.md) — Endpoint ownership and difficulty split.

---

*Last documented from the Faheem implementation plan execution (in-memory phase, stub auth, FastAPI + Next.js integration).*
