# Hammad backend — decisions, TODOs, and gaps

> **Runtime source of truth:** `backend/` (unified FastAPI). Hammad’s routes were promoted into the unified backend. Standalone fork: `backend/hammad_implementation/`.

References: [HAMMAD_BACKEND_IMPLEMENTATION.md](./HAMMAD_BACKEND_IMPLEMENTATION.md) · [LOCAL_TESTING.md](../LOCAL_TESTING.md) · [BACKEND_PRD.md](../BACKEND_PRD.md)

---

## Decisions in effect (unified backend)

- Devices, FL drift/models, forensics upload/RCA, incident playbook mutations, block-IP — all in `backend/app/routers/`
- Firebase JWT verification on protected routes
- Forensics uploads use Supabase Storage when configured

---

## Pending validation (manual/UI)

- [ ] Devices, drift, and model zoo screens against live API
- [ ] Multipart forensics upload from UI
- [ ] Incident lifecycle and block-IP actions

---

## Gaps vs PRD (known)

- [ ] `GET /api/forensics/rca` list shape vs PRD summary rows
- [ ] Some error paths map invalid status to not-found style responses

---

## Suggested next steps

1. Lock RCA list contract with team
2. Normalize invalid-status vs missing-resource errors where needed
3. See [TODO.md](../TODO.md) for cross-team priorities
