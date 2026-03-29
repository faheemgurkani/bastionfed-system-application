# BastionFed Unified Backend

This directory is now the **default unified FastAPI backend entrypoint** for BastionFed.

The implementation here is promoted from the unified Hunain-based backend and is now the general backend source of truth for running the application on a single port.

## What stays intact

The contributor-specific backend directories are still present and still runnable independently:

- `backend/faheem_implementation/`
- `backend/hunain_implementation/`
- `backend/hammad_implementation/`

Use this top-level `backend/` directory when you want the single unified backend for the full application.

## Run the unified backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
.venv/bin/python dev_server.py
```

This is the recommended development command. It enables reload, but only watches `backend/app` and `backend/tests`, which prevents `.venv` from triggering endless reloads.

If you want to run Uvicorn manually with reload, use:

```bash
cd backend
uvicorn app.main:app --reload --reload-dir app --reload-dir tests --host 0.0.0.0 --port 8000
```

If you do not need reload, use:

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API serves at `http://localhost:8000`.

Set the frontend to use it with:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Environment variables

The unified backend loads environment variables from `backend/.env`.

Relevant BastionBot settings:

```env
GROQ_API_KEY=...
GROQ_MODEL=llama-3.1-8b-instant
BASTIONBOT_DB_PATH=data/bastionbot.sqlite3
```

## Tests

Run the unified backend test suite from `backend/`:

```bash
cd backend
.venv/bin/python -m pytest -q
```

Run the live HTTP BastionBot integration test:

```bash
cd backend
export LIVE_SERVER_URL=http://127.0.0.1:8000
.venv/bin/python -m pytest tests/test_live_server.py -q
```

## Notes

- BastionBot remains signed-in only
- the unified backend includes the BastionBot Groq integration, SQLite persistence, and all unified API routes
- the unified `/api/events` alert stream follows Faheem's slower development cadence of one synthetic alert per minute to avoid overwhelming the frontend
- top-level `backend/app` is the general unified backend codebase going forward
- the implementation folders remain available for independent contributor testing and historical isolation
