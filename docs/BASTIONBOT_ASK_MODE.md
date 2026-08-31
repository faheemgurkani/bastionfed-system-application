# BastionBot Ask Mode

This document describes the implemented **BastionBot Ask Mode** feature in the unified backend at `backend/` and the corresponding frontend at `frontend/app/bastionbot`.

## Purpose

BastionBot is the BastionFed in-product assistant for:

- product help
- screen and workflow guidance
- backend and frontend implementation questions
- live operational questions about alerts, incidents, devices, FL Health, and audit verification

This milestone intentionally keeps BastionBot in **read-only ask mode**. It explains the system, cites what it used, and preserves user-specific context, but it must not mutate platform state or trigger response actions.

## Implemented behavior

### Access model

- BastionBot is available only to **signed-in users**
- **`client_user`** accounts: live-data grounding (alerts, incidents, KPIs, FL, audit verify) is limited to **allowed FL client IDs** from `membership_client_scopes`, matching list/detail API filtering
- dev/demo read mode is explicitly blocked in the API
- users who are not signed in see a dedicated sign-in message on `/bastionbot`
- the frontend explains that sign-up or sign-in is required because conversations and memory are isolated per user

### User model and isolation

- every BastionBot conversation belongs to a single user UID
- each user only sees:
  - their own conversation list
  - their own message history
  - their own memory record
- foreign-user access to another conversation returns `404`
- dev mode users do not get BastionBot memory or conversation access (same as unsigned)

### Ask-mode behavior

- BastionBot answers as a BastionFed platform assistant
- it is grounded in:
  - project documentation
  - curated UI metadata
  - curated API metadata
  - live in-process application state when relevant
- it answers in markdown and returns structured source citations
- it uses prior conversation history and recent topics to preserve continuity for the same user
- if grounding is insufficient, it returns a safe fallback instead of inventing an answer

## LLM and grounding stack

### Groq integration

The answer generator uses **Groq** with model **`llama-3.1-8b-instant`**.

Configuration is loaded from `backend/.env` using `python-dotenv` in `app/config.py`.

Relevant settings:

```env
GROQ_API_KEY=...
GROQ_MODEL=llama-3.1-8b-instant
BASTIONBOT_DB_PATH=data/runtime/bastionbot.sqlite3
```

(`data/runtime/` is **`backend/data/runtime/`** when the server runs with cwd `backend/`; see `backend/DATA_DIRECTORY.md`.)

Notes:

- `GROQ_API_KEY` is loaded from `backend/.env`
- `GROQ_MODEL` defaults to `llama-3.1-8b-instant`
- if Groq generation fails or is unavailable, BastionBot falls back to a deterministic local grounded formatter

### Grounding pipeline

The backend answer flow works like this:

1. classify the query as `product_help`, `implementation_help`, `live_data`, or `mixed`
2. gather document matches from the knowledge registry
3. gather live platform context when the question refers to alerts, incidents, devices, dashboard KPIs, FL, or audit state
4. combine citations from docs, UI/API metadata, and live state
5. send the grounded payload to Groq
6. persist the conversation, sources, and user-memory updates

### Knowledge sources

The current knowledge registry indexes:

