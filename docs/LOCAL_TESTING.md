# Local testing — unified backend + frontend

Run from the repo root unless noted.

## Prerequisites

- Python 3.11+
- Node.js 18+

---

## 1. Backend: venv, pytest, dev server

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the unified test suite (in-memory demo mode; no external services required):

```bash
.venv/bin/python -m pytest -q
```

Start the API (recommended reload watcher):

```bash
.venv/bin/python dev_server.py
```

API base: **http://localhost:8000** · OpenAPI: **http://localhost:8000/docs**

Optional live HTTP integration (requires a running server):

```bash
export LIVE_SERVER_URL=http://127.0.0.1:8000
.venv/bin/python -m pytest tests/test_live_server.py -q
```

Data-plane live tests (`test_supabase_live.py`, `test_upstash_redis_live.py`, `test_real_data_plane.py`) require matching env vars in `backend/.env` — skip for local-only work.

---

## 2. Frontend

```bash
cd frontend
cp .env.example .env.local   # or obtain .env.local from the frontend lead
# Ensure: NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

App: **http://localhost:3000**

---

## 3. Manual smoke checks

With both servers running:

| Check | Command / action |
|-------|------------------|
| Health | `curl -s http://localhost:8000/health` |
| Alerts (guest) | `curl -s 'http://localhost:8000/api/alerts?guest=true' \| head -c 400` |
| KPIs | `curl -s 'http://localhost:8000/api/dashboard/kpis?guest=true'` |
| SSE alerts | `curl -N --max-time 3 'http://localhost:8000/api/events?guest=true'` |
| Browser | Sign in or **Continue in dev mode** (`DEMO_MODE=1` on backend); open Dashboard, Alerts, FL Health, Incidents, Forensics, Audit, BastionBot |

---

## 4. Standalone contributor backends (optional)

For isolated route testing only — not required for normal development:

| Fork | Directory | Tests |
|------|-----------|-------|
| Faheem | `backend/faheem_implementation/` | `pytest` from that directory |
| Hunain | `backend/hunain_implementation/` | `pytest -q` |
| Hammad | `backend/hammad_implementation/` | `pytest -q` |

See contributor implementation docs under `docs/FAHEEM/`, `docs/HUNAIN/`, `docs/HAMMAD/`.

---

## Related

- [SETUP_GUIDE.md](../SETUP_GUIDE.md)
- [backend/README.md](../backend/README.md)
- [DATA_PLANE_VERIFICATION.md](./DATA_PLANE_VERIFICATION.md)
