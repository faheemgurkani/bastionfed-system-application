# Hunain backend — decisions, TODOs, and gaps

This document tracks pending work for Hunain’s endpoint scope after the in-memory phase.

References:
- [`HUNAIN_BACKEND_IMPLEMENTATION.md`](./HUNAIN_BACKEND_IMPLEMENTATION.md)
- [`HUNAIN_LOCAL_TESTING.md`](./HUNAIN_LOCAL_TESTING.md)
- [`../BACKEND_PRD.md`](../BACKEND_PRD.md)

---

## Decisions currently in effect

- In-memory state only (`AppState`), seeded at startup.
- Stub bearer auth (token presence), guest mode for read routes.
- SSE route for FL patches implemented in FastAPI (`/api/fl-events`).
- JSON contracts use camelCase aliases.

---

## Pending validation (manual/UI)

- [ ] Verify `/api/fl-events` in browser EventSource flow (token mode and reconnect behavior).
- [ ] Verify chat UX path (`/api/bastionbot/chat`) from frontend context actions.
- [ ] Verify escalate action from alert drawer end-to-end in UI.
- [ ] Verify playbook run button behavior in incident detail UI.
- [ ] Verify model activate action from FL model UI.

---

## Gaps vs PRD (known)

- [ ] Firebase Admin SDK verification not integrated (currently stub bearer check).
- [ ] `POST /api/alerts/{alert_id}/escalate` currently returns 200; PRD example indicates 201.
- [ ] `GET /api/incidents` router currently exposes limit/cursor; PRD also describes extra filters.
- [ ] `GET /api/fl/rounds` PRD mentions query options that are not yet surfaced in router signature.
- [ ] SSE auth policy currently permits guest mode; PRD text leans token-based for SSE.

---

## Suggested next steps

1. Lock contract deltas (status codes + query params) with team.
2. Add Firebase Admin verification in auth dependency layer.
3. Keep existing test suite green while applying strict PRD-alignment fixes.