- `README.md`
- `SETUP_GUIDE.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `CODE_OF_CONDUCT.md`
- `CHANGELOG.md`
- `docs/README.md`
- `docs/LOCAL_TESTING.md`
- `docs/BACKEND_PRD.md`
- `docs/API_ENDPOINTS_IMPLEMENTATION_SPLIT.md`
- `docs/TODO.md`
- `docs/FAHEEM/FAHEEM_BACKEND_IMPLEMENTATION.md`
- `docs/FAHEEM/FAHEEM_BACKEND_TODO.md`
- `backend/README.md`
- `frontend/README.md`

It also adds curated metadata entries for:

- Dashboard
- Alerts
- Incidents
- FL Health
- Forensics
- Audit
- BastionBot
- audit verification API
- BastionBot API contract

### Live-state grounding

When relevant, BastionBot augments answers with live state from the in-process FastAPI store:

- alert lookups by alert ID
- incident lookups by incident ID
- device lookups by device ID
- dashboard KPI snapshot
- FL status snapshot
- audit verification and audit-log context through the same application state and indexed docs

## Backend implementation

### Router

Implemented in `app/routers/bastionbot.py`.

Routes:

- `GET /api/bastionbot/conversations`
- `GET /api/bastionbot/conversations/{conversation_id}`
- `POST /api/bastionbot/chat`

### Auth contract

Implemented via `app/auth/deps.py`.

Required for BastionBot routes:

- `Authorization: Bearer <token>`
- `X-BastionFed-UID: <firebase_uid>`

Behavior:

- anonymous requests return `401`
- dev mode requests return `403`
- signed-in requests missing `X-BastionFed-UID` return `400` with `BASTIONBOT_UID_REQUIRED`

### Request and response models

Implemented in `app/models/api.py` and `app/models/domain.py`.

Request:

```json
{
  "message": "How does audit verification work?",
  "conversationId": "optional-existing-id",
  "context": {
    "alertId": "optional",
    "incidentId": "optional"
  }
}
```

Response fields:

- `conversationId`
- `conversation`
- `message`
- `sources`
- `memoryUsed`

### Persistence

Implemented in `app/bastionbot/storage.py`.

SQLite tables:

- `bot_conversations`
- `bot_messages`
- `bot_user_memory`

Stored data:

- per-user conversation summaries
- ordered message history per conversation
- persisted source citations on bot messages
- last active conversation ID
- recent topics
- preferred answer style

Default database path:

```env
BASTIONBOT_DB_PATH=data/runtime/bastionbot.sqlite3
```

Same path convention as above: **`backend/data/runtime/`** relative to the `backend/` working directory (`backend/DATA_DIRECTORY.md`).

The store is initialized during FastAPI lifespan startup and can be redirected in tests with a temporary SQLite path.

### Conversation lifecycle

- when `conversationId` is omitted, chat creates a new conversation
- the first user message seeds the conversation title
- each user and bot message updates the conversation preview and timestamp
- the sidebar list is ordered by most recently updated conversation first

### Memory behavior

- prior user prompts in the same conversation are used as short-term history
- recent topics across conversations are stored as user memory
- `memoryUsed` is returned in the API response when history or stored topics contributed context
- the last active conversation ID is persisted for continuity

### Audit behavior

Every successful BastionBot chat appends an audit log entry describing that a BastionBot ask-mode response was generated.

## Frontend implementation

### Entry page

Implemented in `frontend/app/bastionbot/page.tsx`.

Behavior:

- loading state while auth is resolving
- dev mode and anonymous users see a sign-in-required card
- signed-in users see the BastionBot workspace

### Workspace

Implemented primarily in:

- `frontend/components/bastionbot/ChatInterface.tsx`
- `frontend/components/bastionbot/ConversationSidebar.tsx`
- `frontend/components/bastionbot/ChatInput.tsx`
- `frontend/components/bastionbot/MessageBubble.tsx`

Implemented UI features:

- conversation sidebar
- new conversation flow
- active conversation persistence in browser storage per UID
- history loading on bootstrap and conversation switch
- quick actions
- optimistic user-message append while a reply is in flight
- source citation rendering on assistant messages
- signed-in requests that attach bearer token and `X-BastionFed-UID`

### Removed legacy behavior

- direct browser Gemini usage is no longer part of BastionBot
- the frontend now uses the backend BastionBot API for chat and history

## Verification and testing

### Pytest coverage

The backend pytest suite now verifies:

- BastionBot OpenAPI paths exist
- signed-in access is required
- dev mode mode is blocked from BastionBot routes
- `X-BastionFed-UID` is required
- new conversations are created when `conversationId` is omitted
- message history order is correct
- conversation lists are user-scoped
- foreign-user history access returns `404`
- SQLite persistence survives application-state reset
- live-data questions return live citations
- documentation and product-help questions return grounded citations
- unknown questions return a safe fallback
- recent-topic memory is updated
- bot message history retains source citations
- updated conversations move to the top of the sidebar list
- memory and history survive store reconfiguration against the same SQLite file
- BastionBot chat appends an audit log entry
- the engine falls back to a local grounded formatter when Groq is unavailable

### Commands

Run the full unified backend suite:

```bash
cd backend
.venv/bin/python -m pytest -q
```

Run only BastionBot-focused tests:

```bash
cd backend
.venv/bin/python -m pytest tests/test_hunain_endpoints.py tests/test_bastionbot_verification.py tests/test_live_server.py -q
```

Run the live HTTP integration test:

```bash
cd backend
export LIVE_SERVER_URL=http://127.0.0.1:8000
.venv/bin/python -m pytest tests/test_live_server.py -q
```

### Manual verification checklist

- sign in with Google and open `/bastionbot`
- confirm the chat workspace loads for signed-in users
- open `/bastionbot` in dev mode mode and confirm the sign-up or sign-in message appears
- start a new conversation and confirm it appears in the sidebar
- send a follow-up message and confirm the same conversation remains active
- refresh the page and confirm the last active conversation reloads
- ask about:
  - audit verification
  - alerts workflow
  - incidents workflow
  - FL Health
  - a known alert ID or incident ID
- confirm source citations appear on assistant responses
- confirm a second signed-in user cannot access the first user’s conversations
- confirm BastionBot does not trigger quarantines, playbooks, or other mutations

## Files involved

Primary unified backend files:

- `backend/app/routers/bastionbot.py`
- `backend/app/bastionbot/engine.py`
- `backend/app/bastionbot/knowledge.py`
- `backend/app/bastionbot/storage.py`
- `backend/app/auth/deps.py`
- `backend/app/config.py`
- `backend/app/models/api.py`
- `backend/app/models/domain.py`
- `backend/app/main.py`

Primary frontend files:

- `frontend/app/bastionbot/page.tsx`
- `frontend/components/bastionbot/ChatInterface.tsx`
- `frontend/components/bastionbot/ConversationSidebar.tsx`
- `frontend/components/bastionbot/ChatInput.tsx`
- `frontend/components/bastionbot/MessageBubble.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/types.ts`

Primary unified backend test files:

- `backend/tests/conftest.py`
- `backend/tests/test_hunain_endpoints.py`
- `backend/tests/test_bastionbot_verification.py`
- `backend/tests/test_live_server.py`

Contributor-specific backend directories remain intact for standalone runs, but `backend/` is now the main unified runtime target.
