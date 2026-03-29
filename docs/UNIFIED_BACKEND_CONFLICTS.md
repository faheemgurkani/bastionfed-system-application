# Unified Backend Conflict Resolution

This note records the runtime conflicts and parity decisions that were resolved when promoting the unified backend to `backend/`.

## Faheem vs Hunain conflict

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

## Hammad alignment decisions

Hammad's standalone implementation introduced additional endpoint logic that was not originally promoted into `backend/`. That gap has now been closed for the shared backend:

- `GET /api/devices`
- `GET /api/devices/{device_id}`
- `GET /api/fl/drift`
- `GET /api/fl/models`
- `GET /api/forensics/rca`
- `PATCH /api/incidents/{incident_id}`
- `PATCH /api/incidents/{incident_id}/playbook/steps/{step_id}`
- `POST /api/incidents/{incident_id}/playbook/halt`
- `POST /api/forensics/samples`
- `POST /api/forensics/rca`
- `POST /api/network/block-ip`

### BastionBot contract conflict

One Hammad-era BastionBot route conflicted with the newer unified BastionBot implementation:

- old Hammad standalone behavior:
  - `GET /api/bastionbot/conversations/{conversation_id}` allowed `?guest=true`
  - unknown conversation IDs returned `200` with an empty message list
- unified backend behavior:
  - BastionBot is signed-in only
  - unknown conversation IDs return `404 CONVERSATION_NOT_FOUND`

### Resolution used by `backend/`

The top-level unified backend keeps the newer unified BastionBot contract:

- BastionBot routes are signed-in only
- `GET /api/bastionbot/conversations/{conversation_id}` returns `404` when the conversation does not exist for that user

### Reflection back into `hammad_implementation`

To remove drift from Hammad's standalone backend:

- `backend/hammad_implementation/app/routers/auth.py`
  - BastionBot conversation history now requires user auth
  - unknown conversation IDs now return `CONVERSATION_NOT_FOUND`
- `backend/hammad_implementation/tests/test_hammad_endpoints.py`
  - updated to match the unified BastionBot contract
