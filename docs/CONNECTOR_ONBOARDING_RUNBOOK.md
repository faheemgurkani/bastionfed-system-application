# Connector Onboarding Runbook

1. Create an ingest source with `POST /api/ingest/sources` as a tenant owner or admin.
2. Record the returned source id and secret in your connector secret store.
3. Configure the external system to send `POST /api/ingest/events` with:
   - `X-BastionFed-Ingest-Key: <secret>`
   - `sourceId`
   - `externalId`
   - `eventType`
   - `payload`
4. Validate idempotency by replaying the same `externalId`; the API should return `parseStatus=DUPLICATE`.
5. Rotate credentials with `POST /api/ingest/sources/{source_id}/rotate-secret` after initial validation and on every credential hygiene cycle.
6. Confirm the tenant dashboard reports `liveDataConnected=true` after the first accepted event.

Use this release for push-style webhook/API connectors only. Full pull-based SIEM/EDR orchestration is out of scope here.
