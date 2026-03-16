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

## Expected environment variables

Your `.env.local` should contain the following keys (values provided by the frontend lead):

```env
NEXT_PUBLIC_FIREBASE_API_KEY=
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=
NEXT_PUBLIC_FIREBASE_PROJECT_ID=
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=
NEXT_PUBLIC_FIREBASE_APP_ID=
NEXT_PUBLIC_GEMINI_API_KEY=
```

A `frontend/.env.example` with these keys (empty values) is already in the repo for reference.

---

> **Never commit `.env.local`** — it is gitignored. If accidentally committed, run `git rm --cached frontend/.env.local` immediately.
