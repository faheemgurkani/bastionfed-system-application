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

Full API contracts remain defined in [`BACKEND_PRD.md`](./BACKEND_PRD.md).

---

## Backend (`backend/`)

### Application entry

- **[`backend/app/main.py`](../backend/app/main.py)** — FastAPI app, CORS from `ALLOWED_ORIGINS` ([`backend/app/config.py`](../backend/app/config.py)), **lifespan** runs **`state.reset()`** on startup, mounts routers under `/api`, exposes `/health`.

### Data layer

- **[`backend/app/store/memory.py`](../backend/app/store/memory.py)** — **`AppState`**: in-memory lists/dicts for alerts, incidents, devices, FL rounds/clients, malware samples, RCA reports, audit logs, users.
- **[`backend/app/store/seed_data.py`](../backend/app/store/seed_data.py)** — Seed snapshots aligned with frontend mocks (`MOCK_DEVICES`, alerts, incidents, FL, forensics, RCA, etc.).

### Audit integrity

- Append-only audit rows with a **SHA-256 hash chain** (previous hash + timestamp + actor + action + target + result).
- **`GET /api/audit/verify`** — Recomputes the chain; returns `{ valid, totalLogs, checkedAt }` or, on failure, `{ valid: false, firstBreakAt, totalLogs, checkedAt }`.
- Automated tests include a **tampered chain** scenario.

### Authentication (stub)

- **[`backend/app/auth/deps.py`](../backend/app/auth/deps.py)**:
  - **GET** (non-SSE): `Authorization: Bearer <token>` **or** `?guest=true`.
  - **SSE** `/api/events`: `?token=<firebase_id_token>` **or** `?guest=true` (per PRD / `EventSource` constraints).
  - **Mutations** (PATCH/POST): require **Bearer**; **guest** receives **403** on those routes.
  - No call to Firebase Admin SDK yet; bearer presence is treated as an authenticated user for `actor` / dependency wiring.

### Server-Sent Events

- **`GET /api/events`** — `text/event-stream`; comment pings **`: keep-alive`**, periodic **`data: <Alert JSON>`** lines built from **`state.next_streaming_alert()`** (synthetic new ids/timestamps; no historical replay on connect per PRD intent).
- Event interval is a **short tick** in code for responsiveness; adjust in [`backend/app/routers/events.py`](../backend/app/routers/events.py) if you need production-like spacing.

### Routers (by file)

| Area | Module |
|------|--------|
| Alerts | [`backend/app/routers/alerts.py`](../backend/app/routers/alerts.py) |
| Incidents | [`backend/app/routers/incidents.py`](../backend/app/routers/incidents.py) |
| FL | [`backend/app/routers/fl.py`](../backend/app/routers/fl.py) |
| Forensics | [`backend/app/routers/forensics.py`](../backend/app/routers/forensics.py) |
| Devices | [`backend/app/routers/devices.py`](../backend/app/routers/devices.py) |
| Audit | [`backend/app/routers/audit.py`](../backend/app/routers/audit.py) |
| Auth | [`backend/app/routers/auth.py`](../backend/app/routers/auth.py) |
| Dashboard | [`backend/app/routers/dashboard.py`](../backend/app/routers/dashboard.py) |
| SSE | [`backend/app/routers/events.py`](../backend/app/routers/events.py) |

### Domain models

- **[`backend/app/models/domain.py`](../backend/app/models/domain.py)** — PRD-aligned Pydantic models (camelCase JSON via alias generator).
- **[`backend/app/models/api.py`](../backend/app/models/api.py)** — List/session/KPI helper schemas where useful.

### Tests

- **[`backend/tests/test_faheem_endpoints.py`](../backend/tests/test_faheem_endpoints.py)** — OpenAPI path checks; alerts filters / pagination / sort; PATCH **404** / **400** / auth errors; incidents, FL, forensics, RCA **404**s; KPI shape; auth session **401**/**403**; quarantine **404** + incident timeline side effect; audit verify + tamper; SSE **401** only (stream body not asserted in pytest—use **`curl`** / browser; see [`FAHEEM_LOCAL_TESTING.md`](./FAHEEM_LOCAL_TESTING.md)).
- **[`backend/pytest.ini`](../backend/pytest.ini)** — `pythonpath = .` for `app` imports.
- **Query params:** `GET /api/alerts` uses PRD names **`status`**, **`from`**, **`to`** (via FastAPI aliases). `GET /api/forensics/samples` uses **`status`** for sample status.

Run tests:

```bash
cd backend && source .venv/bin/activate && pytest tests/test_faheem_endpoints.py -q
```

**Step-by-step local stack + fuller test description:** see [`FAHEEM_LOCAL_TESTING.md`](./FAHEEM_LOCAL_TESTING.md).

### Run backend (development)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

See also [`backend/README.md`](../backend/README.md).

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
| Audit | [`frontend/app/audit/page.tsx`](../frontend/app/audit/page.tsx) — “Verify chain” → `GET /api/audit/verify`. |

### Caveats

- **Next.js route** [`frontend/app/api/events/route.ts`](../frontend/app/api/events/route.ts) — **Not used** by the updated client: alert SSE targets **port 8000**.
- **`/api/fl-events`** — [`frontend/contexts/fl-clients-context.tsx`](../frontend/contexts/fl-clients-context.tsx) still uses the **Next** handler until **`GET /api/fl-events`** exists on FastAPI (assigned elsewhere in the split).

---

## Full stack (local)

1. **Backend** — Uvicorn on **port 8000** (command above).
2. **Frontend** — Copy `frontend/.env.example` → `frontend/.env.local`, set `NEXT_PUBLIC_API_URL=http://localhost:8000`, then:

   ```bash
   cd frontend && npm install && npm run dev
   ```

---

## Related docs

- [`FAHEEM_BACKEND_TODO.md`](./FAHEEM_BACKEND_TODO.md) — Decisions, pending UI validation, gaps vs plan, mutually decided follow-ups.
- [`BACKEND_PRD.md`](./BACKEND_PRD.md) — Full API specification.
- [`API_ENDPOINTS_IMPLEMENTATION_SPLIT.md`](./API_ENDPOINTS_IMPLEMENTATION_SPLIT.md) — Endpoint ownership and difficulty split.

---

*Last documented from the Faheem implementation plan execution (in-memory phase, stub auth, FastAPI + Next.js integration).*
