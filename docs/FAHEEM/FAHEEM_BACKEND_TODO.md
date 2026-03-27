# Faheem backend — decisions, TODOs, and gaps

This document captures **implementation decisions** already in place for **`backend/faheem_implementation/`** ([`../backend/faheem_implementation/`](../backend/faheem_implementation/)), **cross-team API dependencies** (**§2**), **pending work** (including UI validation), **gaps vs the Faheem-scope plan**, and **topics to decide together** before a production-grade stack.

**References**

- What is built: [`FAHEEM_BACKEND_IMPLEMENTATION.md`](./FAHEEM_BACKEND_IMPLEMENTATION.md)
- **Change log (gaps fixed: routes, pytest/live TCP, SSE tests, frontend abort, docs):** [`FAHEEM_GAP_REMEDIATION_LOG.md`](./FAHEEM_GAP_REMEDIATION_LOG.md)
- How to run tests and dev servers: [`FAHEEM_LOCAL_TESTING.md`](./FAHEEM_LOCAL_TESTING.md)
- Full API contract: [`BACKEND_PRD.md`](./BACKEND_PRD.md)
- Faheem’s 12 endpoints (split): [`API_ENDPOINTS_IMPLEMENTATION_SPLIT.md`](./API_ENDPOINTS_IMPLEMENTATION_SPLIT.md) (lines 65–83)
- Original implementation plan: `.cursor/plans/bastionfed-faheem-backend_8c81d383.plan.md` (local Cursor plan; not shipped in repo)

---

## 1. Decisions in effect (as agreed during implementation)

| Topic | Decision | Status |
|-------|-----------|--------|
| **Persistence & integrations (phase 1)** | **In-memory first:** all Faheem endpoints are backed by in-memory `AppState`, seeded from the same shape as [`frontend/lib/mock-data.ts`](../frontend/lib/mock-data.ts). **No** PostgreSQL, Redis, S3, real firewall/FL aggregator, or Firebase Admin verification in this phase. Code is structured so storage/auth can be swapped later **without changing public route paths or JSON contracts**. | **In place** |
| **Frontend integration** | **Wire Next.js to FastAPI:** the app uses `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`) via [`frontend/lib/api.ts`](../frontend/lib/api.ts). Alerts use **`GET /api/alerts`** and **`EventSource`** against FastAPI **`/api/events`** with `?guest=true` or `?token=…` (not the Next `/api/events` route for that flow). | **In place** |

---

## 2. Cross-team dependencies (why Faheem’s UX needs other owners’ endpoints)

Faheem’s **contract split** is still **12** routes in [`API_ENDPOINTS_IMPLEMENTATION_SPLIT.md`](../API_ENDPOINTS_IMPLEMENTATION_SPLIT.md). The **`faheem_implementation`** app extends that for **single-process dev**: list + FL SSE routes (below) share the same in-memory store. Nothing calls *remote* Hunain/Hammad servers (phase 1).

**Long-term owner** for the extra three paths remains **Hunain** in the split doc; **`faheem_implementation`** carries **working copies** until the team merges one backend.

