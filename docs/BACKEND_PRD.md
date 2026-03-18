# BastionFed — Backend API PRD
## FastAPI Service Specification

> **Document type**: Product Requirements Document — Backend  
> **Target stack**: Python · FastAPI · PostgreSQL (or TimescaleDB for time-series) · Redis (SSE pub/sub) · Firebase Admin SDK  
> **Frontend**: Next.js 14 (App Router) — all contracts derived from the live frontend codebase  
> **Base URL (dev)**: `http://localhost:8000`  
> **Auth model**: Firebase ID Token passed as `Authorization: Bearer <token>` on every request (except SSE streams which use a `?token=` query param due to `EventSource` limitations)

---

## Table of Contents

1. [Global Conventions](#1-global-conventions)
2. [Data Schemas](#2-data-schemas)
3. [Authentication](#3-authentication)
4. [Real-Time Streams (SSE)](#4-real-time-streams-sse)
5. [Alerts](#5-alerts)
6. [Incidents](#6-incidents)
7. [Devices](#7-devices)
8. [FL Health](#8-fl-health)
9. [Forensics — Malware Samples](#9-forensics--malware-samples)
10. [Forensics — RCA Reports](#10-forensics--rca-reports)
11. [Audit Logs](#11-audit-logs)
12. [BastionBot](#12-bastionbot)
13. [Response Actions](#13-response-actions)
14. [Dashboard KPIs](#14-dashboard-kpis)
15. [Environment Variables](#15-environment-variables)
16. [Priority Matrix](#16-priority-matrix)

---

## 1. Global Conventions

### Request / Response format
- All request and response bodies are `application/json`.
- All timestamps are **ISO 8601 UTC** strings, e.g. `"2025-06-01T14:30:00Z"`.
- All list endpoints support cursor-based pagination via `?cursor=<opaque_string>&limit=<int>` unless otherwise stated.
- On error, return:

```json
{
  "detail": "Human-readable error message",
  "code": "MACHINE_READABLE_CODE"
}
```

### HTTP status codes used

| Code | Meaning |
|------|---------|
| `200` | OK |
| `201` | Created |
| `204` | No content (successful delete / action with no body) |
| `400` | Bad request / validation error |
| `401` | Missing or invalid Firebase token |
| `403` | Authenticated but insufficient permissions |
| `404` | Resource not found |
| `409` | Conflict (e.g. duplicate resource) |
| `422` | Unprocessable entity (Pydantic validation failure) |
| `500` | Internal server error |

### CORS
Allow `http://localhost:3000` (and production domain) with credentials.

---

## 2. Data Schemas

The following Pydantic models map exactly to the TypeScript interfaces used throughout the frontend. They are referenced by endpoint specs below.

### 2.1 Enumerations

```python
class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH     = "HIGH"
    MEDIUM   = "MEDIUM"
    LOW      = "LOW"

class AlertStatus(str, Enum):
    OPEN           = "OPEN"
    IN_REVIEW      = "IN_REVIEW"
    RESOLVED       = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"

class FLClientStatus(str, Enum):
    ACTIVE            = "ACTIVE"
    DEGRADED          = "DEGRADED"
    OFFLINE           = "OFFLINE"
    POISONING_SUSPECT = "POISONING_SUSPECT"

class IncidentStatus(str, Enum):
    NEW        = "NEW"
    TRIAGING   = "TRIAGING"
    RESPONDING = "RESPONDING"
    RESOLVED   = "RESOLVED"
    POST_MORTEM = "POST_MORTEM"

class DeviceStatus(str, Enum):
    NORMAL      = "NORMAL"
    SUSPICIOUS  = "SUSPICIOUS"
    COMPROMISED = "COMPROMISED"
    ISOLATED    = "ISOLATED"

class AuditAction(str, Enum):
    DETECTION_MADE      = "DETECTION_MADE"
    RESPONSE_TRIGGERED  = "RESPONSE_TRIGGERED"
    MODEL_UPDATED       = "MODEL_UPDATED"
    USER_LOGIN          = "USER_LOGIN"
    DEVICE_QUARANTINED  = "DEVICE_QUARANTINED"
    CONFIG_CHANGED      = "CONFIG_CHANGED"
    REPORT_GENERATED    = "REPORT_GENERATED"
    FL_ROUND_COMPLETED  = "FL_ROUND_COMPLETED"
```

### 2.2 `Device`

```python
class Device(BaseModel):
    id          : str
    name        : str
    ip          : str
    type        : str            # e.g. "MRI Scanner", "Insulin Pump Hub"
    wing        : str            # e.g. "Wing A", "ICU"
    criticality : int            # 1–5
    flClientId  : str
    status      : DeviceStatus
```

### 2.3 `MitreAttackTechnique`

```python
class MitreAttackTechnique(BaseModel):
    id     : str    # e.g. "T0886"
    tactic : str    # e.g. "Lateral Movement"
    name   : str    # e.g. "Remote Services"
```

### 2.4 `ThreatIntelIndicator`

```python
class ThreatIntelIndicator(BaseModel):
    type   : Literal["HASH", "IP", "DOMAIN"]
    value  : str
    source : str    # e.g. "MISP", "AlienVault"
```

### 2.5 `Alert`

```python
class Alert(BaseModel):
    id             : str
    timestamp      : str
    deviceId       : str
    device         : Device
    type           : str            # e.g. "Ransomware", "Lateral Movement"
    tactic         : str            # MITRE tactic label
    technique      : MitreAttackTechnique
    severity       : Severity
    confidence     : float          # 0–100
    status         : AlertStatus
    modelVersion   : str            # e.g. "v4.2.1-DNN"
    threatIntel    : list[ThreatIntelIndicator]
    cveReference   : str | None
    featureSummary : str
```

### 2.6 `FLRound`

```python
class FLRound(BaseModel):
    round     : int
    accuracy  : float
    fpRate    : float
    trainLoss : float
    valLoss   : float
```

### 2.7 `FLClient`

```python
class FLClient(BaseModel):
    id               : str    # e.g. "Cardiology-FL-01"
    department       : str
    participationPct : float  # 0–100
    lastRound        : int
    dpEpsilon        : float
    modelVersion     : str
    status           : FLClientStatus
```

### 2.8 `FLClientPatch` (used in SSE stream)

```python
class FLClientPatch(BaseModel):
    id               : str
    participationPct : float | None = None
    lastRound        : int   | None = None
    status           : FLClientStatus | None = None
    dpEpsilon        : float | None = None
    modelVersion     : str   | None = None
```

### 2.9 `PlaybookStep`

```python
class PlaybookStep(BaseModel):
    id         : str
    stepNumber : int
    name       : str
    status     : Literal["COMPLETED", "RUNNING", "PENDING"]
    timestamp  : str | None = None
    notes      : str | None = None
```

### 2.10 `Playbook`

```python
class Playbook(BaseModel):
    id               : str
    name             : str
    triggerCondition : str
    lastRun          : str
    executions       : int
    status           : Literal["ACTIVE", "DRAFT", "DEPRECATED"]
    steps            : list[PlaybookStep]
```

### 2.11 `IncidentEvent`

```python
class IncidentEvent(BaseModel):
    id          : str
    timestamp   : str
    type        : Literal[
        "DETECTION", "ALERT", "PLAYBOOK_START",
        "QUARANTINE", "ANALYST_ASSIGNED", "RESOLVED"
    ]
    description : str
```

### 2.12 `Incident`

```python
class Incident(BaseModel):
    id              : str          # e.g. "INC-001"
    title           : str
    severity        : Severity
    status          : IncidentStatus
    affectedDevices : list[Device]
    timeOpen        : str          # human-readable, e.g. "47m", "2h"
    analystInitials : str
    timeline        : list[IncidentEvent]
    playbook        : Playbook
    ticketId        : str
    reporter        : str
    assignee        : str
    priority        : str          # "P1", "P2", etc.
    created         : str          # ISO 8601
    labels          : list[str]
```

### 2.13 `MalwareSample`

```python
class StaticAnalysis(BaseModel):
    imports : list[str]
    strings : list[str]

class DynamicAnalysis(BaseModel):
    network    : list[str]
    fileSystem : list[str]
    processes  : list[str]

class SampleAnalysis(BaseModel):
    static  : StaticAnalysis
    dynamic : DynamicAnalysis

class MalwareSample(BaseModel):
    id          : str
    sha256      : str
    md5         : str
    filename    : str
    size        : str            # e.g. "2.4 MB"
    type        : str            # e.g. "PE32 Executable"
    deviceId    : str
    timestamp   : str
    uploadTime  : str
    family      : str            # e.g. "LockBit 3.0"
    threatScore : int            # 0–100
    status      : Literal["COMPLETED", "IN_PROGRESS", "PENDING", "ANALYZED", "ANALYZING"]
    analysis    : SampleAnalysis
```

### 2.14 `RCAReport`

```python
class TimelineNode(BaseModel):
    label     : str
    timestamp : str

class AffectedNode(BaseModel):
    deviceName : str
    ip         : str
    impact     : str

class RCAReport(BaseModel):
    id               : str
    incidentId       : str
    title            : str
    executiveSummary : str
    timelineNodes    : list[TimelineNode]
    affectedNodes    : list[AffectedNode]
    mitreChain       : list[str]
    responseActions  : list[str]
    recommendations  : list[str]
```

### 2.15 `AuditLog`

```python
class AuditLog(BaseModel):
    id        : str
    timestamp : str
    actor     : str
    action    : AuditAction
    target    : str
    result    : str
    hash      : str    # tamper-evident SHA-256 chained hash
```

### 2.16 `BotMessage`

```python
class BotMessage(BaseModel):
    id        : str
    role      : Literal["USER", "BOT"]
    content   : str
    timestamp : str
```

---

## 3. Authentication

The frontend uses Firebase Auth (Google OAuth + guest mode). The backend must validate Firebase ID tokens using the **Firebase Admin SDK**.

### Middleware

All endpoints (except the SSE streams, which accept `?token=`) must verify the `Authorization: Bearer <firebase_id_token>` header. Guest mode is allowed for read-only GET endpoints — the frontend will send a `?guest=true` query param instead of a token when operating in guest mode.

```
POST /api/auth/session
```

**Brief**: Called by the frontend immediately after a successful Firebase sign-in to let the backend upsert the user profile and start a server-side session record.

**Request body**:
```json
{
  "uid": "firebase_uid_string",
  "email": "analyst@hospital.org",
  "displayName": "Alice Chen",
  "photoURL": "https://..."
}
```

**Response `200`**:
```json
{
  "uid": "firebase_uid_string",
  "createdAt": "2025-06-01T10:00:00Z",
  "lastLoginAt": "2025-06-01T14:30:00Z"
}
```

**Detail**: The backend upserts a record in the `users` table keyed by `uid`. It records `lastLoginAt` on every call. This endpoint is also the trigger to emit a `USER_LOGIN` audit log entry. No password management is needed — Firebase owns credentials.

---

## 4. Real-Time Streams (SSE)

### 4.1 Alert Event Stream

```
GET /api/events
```

**Brief**: Server-Sent Events stream that pushes new `Alert` objects to the frontend in real time as the BastionFed inference engine generates detections. This is the single most critical endpoint — it powers the dashboard `KPICards`, `EventsFeed`, `NetworkTopology`, and the full `AlertTable` on `/alerts`.

**Auth**: `?token=<firebase_id_token>` (SSE limitation — `EventSource` cannot set headers).

**Response**: `Content-Type: text/event-stream` stream.

**Event envelope per detection**:
```
data: {"id":"ALT-0052","timestamp":"2025-06-01T14:31:05Z","deviceId":"DEV-003","device":{...},"type":"Ransomware","tactic":"Impact","technique":{"id":"T0486","tactic":"Impact","name":"Data Destruction"},"severity":"CRITICAL","confidence":94.2,"status":"OPEN","modelVersion":"v4.2.1-DNN","threatIntel":[{"type":"HASH","value":"a3f...","source":"MISP"}],"cveReference":"CVE-2024-1234","featureSummary":"Rapid file encryption across 3 mount points detected."}

```

**Detail**:
- The backend must keep the connection alive with SSE comment pings (`": keep-alive\n\n"`) every 15 seconds.
- New alerts are published to a Redis channel by the inference engine. This endpoint subscribes to that channel and forwards events to connected clients.
- On initial connection, the backend **must not** replay history — the frontend seeds its state from `GET /api/alerts` first, then subscribes to the stream for incremental updates.
- Disconnect handling: clean up Redis subscription on client disconnect.
- The `id` field in each alert must be globally unique (e.g. `"ALT-{unix_ms}"`).

---

### 4.2 FL Client Update Stream

```
GET /api/fl-events
```

**Brief**: Server-Sent Events stream that pushes partial `FLClient` patch objects to the frontend as federated learning rounds progress. This powers the live `ClientGrid` on the FL Health page.

**Auth**: `?token=<firebase_id_token>`

**Response**: `Content-Type: text/event-stream` stream.

**Event envelope**:
```
data: {"id":"Cardiology-FL-01","participationPct":87.3,"lastRound":48,"status":"ACTIVE"}

```

**Detail**:
- Each event is a **patch** (not a full object replacement). The frontend's `FLClientsProvider` applies it with `Object.assign` onto the matching client keyed by `id`.
- Fields that have not changed must be omitted from the patch to minimise payload.
- Only `id` is always required; all other fields are optional.
- Emitted whenever the FL aggregation server completes a round or a client changes status (e.g. drift detector flags a client as `POISONING_SUSPECT`).
- Typical update fields per round completion: `{ id, participationPct, lastRound }`.
- Status transitions (e.g. `ACTIVE → POISONING_SUSPECT`) are emitted immediately when the anomaly detector fires.

---

## 5. Alerts

### 5.1 List Alerts

```
GET /api/alerts
```

**Brief**: Returns the paginated historical alert list. Called on initial page load of `/alerts` to seed the client-side state before the SSE stream takes over for live updates.

**Query parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Max records to return |
| `cursor` | string | — | Opaque pagination cursor |
| `severity` | string | — | Filter: `CRITICAL\|HIGH\|MEDIUM\|LOW` |
| `tactic` | string | — | Filter by MITRE tactic label (exact match) |
| `status` | string | — | Filter: `OPEN\|IN_REVIEW\|RESOLVED\|FALSE_POSITIVE` |
| `from` | ISO 8601 | — | Timestamp range start |
| `to` | ISO 8601 | — | Timestamp range end |
| `sort` | string | `timestamp_desc` | `timestamp_desc\|timestamp_asc\|severity_desc` |

**Response `200`**:
```json
{
  "items": [ /* Alert[] */ ],
  "nextCursor": "opaque_string_or_null",
  "total": 1240
}
```

**Detail**: The frontend's `AlertFilters` component allows filtering by severity (ALL / CRITICAL / HIGH / MEDIUM / LOW), ATT&CK tactic, date range (Last 1h / 6h / 24h / 7d / 30d / All Time), and sort order (Newest First / Oldest First / Highest Severity). These map directly to the query parameters above. Filtering and sorting is applied server-side; the frontend does not re-filter a cached list.

---

### 5.2 Get Alert Detail

```
GET /api/alerts/{alert_id}
```

**Brief**: Returns a single alert by ID. Used by `AlertDetailDrawer` when an analyst clicks a row in the alert table.

**Response `200`**: Full `Alert` object.

**Response `404`**: `{ "detail": "Alert not found", "code": "ALERT_NOT_FOUND" }`

---

### 5.3 Update Alert Status

```
PATCH /api/alerts/{alert_id}
```

**Brief**: Updates the status of an alert. Called by the four action buttons in `AlertDetailDrawer`: closing an alert sets status to `RESOLVED`; marking false positive sets `FALSE_POSITIVE`; starting investigation sets `IN_REVIEW`.

**Request body**:
```json
{
  "status": "RESOLVED"
}
```

**Response `200`**: Updated `Alert` object.

**Detail**: Every status change must emit a corresponding `AuditLog` entry with `action: "RESPONSE_TRIGGERED"`, `actor: <uid>`, `target: <alert_id>`, `result: "Status changed to RESOLVED"`. The response should include the updated alert so the frontend can update its local state without a separate fetch.

---

### 5.4 Escalate Alert to Incident

```
POST /api/alerts/{alert_id}/escalate
```

**Brief**: Creates a new `Incident` from an existing open alert. Triggered by the "Escalate to Incident" button in `AlertDetailDrawer`.

**Request body**: Empty (all incident fields are derived from the source alert).

**Response `201`**:
```json
{
  "incident": { /* full Incident object */ }
}
```

**Detail**: The backend creates an `Incident` with:
- `status: "NEW"`
- `severity` copied from the source alert
- `affectedDevices` seeded from `alert.device`
- `timeline` seeded with a single `IncidentEvent` of type `"DETECTION"` referencing the alert
- A default playbook assigned based on `alert.tactic`
- `ticketId` auto-generated (or fetched from a connected ticketing system)

The alert's status must be updated to `IN_REVIEW` as a side effect.

---

## 6. Incidents

### 6.1 List Incidents

```
GET /api/incidents
```

**Brief**: Returns the full list of incidents, grouped or filterable by status. This is the primary data source for `IncidentKanban` on the `/incidents` page. The frontend currently hardcodes `MOCK_INCIDENTS` and the page contains the comment `// FastAPI endpoint: GET http://localhost:8000/api/incidents`.

**Query parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | — | Filter by `IncidentStatus` |
| `severity` | string | — | Filter by `Severity` |
| `assignee` | string | — | Filter by analyst |
| `limit` | int | 100 | Max records |
| `cursor` | string | — | Pagination cursor |

**Response `200`**:
```json
{
  "items": [ /* Incident[] */ ],
  "nextCursor": null,
  "total": 5
}
```

**Detail**: The `IncidentKanban` component groups incidents client-side into five columns: `NEW`, `TRIAGING`, `RESPONDING`, `RESOLVED`, `POST_MORTEM`. The API returns all incidents and the frontend groups them. No server-side grouping endpoint is needed. Each incident object must include the full nested `affectedDevices`, `timeline`, and `playbook` to avoid N+1 fetches, since `IncidentDetail` requires all of them immediately on card click.

---

### 6.2 Get Incident

```
GET /api/incidents/{incident_id}
```

**Brief**: Returns a single incident by ID with full nested objects. Used when deep-linking to an incident or when `IncidentDetail` needs a refresh.

**Response `200`**: Full `Incident` object.

**Response `404`**: `{ "detail": "Incident not found", "code": "INCIDENT_NOT_FOUND" }`

---

### 6.3 Update Incident Status

```
PATCH /api/incidents/{incident_id}
```

**Brief**: Moves an incident through its Kanban lifecycle. Called when an analyst drags a card or explicitly transitions status.

**Request body**:
```json
{
  "status": "RESPONDING",
  "assignee": "JP",
  "notes": "Escalated after confirmed lateral movement."
}
```

**Response `200`**: Updated `Incident` object.

**Detail**: Each status transition appends a new `IncidentEvent` to `incident.timeline` with the appropriate type (e.g. `ANALYST_ASSIGNED`, `RESOLVED`). Emits an `AuditLog` entry.

---

### 6.4 Update Playbook Step

```
PATCH /api/incidents/{incident_id}/playbook/steps/{step_id}
```

**Brief**: Marks a playbook step as `RUNNING` or `COMPLETED`. Called by the "Halt Playbook" and step completion interactions in `IncidentDetail`.

**Request body**:
```json
{
  "status": "COMPLETED",
  "notes": "Device isolated via edge agent command."
}
```

**Response `200`**: Updated `PlaybookStep` object.

**Detail**: When all steps of a playbook are `COMPLETED`, the backend should automatically add a `RESOLVED` event to `incident.timeline` and suggest a status transition. The frontend currently renders a "Halt Playbook" button that has no backend call — this endpoint handles it (send `status: "PENDING"` to reset a running step).

---

## 7. Devices

### 7.1 List Devices

```
GET /api/devices
```

**Brief**: Returns the full inventory of IoMT devices. Used by `NetworkTopology` to render device nodes and by `AlertDetailDrawer` to enrich device context. Currently `MOCK_DEVICES` (15 devices) is imported directly — no dedicated page, but the data underpins every alert.

**Query parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `wing` | string | — | Filter by wing/department |
| `status` | string | — | Filter by `DeviceStatus` |
| `type` | string | — | Filter by device type |

**Response `200`**:
```json
{
  "items": [ /* Device[] */ ]
}
```

---

### 7.2 Get Device

```
GET /api/devices/{device_id}
```

**Brief**: Returns a single device by ID.

**Response `200`**: Full `Device` object.

---

### 7.3 Quarantine Device

```
POST /api/devices/{device_id}/quarantine
```

**Brief**: Sends an isolation command to the edge agent on the target device. Triggered by the "Quarantine Device" action button in `AlertDetailDrawer`.

**Request body**: Empty.

**Response `200`**:
```json
{
  "deviceId": "DEV-003",
  "status": "ISOLATED",
  "commandId": "CMD-0091",
  "sentAt": "2025-06-01T14:32:00Z"
}
```

**Detail**: The backend must:
1. Set `device.status = "ISOLATED"` in the database.
2. Dispatch an isolation command to the edge agent (via a message queue or direct WebSocket).
3. Emit an `AuditLog` entry with `action: "DEVICE_QUARANTINED"`.
4. Append a `QUARANTINE` event to any open incidents that reference this device.

Returns immediately with the command record; the actual edge agent confirmation is asynchronous. The frontend can poll `GET /api/devices/{device_id}` for status updates, or receive it via the SSE stream.

---

### 7.4 Block Source IP

```
POST /api/network/block-ip
```

**Brief**: Submits a firewall rule to block a threat-source IP address. Triggered by the "Block Source IP" button in `AlertDetailDrawer`.

**Request body**:
```json
{
  "ip": "192.168.1.99",
  "reason": "C2 communication detected — ALT-0047",
  "alertId": "ALT-0047"
}
```

**Response `200`**:
```json
{
  "ip": "192.168.1.99",
  "ruleId": "FW-RULE-0023",
  "appliedAt": "2025-06-01T14:33:00Z"
}
```

**Detail**: Emits a `RESPONSE_TRIGGERED` audit log entry. The actual firewall API call is abstracted behind this endpoint; the frontend has no knowledge of the firewall vendor.

---

## 8. FL Health

### 8.1 Get FL System Status

```
GET /api/fl/status
```

**Brief**: Returns summary metrics for the active FL training session, including the current round number, active client count, and aggregated model performance. Used by `RoundStatusBanner` and `PerformanceCharts`. The page comment reads: `// FastAPI endpoint: GET http://localhost:8000/api/fl/status`.

**Response `200`**:
```json
{
  "currentRound"      : 50,
  "totalRounds"       : 100,
  "activeClients"     : 12,
  "totalClients"      : 15,
  "nextRoundIn"       : 180,
  "aggregatorStatus"  : "AGGREGATING",
  "latestAccuracy"    : 97.3,
  "latestFpRate"      : 0.9,
  "driftDetected"     : false
}
```

**Field detail**:

| Field | Description |
|-------|-------------|
| `currentRound` | The round number currently in progress or most recently completed |
| `totalRounds` | Configured total rounds for the current training session |
| `activeClients` | Number of clients that submitted updates in the last round |
| `totalClients` | Total registered FL clients |
| `nextRoundIn` | Seconds until the next aggregation round starts (countdown) |
| `aggregatorStatus` | One of `"IDLE"`, `"COLLECTING"`, `"AGGREGATING"`, `"DISTRIBUTING"` |
| `latestAccuracy` | Global model accuracy after the last completed round |
| `latestFpRate` | Global false-positive rate after the last completed round |
| `driftDetected` | Whether the drift detector has flagged the current session |

**Detail**: `RoundStatusBanner` displays `activeClients / totalClients` (e.g. "12 / 15 CLIENTS ACTIVE"), `nextRoundIn` as a countdown, and the `aggregatorStatus` badge. `PerformanceCharts` uses the historical `FLRound[]` from `GET /api/fl/rounds`.

---

### 8.2 Get FL Training History

```
GET /api/fl/rounds
```

**Brief**: Returns the per-round performance metrics for the current training session. Used by `PerformanceCharts` to render accuracy and loss curves. Currently served from `MOCK_FL_ROUNDS` (50 rounds).

**Query parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `session_id` | string | latest | Training session identifier |
| `limit` | int | 50 | Max rounds to return |

**Response `200`**:
```json
{
  "rounds": [
    {
      "round"     : 1,
      "accuracy"  : 85.2,
      "fpRate"    : 4.1,
      "trainLoss" : 0.452,
      "valLoss"   : 0.498
    }
    /* ... up to `limit` rounds, ordered ascending by round number */
  ],
  "sessionId": "sess_2025_06_01"
}
```

---

### 8.3 List FL Clients

```
GET /api/fl/clients
```

**Brief**: Returns the current state of all registered FL clients. Used to seed the `ClientGrid` component on initial load before the SSE stream patches start arriving. The page comment reads: `// FastAPI endpoint: GET http://localhost:8000/api/fl/clients`.

**Response `200`**:
```json
{
  "clients": [ /* FLClient[] — all 15 clients */ ]
}
```

**Detail**: The `ClientGrid` component sorts clients in the order: `POISONING_SUSPECT → ACTIVE → DEGRADED → OFFLINE`. Sorting is done client-side; the API returns clients in any order.

---

### 8.4 Get FL Client Detail

```
GET /api/fl/clients/{client_id}
```

**Brief**: Returns detailed data for a single FL client. Currently the `ClientGrid` click-to-expand pop-up uses in-memory data — this endpoint allows refreshing that detail on demand.

**Response `200`**: Full `FLClient` object.

---

### 8.5 Get Drift Table

```
GET /api/fl/drift
```

**Brief**: Returns per-client drift metrics for the drift monitoring table on the FL Health page. Currently rendered with 5 hardcoded rows in `DriftTable`.

**Response `200`**:
```json
{
  "entries": [
    {
      "clientId"         : "Cardiology-FL-01",
      "department"       : "Cardiology",
      "roundsAgo"        : 3,
      "driftScore"       : 0.12,
      "baselineAccuracy" : 97.1,
      "currentAccuracy"  : 94.8,
      "flagged"          : false
    }
  ]
}
```

---

### 8.6 List Model Zoo

```
GET /api/fl/models
```

**Brief**: Returns the available models in the Model Zoo and which one is currently active. The `ModelZoo` component currently uses 3 hardcoded models; this endpoint makes the list dynamic.

**Response `200`**:
```json
{
  "models": [
    {
      "name"        : "DNN-v4.2.1",
      "type"        : "DNN",
      "accuracy"    : 97.3,
      "fpRate"      : 0.9,
      "size"        : "48MB",
      "trainedOn"   : "2025-05-28T00:00:00Z",
      "description" : "Deep neural network, general-purpose IoMT threat detection.",
      "active"      : true
    }
  ]
}
```

---

### 8.7 Switch Active Model

```
POST /api/fl/models/{model_name}/activate
```

**Brief**: Switches the inference engine to use the specified model from the Model Zoo. Triggered by the "Switch to Active" button in the `ModelZoo` component.

**Request body**: Empty.

**Response `200`**:
```json
{
  "activated": "GNN-v3.1.0",
  "previouslyActive": "DNN-v4.2.1",
  "switchedAt": "2025-06-01T15:00:00Z"
}
```

**Detail**: Emits a `MODEL_UPDATED` audit log entry. The inference engine must hot-reload the model without downtime.

---

## 9. Forensics — Malware Samples

### 9.1 List Malware Samples

```
GET /api/forensics/samples
```

**Brief**: Returns the list of captured malware samples in the repository. Used by `SampleList` on the `/forensics` page. The page comment reads: `// FastAPI endpoint: GET http://localhost:8000/api/forensics/samples`.

**Query parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | — | Filter by analysis status |
| `family` | string | — | Filter by malware family |
| `limit` | int | 50 | Max records |
| `cursor` | string | — | Pagination cursor |

**Response `200`**:
```json
{
  "items": [ /* MalwareSample[] */ ],
  "nextCursor": null,
  "total": 3
}
```

---

### 9.2 Get Sample Analysis

```
GET /api/forensics/samples/{sample_id}
```

**Brief**: Returns a single malware sample with its full static and dynamic analysis results. Used by `AnalysisReport` when an analyst selects a sample from `SampleList`.

**Response `200`**: Full `MalwareSample` object including the nested `analysis` object.

---

### 9.3 Upload Malware Sample

```
POST /api/forensics/samples
```

**Brief**: Uploads a new malware binary for analysis. Triggered by the "Upload" button in `SampleList`.

**Request**: `multipart/form-data`

| Field | Type | Description |
|-------|------|-------------|
| `file` | binary | The malware binary |
| `deviceId` | string | Source device ID |
| `notes` | string (optional) | Analyst notes |

**Response `201`**:
```json
{
  "id"         : "SAMPLE-004",
  "sha256"     : "e3b0c44298fc1...",
  "status"     : "PENDING",
  "uploadTime" : "2025-06-01T15:05:00Z"
}
```

**Detail**: The file is stored in object storage (S3-compatible). A background analysis job is queued. The sample status transitions: `PENDING → ANALYZING → ANALYZED`. Status updates are delivered via the SSE stream (alert event or a dedicated forensics SSE endpoint in a future iteration).

---

## 10. Forensics — RCA Reports

### 10.1 List RCA Reports

```
GET /api/forensics/rca
```

**Brief**: Returns the list of Root Cause Analysis reports. Currently `MOCK_RCA_REPORTS` (3 reports) exists in mock data but no page consumes it directly — this endpoint prepares for the forensics page expansion.

**Response `200`**:
```json
{
  "items": [ /* RCAReport[] (without full timelineNodes/affectedNodes) */ ],
  "total": 3
}
```

---

### 10.2 Get RCA Report

```
GET /api/forensics/rca/{rca_id}
```

**Brief**: Returns a single RCA report with full detail including timeline, affected nodes, MITRE chain, and recommendations.

**Response `200`**: Full `RCAReport` object.

---

### 10.3 Generate RCA Report

```
POST /api/forensics/rca
```

**Brief**: Auto-generates an RCA report from a resolved incident's data. Triggered by the "Generate Report" action (to be added to `IncidentDetail`).

**Request body**:
```json
{
  "incidentId": "INC-001"
}
```

**Response `201`**: Newly created `RCAReport` object.

**Detail**: The backend assembles the report by:
1. Fetching all `IncidentEvent` entries from the incident timeline.
2. Mapping `tactic`/`technique` references to MITRE ATT&CK for ICS.
3. Generating a narrative `executiveSummary` (optionally via an LLM call).
4. Emitting a `REPORT_GENERATED` audit log entry.

---

## 11. Audit Logs

### 11.1 List Audit Logs

```
GET /api/audit/logs
```

**Brief**: Returns the tamper-evident audit log for all platform actions. Used by `AuditLogTable` on the `/audit` page. The page comment reads: `// FastAPI endpoint: GET http://localhost:8000/api/audit/logs`.

**Query parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `action` | string | — | Filter by `AuditAction` |
| `actor` | string | — | Filter by user/system actor |
| `from` | ISO 8601 | — | Timestamp range start |
| `to` | ISO 8601 | — | Timestamp range end |
| `limit` | int | 50 | Max records |
| `cursor` | string | — | Pagination cursor |

**Response `200`**:
```json
{
  "items": [ /* AuditLog[] */ ],
  "nextCursor": "opaque_string_or_null",
  "total": 30
}
```

**Detail**: Audit logs are **append-only** and must never be mutatable via the API. Each `AuditLog.hash` is a SHA-256 of `(previous_hash + timestamp + actor + action + target + result)` forming a hash chain. This enables tamper detection for HIPAA compliance. The API must expose a separate integrity-check endpoint (see below).

---

### 11.2 Verify Audit Log Integrity

```
GET /api/audit/verify
```

**Brief**: Walks the entire audit log hash chain and confirms no entries have been tampered with. Returns a pass/fail result. Used by compliance officers.

**Response `200`**:
```json
{
  "valid"     : true,
  "totalLogs" : 30,
  "checkedAt" : "2025-06-01T15:10:00Z"
}
```

**Response `200` (tamper detected)**:
```json
{
  "valid"          : false,
  "firstBreakAt"   : "AUD-0012",
  "totalLogs"      : 30,
  "checkedAt"      : "2025-06-01T15:10:00Z"
}
```

---

## 12. BastionBot

### 12.1 Chat

```
POST /api/bastionbot/chat
```

**Brief**: Sends an analyst message to BastionBot and returns an AI-generated response. The page currently calls the **Google Gemini API directly from the client** using `NEXT_PUBLIC_GEMINI_API_KEY`. This endpoint wraps that call server-side to: (a) protect the API key, (b) inject platform context (active alerts, recent incidents) into the prompt, and (c) log all conversations. The page comment reads: `// FastAPI endpoint: POST http://localhost:8000/api/bastionbot/chat`.

**Request body**:
```json
{
  "message"        : "What does ALT-0047 indicate and what should I do?",
  "conversationId" : "conv_abc123",
  "context"        : {
    "alertId"    : "ALT-0047",
    "incidentId" : null
  }
}
```

**Response `200`**:
```json
{
  "message": {
    "id"        : "msg_0091",
    "role"      : "BOT",
    "content"   : "ALT-0047 indicates a ransomware execution attempt on the Insulin Pump Hub (DEV-003)...",
    "timestamp" : "2025-06-01T15:12:00Z"
  },
  "conversationId": "conv_abc123"
}
```

**Detail**:
- The backend constructs a system prompt that includes: current platform state summary (e.g. open alert count, active FL round, any active incidents), the specific alert/incident context if `context.alertId` or `context.incidentId` is provided (full object fetched from DB), and a role definition ("You are BastionBot, a blue team AI assistant for the BastionFed IoMT security platform...").
- Conversation history for `conversationId` is stored server-side (up to last 20 turns) and included in each Gemini call to maintain context.
- Each exchange is stored as `BotMessage` records associated with `conversationId` and `uid`.

---

### 12.2 List Conversations

```
GET /api/bastionbot/conversations
```

**Brief**: Returns the list of past conversation previews for the currently authenticated analyst. Used by the `ConversationList` sidebar in `ChatInterface`.

**Response `200`**:
```json
{
  "conversations": [
    {
      "id"          : "conv_abc123",
      "preview"     : "What does ALT-0047 indicate...",
      "updatedAt"   : "2025-06-01T15:12:00Z",
      "messageCount": 6
    }
  ]
}
```

---

### 12.3 Get Conversation History

```
GET /api/bastionbot/conversations/{conversation_id}
```

**Brief**: Returns the full message history for a given conversation.

**Response `200`**:
```json
{
  "conversationId" : "conv_abc123",
  "messages"       : [ /* BotMessage[] */ ]
}
```

---

## 13. Response Actions

These endpoints cover actions exposed by the frontend UI that do not fit neatly into the resource-centric categories above.

### 13.1 Trigger Playbook

```
POST /api/incidents/{incident_id}/playbook/run
```

**Brief**: Manually triggers execution of the playbook associated with an incident. Used by the play button in `IncidentDetail`.

**Request body**: Empty.

**Response `200`**:
```json
{
  "incidentId"  : "INC-001",
  "playbookId"  : "PB-RANSOM-001",
  "startedAt"   : "2025-06-01T15:15:00Z",
  "currentStep" : 1
}
```

---

### 13.2 Halt Playbook

```
POST /api/incidents/{incident_id}/playbook/halt
```

**Brief**: Halts the currently running playbook on an incident. Triggered by the "Halt Playbook" button in `IncidentDetail` (currently has no backend call).

**Request body**:
```json
{
  "reason": "Manual override by analyst JP"
}
```

**Response `200`**:
```json
{
  "halted"    : true,
  "haltedAt"  : "2025-06-01T15:18:00Z",
  "stoppedAt" : "STEP-003"
}
```

---

## 14. Dashboard KPIs

### 14.1 Get KPI Summary

```
GET /api/dashboard/kpis
```

**Brief**: Returns pre-aggregated KPI metrics for the dashboard `KPICards` component. The frontend currently derives these from the in-memory alerts array — moving the computation server-side prevents large alert payloads needing to be sent to the client just for counts.

**Response `200`**:
```json
{
  "activeThreats"      : 8,
  "avgConfidence"      : 91.4,
  "devicesUnderWatch"  : 23,
  "flRound"            : 50,
  "openIncidents"      : 3,
  "criticalAlerts"     : 2,
  "resolvedToday"      : 5,
  "falsePositiveRate"  : 3.2
}
```

**Detail**: Currently `devicesUnderWatch` (23) and `flRound` (50) are hardcoded in the frontend. This endpoint replaces those hardcoded values. The `KPICards` component renders four cards: active threats, avg confidence, devices under watch, and FL round — all of which this endpoint covers.

---

## 15. Environment Variables

The following environment variables are required by the **backend** service. Frontend-specific vars (Firebase, Gemini) are unchanged.

```dotenv
# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/bastionfed

# ── Redis (SSE pub/sub + session cache) ───────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── Firebase Admin ────────────────────────────────────────────────────────────
FIREBASE_SERVICE_ACCOUNT_KEY_PATH=/secrets/firebase-adminsdk.json
# or supply JSON inline:
FIREBASE_SERVICE_ACCOUNT_KEY_JSON={"type":"service_account",...}

# ── Google Gemini (server-side BastionBot calls) ───────────────────────────────
GEMINI_API_KEY=AIzaSy...

# ── CORS ──────────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS=http://localhost:3000,https://bastionfed.vercel.app

# ── Object Storage (malware sample uploads) ───────────────────────────────────
S3_ENDPOINT=https://s3.amazonaws.com
S3_BUCKET=bastionfed-malware-samples
S3_ACCESS_KEY=AKIA...
S3_SECRET_KEY=...

# ── FL Aggregation Server ─────────────────────────────────────────────────────
FL_AGGREGATOR_URL=http://localhost:9000
FL_AGGREGATOR_API_KEY=...

# ── Firewall / Network Enforcement ────────────────────────────────────────────
FIREWALL_API_URL=http://firewall.internal:8080
FIREWALL_API_KEY=...
```

---

## 16. Priority Matrix

The table below classifies every endpoint by implementation priority relative to the frontend's current state.

| Priority | Rationale |
|----------|-----------|
| **P0** — Blocking | Frontend is broken or shows empty/stale data without this |
| **P1** — High | A full page is non-functional; currently uses hardcoded mock data |
| **P2** — Medium | Feature exists but an action button has no backend call |
| **P3** — Low | Page not yet built or data not yet consumed by frontend |

| Priority | Method | Endpoint | Powers |
|----------|--------|----------|--------|
| **P0** | GET (SSE) | `/api/events` | Dashboard, Alerts — live feed |
| **P0** | GET (SSE) | `/api/fl-events` | FL Health — ClientGrid live patches |
| **P0** | GET | `/api/alerts` | Alerts page — seeding state on load |
| **P1** | GET | `/api/incidents` | Incidents Kanban |
| **P1** | GET | `/api/fl/status` | RoundStatusBanner, FL KPIs |
| **P1** | GET | `/api/fl/rounds` | PerformanceCharts |
| **P1** | GET | `/api/fl/clients` | ClientGrid initial seed |
| **P1** | GET | `/api/forensics/samples` | Forensics SampleList |
| **P1** | GET | `/api/audit/logs` | Audit log table |
| **P1** | GET | `/api/dashboard/kpis` | KPICards (replaces hardcoded values) |
| **P2** | PATCH | `/api/alerts/{id}` | AlertDetailDrawer status actions |
| **P2** | POST | `/api/alerts/{id}/escalate` | Escalate to Incident button |
| **P2** | POST | `/api/devices/{id}/quarantine` | Quarantine Device button |
| **P2** | POST | `/api/network/block-ip` | Block Source IP button |
| **P2** | PATCH | `/api/incidents/{id}` | Incident status transitions |
| **P2** | PATCH | `/api/incidents/{id}/playbook/steps/{step_id}` | Playbook step completion |
| **P2** | POST | `/api/incidents/{id}/playbook/halt` | Halt Playbook button |
| **P2** | POST | `/api/bastionbot/chat` | BastionBot (move key server-side) |
| **P2** | POST | `/api/forensics/samples` | Sample upload button |
| **P2** | POST | `/api/fl/models/{name}/activate` | Model Zoo switch button |
| **P2** | GET | `/api/alerts/{id}` | AlertDetailDrawer detail refresh |
| **P2** | POST | `/api/auth/session` | Post-login user upsert |
| **P3** | GET | `/api/fl/drift` | DriftTable (hardcoded currently) |
| **P3** | GET | `/api/fl/models` | ModelZoo (hardcoded currently) |
| **P3** | GET | `/api/forensics/rca` | RCA list (mock data, no page yet) |
| **P3** | GET | `/api/forensics/rca/{id}` | RCA detail |
| **P3** | POST | `/api/forensics/rca` | Auto-generate RCA report |
| **P3** | GET | `/api/audit/verify` | Audit chain integrity check |
| **P3** | GET | `/api/bastionbot/conversations` | Conversation list sidebar |
| **P3** | GET | `/api/bastionbot/conversations/{id}` | Conversation history |
| **P3** | GET | `/api/devices` | NetworkTopology (enrichment) |
| **P3** | GET | `/api/devices/{id}` | Device detail |
| **P3** | POST | `/api/incidents/{id}/playbook/run` | Run Playbook button |
| **P3** | GET | `/api/incidents/{id}` | Direct incident deep-link |
