# BastionFed FastAPI backend

## Run (development)

This directory remains runnable on its own, but the default unified backend entrypoint for the app is now `backend/`.

```bash
cd backend/hunain_implementation
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API serves at `http://localhost:8000`. Configure the Next.js app with `NEXT_PUBLIC_API_URL=http://localhost:8000`.

Optional BastionBot persistence override:

```bash
export BASTIONBOT_DB_PATH=data/bastionbot.sqlite3
```

Optional Groq configuration for BastionBot Ask Mode is loaded from `backend/.env`:

```bash
GROQ_API_KEY=...
GROQ_MODEL=llama-3.1-8b-instant
```

Implementation notes:

- BastionBot is available only to signed-in users
- BastionBot conversation state is stored in SQLite
- BastionBot chat is grounded with project docs, curated UI/API metadata, and live in-process platform state
- Full BastionBot implementation details are documented in `docs/BASTIONBOT_ASK_MODE.md`
- The promoted unified backend source of truth now lives at `backend/`, while this directory remains available for independent runs

## Tests

```bash
cd backend/hunain_implementation
.venv/bin/python -m pytest -q
```

Live BastionBot HTTP test:

```bash
export LIVE_SERVER_URL=http://127.0.0.1:8000
.venv/bin/python -m pytest tests/test_live_server.py -q
```
