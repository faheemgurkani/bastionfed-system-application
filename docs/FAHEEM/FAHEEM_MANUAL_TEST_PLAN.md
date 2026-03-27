Here’s a **short manual pass** you can follow with **Uvicorn on :8000** and **Next on :3000**, with **`NEXT_PUBLIC_API_URL=http://localhost:8000`** in `frontend/.env.local`.

---

### Before you click anything

1. **Backend:** `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` from `backend/faheem_implementation/`.  
2. **Frontend:** `npm run dev` from `frontend/`.  
3. Open DevTools → **Network**, filter by **Fetch/XHR** (and optionally **`events`** / **`fl-events`** for SSE).  
**Expect:** No failed calls to `localhost:8000` for flows below, except **audit logs** (see Audit).

---

### 1. Landing (`/`)

- Scroll hero, nav, sections.  
**Expect:** Static/marketing UI; no FastAPI required for first paint.  
- Use **Continue as guest** or **Sign in with Google** (from your header/auth UI).  
**Expect:** After guest/sign-in you can open app routes; unauthenticated users hitting gated routes get sent back to `/` (see `AuthGate`).

---

### 2. Dashboard (`/dashboard`)

**Expect:**

- **`GET /api/dashboard/kpis?guest=true`** (guest) or with **`Authorization: Bearer …`** (signed in).  
- KPI cards show **numbers**, not permanent **“—”** / error state.  
- If backend is down: error or fallback messaging tied to that fetch.

---

### 3. Alerts (`/alerts`)

**Expect:**

- **`GET /api/alerts?guest=true`** loads the table.  
- **`EventSource`** to **`/api/events?guest=true`** (or `?token=…` when signed in): status **200**, type **`text/event-stream`**; list should **gain new rows over time** (synthetic stream).  
- **Guest:** status / quarantine actions should **block** or prompt sign-in.  
- **Signed in:** **`PATCH /api/alerts/{id}`**, **`POST /api/devices/{deviceId}/quarantine`** succeed **200**; device may show isolated in UI.

---

### 4. FL Health (`/fl-health`)

**Expect:**

- **`GET /api/fl/status?guest=true`** — banner metrics load.  
- **`GET /api/fl/clients?guest=true`** — grid populated from API (not only silent mock fallback).  
- **`EventSource`** **`/api/fl-events?guest=true`** — live **`data:`** lines; grid values may **tick** (e.g. `participationPct`).  
- Open a client detail: **`GET /api/fl/clients/{id}`** — **200**.

---

### 5. Forensics (`/forensics`)

**Expect:**

- **`GET /api/forensics/samples?guest=true`** — sample list; selecting a row shows analysis from list payload (no separate sample-by-id call required for basic flow).

---

### 6. Incidents (`/incidents`)

**Expect:**

- **`GET /api/incidents?guest=true`** — Kanban populated (no empty board solely because list 404).  
- Open a card → **`GET /api/incidents/{id}?guest=true`** — detail refresh **200**.

---

### 7. Audit (`/audit`)

**Expect:**

- **Verify chain** → **`GET /api/audit/verify?guest=true`** — human-readable result (valid / tamper text).  
- **Audit table** → **`GET /api/audit/logs`** — **still not implemented** on the Faheem-only backend: expect **4xx** and table error/empty; that’s **expected** until that route exists on `:8000`.

---

### 8. BastionBot (`/bastionbot`) — optional

**Expect:** May use **client-side Gemini** and/or backend depending on implementation; failures here are often **API keys / network**, not your FastAPI smoke path. Treat as **out of core** Faheem API checklist unless you’re testing that feature specifically.

---

### Quick “green” checklist

| Step | Green signal |
|------|----------------|
| Landing | Guest or Google works |
| Dashboard | `kpis` **200**, numbers shown |
| Alerts | `alerts` **200**, `events` stream **200**, rows update |
| FL | `fl/status`, `fl/clients`, `fl-events` **200**, grid + patches |
| Forensics | `samples` **200** |
| Incidents | `incidents` list + detail **200** |
| Audit | `verify` **200**; **`logs` may fail** (known gap) |

That’s enough for a **straight-through manual run** from landing onward with both servers up.

---

### Documentation: UI Features & Dynamics (Alerts)

#### 1. The ATT&CK (Kill Chain) Section
When you open this tab, it maps the alert's specific tactic onto a visual cyber kill chain (consisting of *Initial Access*, *Execution*, *Persistence*, *Lateral Movement*, *Exfiltration*, and *Impact*).
It highlights the exact stage the threat is currently sitting at within your network. Additionally, it displays the specific MITRE ATT&CK technique ID and name that triggered the alert (for example, "T0886 - Remote Services"), giving you the exact methodology the attacker is attempting to use.

#### 2. The Actions Tab ("Mark In Review" / "False Positive")
When you click these buttons, you are actively performing a SOC (Security Operations Center) triaging workflow. Here is the dynamic sequence that happens under the hood:
1. **Authentication Check:** The UI first verifies you are a real signed-in user and not a guest (guests cannot modify alerts).
2. **The Network Call:** It fires an HTTP `PATCH` request to the backend (`/api/alerts/{alert_id}`) containing the new status (e.g., `IN_REVIEW` or `FALSE_POSITIVE`).
3. **Backend Update:** Your FastAPI backend receives this, updates the alert in its memory store, logs your action in the Audit Trail, and returns the updated alert.
4. **Instant UI Update:** The frontend context instantly catches this successful response and modifies the underlying table row to reflect the new status, allowing you to triage alerts extremely fast without ever having to refresh the page.

*Note: Updating an alert status does not solely affect the alerts list! Because the backend processes the change, this action cascades across the system. For instance, marking an active alert as "RESOLVED" or "FALSE_POSITIVE" will instantly decrease the "Active Threats" count on your Threat Map (Dashboard) and push a new persistent log line to your Audit Trails page.*

---

### Documentation: UI Features & Dynamics (Incidents)

#### 1. "Halt Playbook" Button
Currently, the **Halt Playbook** button is a static UI placeholder for this specific manual testing pass (if you click it, it doesn't currently fire a network request). 
In a fully wired SOC environment, it acts as an **Analyst Override**. When the system detects a critical incident, it might automatically start running a sequence of actions (like quarantining devices or blocking ports). If a human analyst reviews the situation and realizes the system is making a mistake or is about to block a critical hospital server, they would slam the "Halt Playbook" button to instantly freeze the automated response sequence mid-execution.

#### 2. Evidence Downloads
If you click on the Evidence tab, it lists a static mockup array of **Digital Forensic Artifacts** that a SOC analyst would need to investigate a compromised device. The available mock downloads are:
* **PCAP Dump:** Network packet captures (to see exactly what data was sent/received via the network).
* **System Log:** The operating system's activity logs leading up to the breach.
* **Memory Dump:** A massive file (1.4 GB) containing the live state of the device's RAM during the attack.
* **Malware Binary:** The actual suspected malicious file/virus that was found, packaged for safe download so researchers can reverse-engineer it.
