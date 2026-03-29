# BastionFed — Setup Guide

## Prerequisites

- Node.js 18+
- npm

---

## 1. Clone the repo

```bash
git clone <repo-url>
cd bastionfed-system-application
```

---

## 2. Get the `.env.local` file

Get the `.env.local` file from the frontend lead and place it inside the `frontend/` folder:

```
bastionfed-system-application/
└── frontend/
    └── .env.local   ← place it here
```

> Do **not** create a new Firebase project — the existing credentials are shared via this file.

---

## 3. Install & run

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## 4. Run the unified FastAPI backend (single port)

This repo originally had 3 backend “forks”. The unified backend now runs directly from the top-level `backend/` directory.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
.venv/bin/python dev_server.py
```

This is the recommended development command. It uses a scoped reload watcher so `.venv` does not trigger repeated reloads.

If you want to use raw Uvicorn with reload, run:

```bash
cd backend
uvicorn app.main:app --reload --reload-dir app --reload-dir tests --host 0.0.0.0 --port 8000
```

The API serves at `http://localhost:8000`. Ensure `frontend/.env.local` contains:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Optional BastionBot persistence override:

```env
BASTIONBOT_DB_PATH=data/bastionbot.sqlite3
```

Optional BastionBot Groq configuration is loaded from `backend/.env`:

```env
GROQ_API_KEY=
GROQ_MODEL=llama-3.1-8b-instant
```

The contributor-specific backends still remain intact and runnable independently:

- `backend/faheem_implementation/`
- `backend/hunain_implementation/`
- `backend/hammad_implementation/`

---

## Expected environment variables

Your `.env.local` should contain the following keys (values provided by the frontend lead):

```env
NEXT_PUBLIC_FIREBASE_API_KEY=
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=
NEXT_PUBLIC_FIREBASE_PROJECT_ID=
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=
NEXT_PUBLIC_FIREBASE_APP_ID=
```

The BastionBot page no longer requires a browser-side Gemini key. It now uses the unified FastAPI backend and per-user SQLite-backed memory.

A `frontend/.env.example` with these keys (empty values) is already in the repo for reference.

---

> **Never commit `.env.local`** — it is gitignored. If accidentally committed, run `git rm --cached frontend/.env.local` immediately.
