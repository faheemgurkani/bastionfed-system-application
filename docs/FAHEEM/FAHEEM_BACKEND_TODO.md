# Faheem backend — decisions, TODOs, and gaps

> **Runtime source of truth:** `backend/` (unified FastAPI). This document tracks Faheem’s original 12-endpoint scope and UI ownership. The standalone fork at `backend/faheem_implementation/` remains for isolated pytest only.

**References:** [FAHEEM_BACKEND_IMPLEMENTATION.md](./FAHEEM_BACKEND_IMPLEMENTATION.md) · [API split](../API_ENDPOINTS_IMPLEMENTATION_SPLIT.md) · [BACKEND_PRD.md](../BACKEND_PRD.md) · [LOCAL_TESTING.md](../LOCAL_TESTING.md)

---

## 1. Current state (unified backend)

| Topic | Status |
|-------|--------|
| **Default API** | All 36 routes run from `backend/` on port 8000 |
| **Frontend** | `NEXT_PUBLIC_API_URL` → unified backend via `frontend/lib/api.ts` |
| **Auth** | Firebase JWT verification on API (`app/auth/firebase.py`); demo tenant when `DEMO_MODE=1` |
| **Persistence** | Supabase Postgres + Redis + Storage when configured; in-memory/SQLite fallback for local demo |
| **Seed data** | `backend/app/store/seed_data.py` (aligned with frontend types) |

Faheem’s assigned routes (alerts, incidents detail, FL status/client detail, forensics reads, dashboard KPIs, auth session, `/api/events` SSE, quarantine, audit verify) live in `backend/app/routers/`.

---

## 2. Cross-team UI dependencies

The Next.js app expects **one** API origin. Routes outside Faheem’s 12-endpoint split (incident list, FL list/SSE, audit logs, devices, playbook, BastionBot chat, etc.) are implemented in the unified `backend/app/routers/` tree — see [API_ENDPOINTS_IMPLEMENTATION_SPLIT.md](../API_ENDPOINTS_IMPLEMENTATION_SPLIT.md).

---

## 3. Active work (see also [TODO.md](../TODO.md))

- Data plane: provision and verify per [FIREBASE_DATA_PLANE_MAPPING.md](../FIREBASE_DATA_PLANE_MAPPING.md)
- Feature catalog vs reality: [BLUE_TEAM_APPLICATION_SPEC.md](../BLUE_TEAM_APPLICATION_SPEC.md)
- FL orchestration and ingest UX gaps
- Production auth/RBAC hardening beyond demo mode

---

## 4. Historical note — standalone `faheem_implementation/`

During phase 1, Faheem’s fork temporarily included Hunain-owned list/SSE routes for single-process dev. Those conflicts were resolved when promoting to `backend/` — see [UNIFIED_BACKEND_CONFLICTS.md](../UNIFIED_BACKEND_CONFLICTS.md). Do not treat the standalone fork as the integration target.
