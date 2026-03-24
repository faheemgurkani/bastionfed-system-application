# Hammad backend — decisions, TODOs, and gaps

This document captures pending work for Hammad’s endpoint scope after the in-memory phase.

References:
- [`HAMMAD_BACKEND_IMPLEMENTATION.md`](./HAMMAD_BACKEND_IMPLEMENTATION.md)
- [`HAMMAD_LOCAL_TESTING.md`](./HAMMAD_LOCAL_TESTING.md)
- [`../BACKEND_PRD.md`](../BACKEND_PRD.md)

---

## Decisions currently in effect

- In-memory `AppState` with startup reset and seeded data.
- Stub bearer auth and guest-mode reads.
- Endpoint ownership strictly limited to Hammad assigned route surface.

---

## Pending validation (manual/UI)

- [ ] Verify frontend screens using `devices`, `fl/drift`, `fl/models` are wired against backend.
- [ ] Verify multipart sample upload UX path from forensics page.
- [ ] Verify incident lifecycle UI actions (status patch, step patch, halt).
- [ ] Verify block-IP action wiring from alert drawer once enabled in UI.

---

## Gaps vs PRD (known)

- [ ] Firebase Admin SDK verification not integrated (stub auth only).
- [ ] `GET /api/forensics/rca` currently returns full RCA objects; PRD list endpoint suggests summary rows.
- [ ] Some router response models use `dict` instead of strict typed wrappers.
- [ ] `PATCH /playbook/steps/{step_id}` invalid status currently maps to step-not-found style handling.

---

## Suggested next steps

1. Lock expected contract strictness with team (especially RCA list shape).
2. Normalize error handling for invalid status vs missing resources where needed.
3. Add Firebase Admin token verification when moving off stub auth.
