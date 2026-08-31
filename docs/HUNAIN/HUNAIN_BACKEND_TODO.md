# Hunain backend — decisions, TODOs, and gaps

> **Runtime source of truth:** `backend/` (unified FastAPI). This document tracks Hunain’s original 12-endpoint scope. Standalone fork: `backend/hunain_implementation/`.

References: [HUNAIN_BACKEND_IMPLEMENTATION.md](./HUNAIN_BACKEND_IMPLEMENTATION.md) · [LOCAL_TESTING.md](../LOCAL_TESTING.md) · [BACKEND_PRD.md](../BACKEND_PRD.md)

---

## Decisions in effect (unified backend)

- Tenant-scoped Postgres when `DATABASE_URL` is set; in-memory fallback for demo/tests
- Firebase JWT verification on protected routes (`app/auth/firebase.py`)
- SSE: `/api/fl-events` (fast FL patches), Redis pub/sub when `REDIS_URL` is set
- BastionBot: signed-in only, Groq + Postgres/SQLite persistence, grounded citations — see [BASTIONBOT_ASK_MODE.md](../BASTIONBOT_ASK_MODE.md)

---

## Pending validation (manual/UI)

- [ ] `/api/fl-events` EventSource reconnect behavior in browser
- [ ] BastionBot chat end-to-end with Google sign-in
- [ ] Alert escalate, playbook run, model activate from UI

---

## Gaps vs PRD (known)

- [ ] `POST /api/alerts/{alert_id}/escalate` returns 200; PRD example indicates 201
- [ ] `GET /api/incidents` — extra PRD filters not fully exposed
- [ ] Guest/demo SSE policy vs production token-only policy — confirm product decision

---

## Suggested next steps

1. Lock contract deltas (status codes, query params) with team
2. Keep unified pytest green while applying PRD-alignment fixes
3. See [TODO.md](../TODO.md) for cross-team priorities
