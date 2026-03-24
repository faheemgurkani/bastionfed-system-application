# Hammad Backend Implementation — Status & Runbook

This document describes what was implemented for **Hammad’s 12 endpoints** per [`API_ENDPOINTS_IMPLEMENTATION_SPLIT.md`](../API_ENDPOINTS_IMPLEMENTATION_SPLIT.md) and contracts in [`BACKEND_PRD.md`](../BACKEND_PRD.md).

**Scope (phase 1):** FastAPI service with in-memory state, seeded mock data, and stub auth.

---

## Implemented endpoints (Hammad)

| Difficulty | Method | Path |
|------------|--------|------|
| Easy | GET | `/api/devices` |
| Easy | GET | `/api/devices/{device_id}` |
| Easy | GET | `/api/fl/drift` |
| Easy | GET | `/api/fl/models` |
| Easy | GET | `/api/forensics/rca` |
| Easy | GET | `/api/bastionbot/conversations/{conversation_id}` |
| Medium | PATCH | `/api/incidents/{incident_id}` |
| Medium | PATCH | `/api/incidents/{incident_id}/playbook/steps/{step_id}` |
| Medium | POST | `/api/incidents/{incident_id}/playbook/halt` |
| Hard | POST | `/api/forensics/samples` |
| Hard | POST | `/api/forensics/rca` |
| Hard | POST | `/api/network/block-ip` |

Additional non-contract route:
- `GET /health`

---

## Backend structure (`backend/hammad_implementation/`)

- **Entry app:** `app/main.py` (lifespan reset + router mounting under `/api`)
- **Routers:** `devices.py`, `fl.py`, `forensics.py`, `incidents.py`, `auth.py`
- **State/data:** `app/store/memory.py` + `app/store/seed_data.py`
- **Models:** `app/models/domain.py`, `app/models/api.py`
- **Auth deps:** `app/auth/deps.py`

---

## Endpoint behavior highlights

- `GET /api/devices` supports `wing`, `status`, `type` filtering.
- `GET /api/fl/drift` returns per-client drift rows for FL monitoring table.
- `GET /api/fl/models` returns model zoo with exactly one active model.
- `PATCH /api/incidents/{id}` updates status/assignee and appends timeline + audit entry.
- `PATCH /playbook/steps/{step_id}` updates a step and can auto-resolve incident when all steps completed.
- `POST /playbook/halt` halts running step and writes audit entry.
- `POST /api/forensics/samples` accepts multipart upload and creates pending sample record.
- `POST /api/forensics/rca` generates RCA from incident data and appends audit entry.
- `POST /api/network/block-ip` returns firewall rule metadata (`ruleId`, `appliedAt`) and logs audit action.

---

## Testing status

- Test file: `backend/hammad_implementation/tests/test_hammad_endpoints.py`
- Current automated result: **23 passed**
- Runtime smoke validation: all **12/12 endpoints** manually verified as passing.

---

## Run locally

```bash
cd backend/hammad_implementation
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

---

## Related docs

- [`HAMMAD_BACKEND_TODO.md`](./HAMMAD_BACKEND_TODO.md)
- [`HAMMAD_LOCAL_TESTING.md`](./HAMMAD_LOCAL_TESTING.md)
- [`../BACKEND_PRD.md`](../BACKEND_PRD.md)
- [`../API_ENDPOINTS_IMPLEMENTATION_SPLIT.md`](../API_ENDPOINTS_IMPLEMENTATION_SPLIT.md)
