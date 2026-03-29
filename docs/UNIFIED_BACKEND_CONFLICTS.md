# Unified Backend Conflict Resolution

This note records the Faheem vs Hunain logic conflict that was resolved when promoting the unified backend to `backend/`.

## Conflict

The only confirmed Faheem/Hunain runtime conflict was in the SSE event cadence:

- Faheem implementation expected `GET /api/events` to emit one synthetic alert per minute
- Hunain implementation used a fast shared SSE tick that caused `GET /api/events` to emit alerts continuously
- `GET /api/fl-events` should remain fast for FL client patch updates

## Resolution used by `backend/`

The top-level unified backend now uses:

- `GET /api/events`: Faheem-style slow alert cadence
  - alert tick every `1.0s`
  - actual alert emission every `60.0s`
- `GET /api/fl-events`: Hunain-style fast FL patch cadence
  - FL tick every `0.25s`

## Reflection back into standalone implementations

To keep standalone behavior aligned with the unified backend:

- `backend/hunain_implementation/app/routers/events.py`
  - updated so `/api/events` is slow and `/api/fl-events` stays fast
- `backend/faheem_implementation/app/routers/fl_events.py`
  - updated FL SSE tick to `0.25s` to match the unified backend

## Current source of truth

When you run the server from `backend/`, the active runtime behavior is:

- Faheem logic for alert SSE cadence on `/api/events`
- Hunain logic for FL SSE cadence on `/api/fl-events`

Everything else on the Faheem/Hunain assigned endpoint surface remains preserved in the unified backend according to the promoted router logic already present in `backend/app`.
