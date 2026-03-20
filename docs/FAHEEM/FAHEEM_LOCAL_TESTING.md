# Local testing — Backend + Frontend + Pytest

Step-by-step commands for **macOS / Linux** from the repo root  
`personal/bastionfed-system-application/` (adjust the path if yours differs).

---

## Prerequisites

- **Python 3.11** (`python3.11 --version`)
- **Node.js** + npm (for the Next.js app)

---

## 1. Backend: venv, dependencies, automated tests

```bash
cd /Users/muhammadfaheem/Documents/GitHub/personal/bastionfed-system-application/backend
```

Create / refresh virtualenv (optional if `.venv` already exists):

```bash
rm -rf .venv
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Run **all Faheem API tests** (comprehensive suite in `tests/test_faheem_endpoints.py`):

```bash
pytest tests/test_faheem_endpoints.py -v
```

### Expected output when tests pass

You should see **33 collected** items (one file: `tests/test_faheem_endpoints.py`), **100% passed**, and a quick in-process runtime (often around **0.1–1s**). Example from a successful run (versions may differ slightly):

```text
============ test session starts =============
platform darwin -- Python 3.11.9, pytest-9.0.2, pluggy-1.6.0 -- .../backend/.venv/bin/python3.11
cachedir: .pytest_cache
rootdir: .../bastionfed-system-application/backend
configfile: pytest.ini
plugins: anyio-4.12.1
collected 33 items

tests/test_faheem_endpoints.py::test_health PASSED [  3%]
tests/test_faheem_endpoints.py::test_openapi_contains_faheem_paths PASSED [  6%]
# ... (remaining tests in the same file) ...
tests/test_faheem_endpoints.py::test_events_unauthenticated PASSED [100%]

============= 33 passed in 0.14s =============
```

If `collected` is not **33**, or any test **FAILED** / **ERROR**, fix the backend or test env before relying on the suite as green.

Quiet summary:

```bash
pytest tests/test_faheem_endpoints.py -q
```

---

## 2. Backend: run the API server

Still in `backend/` with venv activated:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Leave this terminal open. API base: **http://localhost:8000**  
Interactive docs: **http://localhost:8000/docs**

---

## 3. Frontend: env, install, dev server

Open a **new** terminal:

```bash
cd /Users/muhammadfaheem/Documents/GitHub/personal/bastionfed-system-application/frontend
```

If you don’t have `.env.local` yet:

```bash
cp .env.example .env.local
# Ensure: NEXT_PUBLIC_API_URL=http://localhost:8000
```

Install and start:

```bash
npm install
npm run dev
```

App is usually **http://localhost:3000**. The UI calls the FastAPI base from `NEXT_PUBLIC_API_URL`.

---

## 4. Manual smoke checks (browser + curl)

With **both** servers running:

| Check | Suggestion |
|--------|------------|
| Health | `curl -s http://localhost:8000/health` |
| Alerts (guest) | `curl -s 'http://localhost:8000/api/alerts?guest=true' \| head -c 400` |
| KPIs | `curl -s 'http://localhost:8000/api/dashboard/kpis?guest=true'` |
| OpenAPI | Open http://localhost:8000/docs |

In the browser: sign in or **Continue as guest**, then open **Alerts**, **Dashboard**, **FL Health**, **Forensics**, **Incidents**, **Audit** (Verify chain).

---

## 5. What the automated tests cover

See [`backend/tests/test_faheem_endpoints.py`](../backend/tests/test_faheem_endpoints.py). They exercise:

- OpenAPI path registration for all Faheem routes  
- **GET** auth (guest vs missing auth)  
- **Alerts**: filters (`status`, `severity`), `sort`, cursor pagination, PATCH success + **404** / **400** / **401** / **403**, audit append  
- **Incidents** + **FL** + **Forensics** + **RCA**: success and **404**  
- **Dashboard KPIs** response shape  
- **Auth session**: success, **401**, **403** (guest)  
- **Quarantine**: success, **404**, device sync on alerts, **INC-001** timeline `QUARANTINE`  
- **Audit verify**: valid chain + tamper detection  
- **SSE** `/api/events`: **401** without auth in tests; **guest/token stream** is not asserted in pytest (infinite body + ASGI/clients often hang on partial read or close). Verify manually: `curl -N --max-time 2 'http://localhost:8000/api/events?guest=true'` (expect `text/event-stream` and `keep-alive` / `data:` lines).

---

## Related docs

- [`FAHEEM_BACKEND_IMPLEMENTATION.md`](./FAHEEM_BACKEND_IMPLEMENTATION.md) — what was built  
- [`BACKEND_PRD.md`](./BACKEND_PRD.md) — full API contract  
