## Backend API Endpoints — Count, Difficulty, and Assignment Split

Source: `docs/BACKEND_PRD.md`

### Total endpoint count

**36** total backend endpoints (counted as **HTTP method + path**).

### Difficulty buckets (summary)

- **Easy (18)**: Mostly read-only GETs (list/detail) with straightforward DB reads and filtering.
- **Medium (9)**: Mutations (PATCH/POST) with state transitions, audit logging, and/or light orchestration.
- **Hard (9)**: SSE streaming, external integrations (firewall/edge agent/LLM/S3), background jobs, or integrity verification workflows.

### Difficulty buckets (full list)

#### Easy (18)
- GET `/api/alerts`
- GET `/api/alerts/{alert_id}`
- GET `/api/incidents`
- GET `/api/incidents/{incident_id}`
- GET `/api/devices`
- GET `/api/devices/{device_id}`
- GET `/api/fl/status`
- GET `/api/fl/rounds`
- GET `/api/fl/clients`
- GET `/api/fl/clients/{client_id}`
- GET `/api/fl/drift`
- GET `/api/fl/models`
- GET `/api/forensics/samples`
- GET `/api/forensics/samples/{sample_id}`
- GET `/api/forensics/rca`
- GET `/api/forensics/rca/{rca_id}`
- GET `/api/bastionbot/conversations`
- GET `/api/bastionbot/conversations/{conversation_id}`

#### Medium (9)
- POST `/api/auth/session`
- PATCH `/api/alerts/{alert_id}`
- POST `/api/alerts/{alert_id}/escalate`
- PATCH `/api/incidents/{incident_id}`
- PATCH `/api/incidents/{incident_id}/playbook/steps/{step_id}`
- POST `/api/incidents/{incident_id}/playbook/run`
- POST `/api/incidents/{incident_id}/playbook/halt`
- GET `/api/audit/logs`
- GET `/api/dashboard/kpis`

#### Hard (9)
- GET `/api/events` (SSE)
- GET `/api/fl-events` (SSE)
- POST `/api/devices/{device_id}/quarantine`
- POST `/api/network/block-ip`
- POST `/api/bastionbot/chat`
- POST `/api/forensics/samples` (multipart upload + storage + async analysis)
- POST `/api/forensics/rca` (generation pipeline; may include LLM)
- GET `/api/audit/verify` (hash-chain integrity verification)
- POST `/api/fl/models/{model_name}/activate` (hot model switch)

---

## Implementation assignment

Goal: each member gets **12 endpoints total** with the same difficulty mix: **6 easy, 3 medium, 3 hard**.

### Faheem (12 total = 6 easy / 3 medium / 3 hard)

- **Easy (6)**
  - GET `/api/alerts`
  - GET `/api/incidents/{incident_id}`
  - GET `/api/fl/status`
  - GET `/api/fl/clients/{client_id}`
  - GET `/api/forensics/samples`
  - GET `/api/forensics/rca/{rca_id}`

- **Medium (3)**
  - PATCH `/api/alerts/{alert_id}`
  - GET `/api/dashboard/kpis`
  - POST `/api/auth/session`

- **Hard (3)**
  - GET `/api/events` (SSE)
  - POST `/api/devices/{device_id}/quarantine`
  - GET `/api/audit/verify`

**Integration note:** The Next.js UI wired for these routes also calls endpoints assigned to **Hunain** and **Hammad** (e.g. incident **list**, FL **list** + **`/api/fl-events`**, audit **log list**). For end-to-end behavior, those routes must exist on the same `NEXT_PUBLIC_API_URL` service (or the client must use multiple API bases). See [`docs/FAHEEM/FAHEEM_BACKEND_TODO.md`](./FAHEEM/FAHEEM_BACKEND_TODO.md) **§2** for the dependency table and implementer requirements.

### Hunain (12 total = 6 easy / 3 medium / 3 hard)

- **Easy (6)**
  - GET `/api/alerts/{alert_id}`
  - GET `/api/incidents`
  - GET `/api/fl/rounds`
  - GET `/api/fl/clients`
  - GET `/api/forensics/samples/{sample_id}`
  - GET `/api/bastionbot/conversations`

- **Medium (3)**
  - POST `/api/alerts/{alert_id}/escalate`
  - GET `/api/audit/logs`
  - POST `/api/incidents/{incident_id}/playbook/run`

- **Hard (3)**
  - GET `/api/fl-events` (SSE)
  - POST `/api/bastionbot/chat`
  - POST `/api/fl/models/{model_name}/activate`

### Hammad (12 total = 6 easy / 3 medium / 3 hard)

- **Easy (6)**
  - GET `/api/devices`
  - GET `/api/devices/{device_id}`
  - GET `/api/fl/drift`
  - GET `/api/fl/models`
  - GET `/api/forensics/rca`
  - GET `/api/bastionbot/conversations/{conversation_id}`

- **Medium (3)**
  - PATCH `/api/incidents/{incident_id}`
  - PATCH `/api/incidents/{incident_id}/playbook/steps/{step_id}`
  - POST `/api/incidents/{incident_id}/playbook/halt`

- **Hard (3)**
  - POST `/api/forensics/samples`
  - POST `/api/forensics/rca`
  - POST `/api/network/block-ip`

