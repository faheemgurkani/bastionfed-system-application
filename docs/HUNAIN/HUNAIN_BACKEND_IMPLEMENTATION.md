# Hunain Backend Implementation — Status & Runbook

> **Runtime source of truth:** `backend/` (unified FastAPI). This document describes Hunain’s **12 assigned endpoints**. See [LOCAL_TESTING.md](../LOCAL_TESTING.md) for running the unified stack.

**Scope (phase 1):** FastAPI service with **in-memory** product state, seeded mock data, **stub auth** (no Firebase Admin verification yet), and a completed **BastionBot Ask Mode** backed by **SQLite** for per-user conversations and memory.

---

## Implemented endpoints (Hunain)

| Difficulty | Method | Path |
|------------|--------|------|
| Easy | GET | `/api/alerts/{alert_id}` |
| Easy | GET | `/api/incidents` |
| Easy | GET | `/api/fl/rounds` |
| Easy | GET | `/api/fl/clients` |
| Easy | GET | `/api/forensics/samples/{sample_id}` |
| Easy | GET | `/api/bastionbot/conversations` |
| Easy | GET | `/api/bastionbot/conversations/{conversation_id}` |
| Medium | POST | `/api/alerts/{alert_id}/escalate` |
| Medium | GET | `/api/audit/logs` |
| Medium | POST | `/api/incidents/{incident_id}/playbook/run` |
| Hard | GET | `/api/fl-events` (SSE) |
| Hard | POST | `/api/bastionbot/chat` |
| Hard | POST | `/api/fl/models/{model_name}/activate` |

Additional non-contract route:
- `GET /health`

---

## Backend structure (`backend/hunain_implementation/`)

- **Entry app:** `app/main.py` (lifespan reset + router mounting under `/api`)
- **Routers:** `app/routers/alerts.py`, `incidents.py`, `fl.py`, `forensics.py`, `auth.py`, `audit.py`, `events.py`, `bastionbot.py`
- **BastionBot modules:** `app/bastionbot/storage.py`, `knowledge.py`, `engine.py`
- **Data/state:** `app/store/memory.py` + `app/store/seed_data.py`
- **Models:** `app/models/domain.py`, `app/models/api.py`
- **Auth deps:** `app/auth/deps.py` (`require_read_auth`, `require_user`, `require_sse_auth`, `require_bastionbot_user`)
- **Errors:** `app/errors.py` (`api_error` envelope)

---

## Endpoint behavior highlights

- `POST /api/alerts/{id}/escalate` creates a new incident and marks alert as `IN_REVIEW` side-effect.
- `POST /api/incidents/{id}/playbook/run` marks first pending step as `RUNNING` and appends audit entry.
- `POST /api/fl/models/{model}/activate` switches active model and writes `MODEL_UPDATED` audit entry.
- `POST /api/bastionbot/chat` creates or continues a **signed-in analyst** conversation, stores user + bot messages in **SQLite**, retrieves grounded sources from docs/code metadata/live state, and appends audit activity.
- `GET /api/bastionbot/conversations/{conversation_id}` returns the full history only for the owning user.
- `GET /api/fl-events` streams FL client patch payloads over SSE (`text/event-stream`).
- `GET /api/audit/logs` supports filters + cursor pagination.

---

## Testing status

- Test file: `backend/hunain_implementation/tests/test_hunain_endpoints.py`
- Current automated result: **31 passed, 1 skipped**
- Coverage includes:
  - OpenAPI assigned-path validation
  - Read endpoint auth + shape checks
  - Mutation auth gating
  - 404/validation branches
  - Pagination/filter checks (`incidents`, `audit/logs`)
  - Mutation side effects (`escalate`, `playbook/run`, model activate, chat)

---

## Run locally

```bash
cd backend/hunain_implementation
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

---

## Related docs

- [`../BLUE_TEAM_APPLICATION_SPEC.md`](../BLUE_TEAM_APPLICATION_SPEC.md) — claims vs implementation for security / blue-team review (includes recent FL health & metrics changes)
- [`HUNAIN_BACKEND_TODO.md`](./HUNAIN_BACKEND_TODO.md)
- [`HUNAIN_LOCAL_TESTING.md`](./HUNAIN_LOCAL_TESTING.md)
- [`../BASTIONBOT_ASK_MODE.md`](../BASTIONBOT_ASK_MODE.md)
- [`../BACKEND_PRD.md`](../BACKEND_PRD.md)
- [`../API_ENDPOINTS_IMPLEMENTATION_SPLIT.md`](../API_ENDPOINTS_IMPLEMENTATION_SPLIT.md)