Other routes (**`GET /api/audit/logs`**, BastionBot, playbook mutations, …) remain **Hunain**/**Hammad** elsewhere in the PRD.

### 2.1 Dependency table (UI → endpoint → owner)

| User-visible flow | HTTP route | Split-doc owner | Notes |
|-------------------|------------|-----------------|--------|
| **Incidents Kanban** | `GET /api/incidents` | **Hunain** | **Implemented** in [`faheem_implementation`](../backend/faheem_implementation/) for dev; PRD §6.1 shape (`items`, `nextCursor`, `total`). |
| **FL ClientGrid seed** | `GET /api/fl/clients` | **Hunain** | **Implemented** in `faheem_implementation`; PRD §8.3 `{ clients }`. Works with `GET /api/fl/clients/{id}` popover. |
| **FL live patches** | `GET /api/fl-events` | **Hunain** | **Implemented** in `faheem_implementation` (synthetic SSE, same pattern as `/api/events`). Client URL: [`flEventsSourceUrl`](../frontend/lib/api.ts) → `NEXT_PUBLIC_API_URL`. |
| **Audit table** | `GET /api/audit/logs` | **Hunain** | **Not** in Faheem’s app; verify-chain (**Faheem**) can pass while table still errors. |

**Self-contained on Faheem’s FastAPI today** (typical manual QA): alerts (+ SSE), incidents list + detail, FL status + clients list + detail + FL SSE, forensics samples/RCA, dashboard KPIs, auth session, devices quarantine, audit verify.

### 2.2 Requirements for implementers (merged backend / contract parity)

When **combining** Faheem’s app with Hunain’s and Hammad’s routers into **one** FastAPI process (recommended for local dev and production):

1. **One origin:** All `apiFetchJson` and SSE helpers that use [`apiUrl`](../frontend/lib/api.ts) must resolve to a service that mounts **every** route the UI calls (Faheem + Hunain + Hammad), unless you deliberately introduce path-based proxies.
2. **Guest vs Bearer:** Match Faheem’s pattern: read-only `GET`s allow `?guest=true` or `Authorization: Bearer …`; mutations require Bearer (see [`FAHEEM_BACKEND_IMPLEMENTATION.md`](./FAHEEM_BACKEND_IMPLEMENTATION.md)).
3. **Shared IDs and seed shape:** List and detail endpoints must agree on **`incident_id`**, **`client_id`**, **`device_id`**, etc. The phase-1 expectation is alignment with [`frontend/lib/mock-data.ts`](../frontend/lib/mock-data.ts) until a real database is the source of truth.
4. **FL SSE + list:** `GET /api/fl/clients` seed and `GET /api/fl-events` patches must describe the **same** client IDs so the UI’s `Object.assign` merge behaves correctly.
5. **Audit:** `GET /api/audit/logs` entries should be the same chain **`GET /api/audit/verify`** walks (Faheem’s verify is authoritative for tamper detection once merged).

### 2.3 Product features outside Faheem’s 12 (Hammad and remaining Hunain)

Incident **playbook** actions, **halt/run**, **escalate alert**, **block IP**, **forensics upload / RCA generate**, **BastionBot chat**, **`GET /api/alerts/{id}`** (single-alert refresh), **`GET /api/forensics/samples/{sample_id}`**, etc., are assigned to **Hunain** or **Hammad** in [`API_ENDPOINTS_IMPLEMENTATION_SPLIT.md`](../API_ENDPOINTS_IMPLEMENTATION_SPLIT.md). They are not required for Faheem’s pytest suite but block full **PRD** coverage and some buttons elsewhere in the app.

**Implementation path:** [`backend/faheem_implementation/`](../backend/faheem_implementation/) (tests: `pytest` from that directory). Paths in older sentences in this repo may say `backend/`; treat **`faheem_implementation`** as the Faheem FastAPI root.

---

## 3. TODO — pending validation from the UI (dev stack)

These require **both servers running** (backend + frontend), as in [`FAHEEM_LOCAL_TESTING.md`](./FAHEEM_LOCAL_TESTING.md).

- [ ] **End-to-end smoke:** With `uvicorn` on **:8000** and `npm run dev` on **:3000**, sign in or use **Continue as guest** and confirm pages load without console/network errors for Faheem-backed flows.
- [ ] **Alerts:** List loads from API; live events appear via SSE; drawer actions (status PATCH, quarantine) behave as expected for a signed-in user (guest cannot mutate).
- [ ] **Dashboard:** KPI cards reflect `GET /api/dashboard/kpis` (not only local mock math).
- [ ] **FL Health:** Banner reflects `GET /api/fl/status`; client detail popover refreshes from `GET /api/fl/clients/{id}`. **Live grid SSE** uses `GET /api/fl-events` on `NEXT_PUBLIC_API_URL` (**Hunain**); see **§2**.
- [ ] **Forensics:** Sample list from `GET /api/forensics/samples`; select rows and confirm analysis view.
- [ ] **Incidents:** Kanban list from **`GET /api/incidents`** (Hunain) if using merged API; open a card and confirm detail refresh from Faheem’s **`GET /api/incidents/{id}`**.
- [ ] **Auth:** After Google sign-in, confirm `POST /api/auth/session` succeeds when the backend is up (check network tab; failures are logged if API is down).
- [ ] **Audit:** Run **Verify chain** and confirm result text matches Faheem’s `GET /api/audit/verify`. **Table rows** need Hunain’s `GET /api/audit/logs` on the same host — see **§2**.

---

## 4. Gaps vs Faheem plan scope (backend + wired frontend)

Items below are **relative to** the bastionfed-faheem-backend plan **for Faheem’s 12 endpoints only**. They are not a full product backlog.

### 4.1 PRD / plan fidelity (still simplified or stubbed)

- [ ] **Firebase Admin SDK:** Tokens are **not** verified; any non-empty `Authorization: Bearer` is treated as authenticated for mutations. **Gap vs PRD** — replace stub with real verification and stable `uid`/claims for audit `actor`.
- [ ] **SSE /events:** PRD describes **Redis pub/sub** and inference pushing alerts; current implementation emits **synthetic** alerts from in-memory seed data on a **short tick** (configurable in code), not Redis.
- [ ] **Quarantine:** No real edge agent, queue, or async acknowledgement; device is set **ISOLATED** in memory and incidents get a timeline event — **gap vs PRD** “dispatch to edge agent”.
- [ ] **Error envelope:** Dedicated helpers exist for many routes; **FastAPI/Pydantic 422** validation responses may **not** always match the `{ "detail", "code" }` pattern everywhere — worth normalizing if required for the frontend.
- [ ] **GET /api/alerts — `tactic` filter:** Supported in store/router if passed; confirm parity with all PRD sort keys and edge cases in manual QA.

### 4.2 Frontend (within Faheem wiring — known caveats)

- [ ] **`/api/fl-events`:** **Hunain** on FastAPI when using `NEXT_PUBLIC_API_URL`; repo also has a **Next.js** route that the current client does not use for this URL — see **§2**.
- [ ] **RCA in UI:** Plan mentioned fetching **`GET /api/forensics/rca/{rca_id}`** where a detail viewer exists; confirm whether any screen still needs that wire-up (Faheem endpoint exists on the backend).
- [ ] **Optional Next routes:** [`frontend/app/api/events/route.ts`](../frontend/app/api/events/route.ts) is **unused** by the new alert SSE client path; can be removed or kept for legacy — team choice.

### 4.3 Testing

- [ ] **Automated tests** cover many paths via `TestClient` (see [`backend/faheem_implementation/tests/test_faheem_endpoints.py`](../backend/faheem_implementation/tests/test_faheem_endpoints.py)); **SSE body is not fully consumed** in tests (infinite stream). Optional: add a separate integration job hitting a short-lived `uvicorn` with `httpx` stream timeout.
- [ ] **Manual / UI test checklist** in **§3** is **pending** until someone runs both dev servers (or a merged API per **§2**).

---

## 5. Mutually to be decided (beyond Faheem phase 1)

These are called out in [`BACKEND_PRD.md`](./BACKEND_PRD.md) but **not** implemented in the in-memory phase. Stakeholders should align before implementation work:

| Area | Examples to decide |
|------|---------------------|
| **Database** | PostgreSQL vs Timescale for time-series; schema/migrations (SQLAlchemy/Alembic async); what is source of truth vs Firestore for user profiles. |
| **Redis** | SSE channels for `/api/events` (and later `/api/fl-events`); session cache as in PRD env vars. |
| **Auth** | Firebase Admin SDK setup (`FIREBASE_SERVICE_ACCOUNT_KEY_*`); guest vs signed-in rules in production; service-to-service auth if any. |
| **Object storage** | S3-compatible uploads for `POST /api/forensics/samples` (multipart) — buckets, keys, malware handling policy. |
| **External APIs** | FL aggregator URL/key; firewall API for `POST /api/network/block-ip`; any ticketing integration for incidents. |
| **Hosting & env** | `ALLOWED_ORIGINS`, TLS, secrets management, logging/metrics, backup of DB and audit append-only store. |
| **Frontend** | Production `NEXT_PUBLIC_API_URL`; whether to proxy `/api/*` through Next for same-origin cookies/CORS simplification. |

---

## 6. Suggested order of next steps

1. Complete **§3 UI validation** with both dev servers (or a **merged** FastAPI that satisfies **§2**).
2. File issues for **§4** items that block demo or production.
3. Schedule a short session to lock **§5** (especially DB + Redis + real Firebase auth) before the next implementation milestone.

---

*Document version: aligns with Faheem in-memory implementation and frontend wiring as described in [`FAHEEM_BACKEND_IMPLEMENTATION.md`](./FAHEEM_BACKEND_IMPLEMENTATION.md).*
