# Faheem backend — implementation status

> **Runtime source of truth:** `backend/` (unified FastAPI). This document describes Faheem’s **12 assigned endpoints** and the frontend surfaces they power. For running tests locally, see [LOCAL_TESTING.md](../LOCAL_TESTING.md).

**Scope:** Faheem’s routes per [API_ENDPOINTS_IMPLEMENTATION_SPLIT.md](../API_ENDPOINTS_IMPLEMENTATION_SPLIT.md) (lines 65–83). Full contracts: [BACKEND_PRD.md](../BACKEND_PRD.md).

---

## Assigned endpoints

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

Unified implementation: `backend/app/routers/` (`alerts.py`, `incidents.py`, `fl.py`, `forensics.py`, `devices.py`, `audit.py`, `auth.py`, `dashboard.py`, `events.py`).

---

## Frontend integration

| Feature | File | API |
|---------|------|-----|
| Alerts + SSE | `frontend/contexts/alerts-context.tsx` | `GET /api/alerts`, `GET /api/events` |
| Auth session | `frontend/contexts/auth-context.tsx` | `POST /api/auth/session` |
| Dashboard KPIs | `frontend/components/dashboard/KPICards.tsx` | `GET /api/dashboard/kpis` |
| FL banner / client | `frontend/components/fl-health/` | `GET /api/fl/status`, `GET /api/fl/clients/{id}` |
| Forensics | `frontend/app/forensics/page.tsx` | `GET /api/forensics/samples` |
| Incident detail | `frontend/components/incidents/IncidentDetail.tsx` | `GET /api/incidents/{id}` |
| Alert actions | `frontend/components/alerts/AlertDetailDrawer.tsx` | `PATCH /api/alerts/{id}`, quarantine |
| Audit verify | `frontend/app/audit/page.tsx` | `GET /api/audit/verify` |

API client: `frontend/lib/api.ts` (`NEXT_PUBLIC_API_URL`, default `http://localhost:8000`).

Screens that also call Hunain/Hammad routes (incident list, FL SSE, audit logs, etc.) require the **unified** backend — all routes are mounted in `backend/app/main.py`.

---

## Tests

**Unified (recommended):**

```bash
cd backend && .venv/bin/python -m pytest -q
```

**Standalone fork (Faheem scope only):**

```bash
cd backend/faheem_implementation && pytest tests/test_faheem_endpoints.py -q
```

---

## Related

- [FAHEEM_BACKEND_TODO.md](./FAHEEM_BACKEND_TODO.md) — active gaps and cross-team notes
- [UNIFIED_BACKEND_CONFLICTS.md](../UNIFIED_BACKEND_CONFLICTS.md) — SSE cadence merge decisions
- [backend/README.md](../../backend/README.md) — env vars and data plane
