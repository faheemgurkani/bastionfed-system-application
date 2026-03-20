# Faheem backend — decisions, TODOs, and gaps

This document captures **implementation decisions** already in place for [`backend/`](../backend/), **pending work** (including UI validation), **gaps vs the Faheem-scope plan**, and **topics to decide together** before a production-grade stack.

**References**

- What is built: [`FAHEEM_BACKEND_IMPLEMENTATION.md`](./FAHEEM_BACKEND_IMPLEMENTATION.md)
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

## 2. TODO — pending validation from the UI (dev stack)

These require **both servers running** (backend + frontend), as in [`FAHEEM_LOCAL_TESTING.md`](./FAHEEM_LOCAL_TESTING.md).

- [ ] **End-to-end smoke:** With `uvicorn` on **:8000** and `npm run dev` on **:3000**, sign in or use **Continue as guest** and confirm pages load without console/network errors for Faheem-backed flows.
- [ ] **Alerts:** List loads from API; live events appear via SSE; drawer actions (status PATCH, quarantine) behave as expected for a signed-in user (guest cannot mutate).
- [ ] **Dashboard:** KPI cards reflect `GET /api/dashboard/kpis` (not only local mock math).
- [ ] **FL Health:** Banner reflects `GET /api/fl/status`; client detail popover refreshes from `GET /api/fl/clients/{id}` (**note:** live FL grid patches still use Next **`/api/fl-events`** until FastAPI implements that endpoint — not Faheem’s assignment).
- [ ] **Forensics:** Sample list from `GET /api/forensics/samples`; select rows and confirm analysis view.
- [ ] **Incidents:** Open a card; confirm detail refresh from `GET /api/incidents/{id}`.
- [ ] **Auth:** After Google sign-in, confirm `POST /api/auth/session` succeeds when the backend is up (check network tab; failures are logged if API is down).
- [ ] **Audit:** Run **Verify chain** and confirm result text matches `GET /api/audit/verify` (**note:** audit **table** may still be mock data if not yet wired to `GET /api/audit/logs` — outside Faheem’s 12 endpoints).

---

## 3. Gaps vs Faheem plan scope (backend + wired frontend)

Items below are **relative to** the bastionfed-faheem-backend plan **for Faheem’s 12 endpoints only**. They are not a full product backlog.

### 3.1 PRD / plan fidelity (still simplified or stubbed)

- [ ] **Firebase Admin SDK:** Tokens are **not** verified; any non-empty `Authorization: Bearer` is treated as authenticated for mutations. **Gap vs PRD** — replace stub with real verification and stable `uid`/claims for audit `actor`.
- [ ] **SSE /events:** PRD describes **Redis pub/sub** and inference pushing alerts; current implementation emits **synthetic** alerts from in-memory seed data on a **short tick** (configurable in code), not Redis.
- [ ] **Quarantine:** No real edge agent, queue, or async acknowledgement; device is set **ISOLATED** in memory and incidents get a timeline event — **gap vs PRD** “dispatch to edge agent”.
- [ ] **Error envelope:** Dedicated helpers exist for many routes; **FastAPI/Pydantic 422** validation responses may **not** always match the `{ "detail", "code" }` pattern everywhere — worth normalizing if required for the frontend.
- [ ] **GET /api/alerts — `tactic` filter:** Supported in store/router if passed; confirm parity with all PRD sort keys and edge cases in manual QA.

### 3.2 Frontend (within Faheem wiring — known caveats)

- [ ] **`/api/fl-events`:** Still served by **Next.js**, not FastAPI — plan explicitly left this for another owner / later FastAPI route.
- [ ] **RCA in UI:** Plan mentioned fetching **`GET /api/forensics/rca/{rca_id}`** where a detail viewer exists; confirm whether any screen still needs that wire-up (Faheem endpoint exists on the backend).
- [ ] **Optional Next routes:** [`frontend/app/api/events/route.ts`](../frontend/app/api/events/route.ts) is **unused** by the new alert SSE client path; can be removed or kept for legacy — team choice.

### 3.3 Testing

- [ ] **Automated tests** cover many paths via `TestClient` (see [`backend/tests/test_faheem_endpoints.py`](../backend/tests/test_faheem_endpoints.py)); **SSE body is not fully consumed** in tests (infinite stream). Optional: add a separate integration job hitting a short-lived `uvicorn` with `httpx` stream timeout.
- [ ] **Manual / UI test checklist** in §2 is **pending** until someone runs both dev servers.

---

## 4. Mutually to be decided (beyond Faheem phase 1)

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

## 5. Suggested order of next steps

1. Complete **§2 UI validation** with both dev servers.
2. File issues for **§3** items that block demo or production.
3. Schedule a short session to lock **§4** (especially DB + Redis + real Firebase auth) before the next implementation milestone.

---

*Document version: aligns with Faheem in-memory implementation and frontend wiring as described in [`FAHEEM_BACKEND_IMPLEMENTATION.md`](./FAHEEM_BACKEND_IMPLEMENTATION.md).*
