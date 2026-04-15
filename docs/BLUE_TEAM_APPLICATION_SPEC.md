# BastionFed — Application Specification for Blue Team Review

**Audience:** Cybersecurity blue team leads, SOC architects, and assessors judging _claims vs operational reality_ for a healthcare-flavored federated-learning security platform.

**Baseline snapshot:** `main` branch after the tenant-scoped data-plane migration, ingest/forensics lifecycle work, audit export, and FL honesty labeling updates.

> **Data plane verification (2026-04):** Supabase PostgreSQL now backs **tenant-scoped normalized tables** for operational entities plus BastionBot tables, Supabase Storage backs private `forensics` / `models` buckets, Upstash Redis backs tenant-scoped SSE, and Firebase Auth/Firestore remain the browser-side identity and profile mirror surfaces. Evidence and commands are recorded in [`DATA_PLANE_VERIFICATION.md`](./DATA_PLANE_VERIFICATION.md), and the concrete service-to-code mapping is in [`FIREBASE_DATA_PLANE_MAPPING.md`](./FIREBASE_DATA_PLANE_MAPPING.md). **Firebase JWT verification on the API is implemented** in the current backend and depends on `PyJWT[crypto]` being present in the runtime environment.

---

## Part A — What this document is and is not

### A.1 Purpose (written artifact)

This specification **consolidates** product intent, trust boundaries, and a **claims-vs-reality** matrix so a reviewer can **scope** an assessment and **structure** findings. It is written to support **critical evaluation** of whether implemented features and advertised behavior are **accurate** and **grounded** in what a real SOC, healthcare operator, or FL program would require.

### A.2 Limitations (cannot be satisfied by this file alone)

The following **cannot** be fully validated from static text. The reviewer must treat them as **mandatory follow-up** with independent evidence:

| Gap                             | Why text is insufficient                                                                    | Evidence the reviewer should obtain                                                                                        |
| ------------------------------- | ------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **Hands-on behavior**           | Runtime paths, error handling, and side effects differ from reading summaries.              | Run API service and UI; exercise OpenAPI-documented routes; capture requests/responses and logs.                           |
| **Complete surface area**       | Not every route, validation rule, and edge case is enumerated here.                         | Full router/handler inventory; automated or manual test results; dependency and config review.                             |
| **Forensics pipeline**          | Binary ingest, storage, scanning, and retention need procedural and technical proof.        | Trace upload → storage → scan/lifecycle → download/export; malware handling policy; isolation and legal review.            |
| **BastionBot / LLM path**       | Prompting, retrieval, and logging have security and privacy implications beyond this scope. | Review copilot engine, conversation storage, retrieval context, and any external model calls.                              |
| **Organizational requirements** | “Real life” includes **your** risk appetite, jurisdictions, and contracts.                  | Written RTO/RPO, compliance targets, incident classification scheme, acceptable use of guest/demo modes, retention policy. |
| **Threat model**                | Attack scenarios are not exhaustively derived here.                                         | STRIDE or equivalent; trust-boundary diagram; adversary assumptions; red-team or pentest results if available.             |
| **Legal / clinical**            | Healthcare claims may implicate IRB, clinical safety, or liability.                         | Legal and clinical stakeholders sign-off where applicable.                                                                 |

### A.3 What this document _does_ provide for the critic

- Stated **product intent** vs **implemented stack** across auth, persistence, ingest, forensics, and FL honesty.
- A **feature matrix** for systematic “implied vs actual” scoring.
- **Review checklists** and an **output template** so analysis can be presented consistently.
- Explicit flags for **known demo or research artifacts** such as dev/demo mode and synthetic per-client drift.
- Pointers to **[`FIREBASE_DATA_PLANE_MAPPING.md`](./FIREBASE_DATA_PLANE_MAPPING.md)** and **[`DATA_PLANE_VERIFICATION.md`](./DATA_PLANE_VERIFICATION.md)** for backing-service and evidence details.

---

## Part B — Stated product intent

- **Narrative:** Hospital-style environment with devices and criticality labels, SOC-style **alerts** and **incidents**, **MITRE**-style labeling, **federated learning** for malware detection, **drift monitoring**, **forensics** samples and RCA-style reports, **audit logging**, and an analyst copilot (**BastionBot**).
- **Client profile mirror:** Firestore **`users/{uid}`** remains a browser-side profile mirror. The server-side system of record is now tenant-scoped SQL (`users`, `tenants`, `memberships`, and domain tables), not Firestore and not the legacy `bf_bundle`.
- **Target deployment story (design intent):** Verified identity on API calls, durable relational storage for operational data, Redis-backed real-time streams, object storage for large binaries and model artifacts, and demo-only dev/read access when explicitly enabled.

**This specification** separates what the **UI and public API suggest** from what is **enforced and persisted** in the current implementation.

---

## Part C — High-level architecture (as implemented)

| Layer                                               | Technology                                                                                                   | Notes for assessors                                                                                                                                                                                                                                                                                                                                                                                |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Web client                                          | Next.js 16 (App Router)                                                                                      | Uses configured API base URL and Firebase client SDK for sign-in/profile mirroring.                                                                                                                                                                                                                                                                                                                |
| API service                                         | FastAPI                                                                                                      | Single process; HTTP API under `/api`. Startup loads ML weights and uses tenant-scoped stores when data-plane services are configured. `BASTIONFED_STRICT_DATA_PLANE=1` can require live Postgres + Redis + Storage readiness.                                                                                                                                                                     |
| Product / FL orchestration state                    | **Supabase PostgreSQL** normalized tables when `DATABASE_URL` / `SUPABASE_DATABASE_URL` is set and reachable | Operational entities live in tenant-scoped SQL tables (`users`, `tenants`, `memberships`, `alerts`, `incidents`, `devices`, `fl_*`, `model_registry`, `malware_samples`, `audit_log`, `ingest_*`, etc.). Demo/test can still run in-memory when DB is absent and strict mode is off. **Filled** for tenant-scoped product data; enterprise RLS and compliance narratives remain separate concerns. |
| Copilot memory                                      | **PostgreSQL `bot_*` tables** when the same DB connection succeeds; else **SQLite** in demo/test             | BastionBot history and memory are tenant-scoped by `(tenant_id, firebase_uid)`. **Filled** for persisted multi-tenant storage in the live Postgres path.                                                                                                                                                                                                                                           |
| Real-time SSE (`/api/events`, `/api/fl-events`)     | **Upstash Redis** when `REDIS_URL` / `UPSTASH_REDIS_URL` is set                                              | Tenant-scoped pub/sub channels (`bastionfed:tenant:{tenant_id}:...`) back SSE; in-memory fallback is demo/test only. **Filled** for product SSE transport.                                                                                                                                                                                                                                         |
| Large binaries (forensics samples, model artifacts) | **Supabase Storage** when `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` are set                                    | Private buckets `forensics`, `models`; object metadata and lifecycle state live in SQL; signed forensics download URLs are issued via the API. **Partially filled** because storage is implemented but handling policy is broader than the database.                                                                                                                                               |
| ML artifacts                                        | On-disk weight files and optional Storage-backed model objects                                               | Inference loads checkpoints at runtime; model activation updates persisted metadata but still switches the active model **in-process** on this server.                                                                                                                                                                                                                                             |
| Auth                                                | **Firebase ID tokens verified on the API**                                                                   | FastAPI verifies Firebase JWTs against signing keys, derives tenant context from memberships, and limits dev/demo mode to the dedicated demo tenant when `DEMO_MODE=1`. **Filled** for cryptographic token validation; least-privilege role design remains limited.                                                                                                                                   |
| Legacy runtime path                                 | Historical `bf_bundle` helper only                                                                           | `app/db/persistence.py` remains in the repo for reference but is **not** the active runtime path.                                                                                                                                                                                                                                                                                                  |

No further **directory tree** or **folder layout** is specified in this document; assessors should use their own code navigation and build/run procedures.

---

## Part D — Feature catalog: claims vs reality

Use this table to score each row: **Accurate / Partially accurate / Misleading / Not applicable** for real-world SOC or FL operations.

| Feature area                     | What the product narrative or UI implies           | Implementation reality (current)                                                                                                                                                                                                                                                                                                                                                                                                                            | Typical blue-team relevance                                                                                               |
| -------------------------------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **Authentication**               | Verified identity on protected calls               | Firebase ID tokens are cryptographically verified on the API, tenant context comes from memberships, and client-supplied UID headers are no longer trusted. **Filled / materially improved.** Dev/demo read mode still exists for the demo tenant when `DEMO_MODE=1`, and authorization is still coarse compared with full enterprise RBAC.                                                                                                                    | **High:** Much stronger than the earlier stub path, but still review least-privilege and demo-mode acceptability.         |
| **Alerts / incidents / devices** | Full operational CTI workflow                      | Tenant-scoped SQL tables replace the earlier shared snapshot model, and ingest APIs plus provenance fields (`sourceType`, `sourceRef`, `ingestedAt`, `isDemo`) support real event normalization. **Filled** for data modeling and API scope. Real connector deployment and operational telemetry coverage remain **partially external**.                                                                                                                    | Product data isolation is present; production detection coverage still depends on live SIEM/EDR/ticket connector rollout. |
| **Federated learning**           | Distributed hospitals, rounds, poisoning awareness | Tenant-scoped FL tables and endpoints exist, but there is still **no real federation control plane**, secure aggregation runtime, or hospital-node protocol in this service.                                                                                                                                                                                                                                                                                | FL remains **research/demo + local orchestration**, not production multi-site federation.                                 |
| **Model registry / Model Zoo**   | Many deployable models                             | Model metadata is persisted per tenant in SQL and exposed through the API. **Activation requires `owner` or `admin` membership** (not `member`/analyst-only roles), is audited, and still switches the active model **in-process** on this server.                                                                                                                                                                                                          | Review provenance of weights, who holds admin roles, and whether in-process switching is acceptable.                      |
| **Offline model metrics**        | Model quality metrics                              | HTTP metrics still evaluate packaged assets and a fixed eval shape rather than production runtime telemetry.                                                                                                                                                                                                                                                                                                                                                | Sanity check, not a substitute for live operational monitoring.                                                           |
| **Drift — global**               | Multimodal drift with thresholds                   | Global drift remains inference-fed and depends on reference statistics being present.                                                                                                                                                                                                                                                                                                                                                                       | Useful for local monitoring, but still tied to runtime traffic and packaged references.                                   |
| **Drift — per client**           | Per-site monitoring                                | Per-client drift is explicitly labeled **demo/research** in API responses and UI-adjacent flows. **Filled** for honesty labeling. It is still **not real client telemetry** unless replaced with a true federation/telemetry plane.                                                                                                                                                                                                                         | **Critical:** The main remaining requirement is to keep the non-operational nature explicit.                              |
| **Malware inference**            | Image + feature vector → classification            | Fusion-capable inference still exists, and drift side channels update on prediction. No edge agent or independent endpoint protection runtime is defined solely by this service.                                                                                                                                                                                                                                                                            | Input trust, model robustness, and handling of sensitive content still matter.                                            |
| **FV drift (consistency)**       | Documentation may describe z-score vs reference    | **Filled** for reconciliation: the unified API uses a **round-accuracy heuristic** (`ROUND_ACCURACY_HEURISTIC`), not z-score FV drift; semantics and the split from Hunain reference code are documented in [`ML_DRIFT_SEMANTICS.md`](./ML_DRIFT_SEMANTICS.md), and drift responses expose `driftMethod` / related fields. Optional z-score FV drift remains only in `hunain_implementation` unless that stack is deployed separately.                                                                                  | Use API fields + `ML_DRIFT_SEMANTICS.md` when comparing claims to behavior.                                               |
| **Forensics**                    | Upload, handling, and analysis lifecycle           | Samples upload to private Supabase Storage, SQL tracks immutable storage coordinates plus `scan_status`, `quarantine_status`, `retention_status`, custody JSON, scanner verdicts, and signed-download eligibility, and custody transitions are auditable. **Partially filled**: storage, metadata, lifecycle, and signed download are implemented; scanning, isolation environment, legal review, and retention operations still need independent evidence. | Stronger than simple blob storage, but still not the same as a full malware-handling program.                             |
| **Audit log**                    | Tamper-evident chain and verify/export endpoints   | Dedicated tenant-scoped `audit_log` table stores append-only chained entries, verify works against that table, and export endpoints exist. **Filled** for product-level audit persistence and export. WORM, legal hold, SIEM retention, and evidence-management operations remain external.                                                                                                                                                                 | Good product artifact; not itself an enterprise compliance attestation.                                                   |
| **Response actions**             | Quarantine, network block                          | Quarantine and block-style product actions are tracked in product state and audit, but they are not proof of firewall/EDR enforcement outside this service unless integrated with external systems.                                                                                                                                                                                                                                                         | IR playbooks must distinguish product workflow state from external enforcement.                                           |
| **Server-Sent Events**           | Live event streams                                 | SSE uses tenant-scoped Redis channels with verified token or dev-mode auth. Query-parameter tokens still exist for `EventSource` constraints. **Filled** for tenant isolation and auth gating, with ongoing token hygiene considerations.                                                                                                                                                                                                                 | Review TLS, proxy logs, and token-in-URL exposure.                                                                        |

---

## Part E — Authentication and authorization (detailed)

**Observed design in code:**

- **Read access:** Bearer tokens are verified against Firebase signing keys. Tenant context is derived from `memberships`, not from client-supplied UID headers.
- **Dev/demo:** Read-oriented dev/demo mode exists only for the dedicated demo tenant and only when `DEMO_MODE=1`.
- **Mutations:** Mutating routes require authenticated user context; dev/demo mode is rejected for those endpoints. **Tenant-admin-only** mutations include ingest source management (`owner`/`admin`) and FL model activation (`owner`/`admin`); other mutating routes still use authenticated membership without a finer matrix.
- **SSE:** `EventSource` flows may still carry the token in a query string, but the token is verified and the resolved tenant scopes the channel subscription.
- **Roles:** Membership-derived roles exist, but the current model is still limited compared with a full least-privilege enterprise authorization matrix.

**Production expectation (for comparison):** Verified tokens, least-privilege roles, explicit org IAM policy, and careful treatment of demo/dev mode.

**Reviewer questions:**

1. Is the current membership-based role model sufficient for the mutating operations exposed by this API?
2. Is demo/dev mode acceptable in any environment beyond controlled demonstrations?
3. Are token-in-query SSE flows adequately protected by TLS, proxy policy, and log hygiene?

---

## Part F — Federated learning and ML operations (mental stress test)

1. There is still **no real federation control plane** for remote hospital/site nodes.
2. Model activation affects **this server process** unless separate deployment automation exists elsewhere.
3. Client-labeled metrics and per-client drift remain **research/demo semantics** unless backed by real client telemetry.
4. Drift buffers still reflect **recent inference** activity; idle systems can show sparse or empty history.
5. Weight loading still assumes trust in artifact integrity unless a stronger provenance/signing workflow is added.

---

## Part G — FL health UI vs API (behavioral, not structural)

The FL health experience loads **active model** and **zoo list** from the API, and **live accuracy/samples** from metrics endpoints when available. The current implementation now labels per-client drift as **demo/research** rather than ordinary operational telemetry, and documents **drift method** explicitly (see [`ML_DRIFT_SEMANTICS.md`](./ML_DRIFT_SEMANTICS.md) and `driftMethod` on drift endpoints). The reviewer should still determine which source is **authoritative** for any external reporting and whether static copy remains aligned with live payloads.

---

## Part H — Data classification and residency

- **PHI:** Demo labels are synthetic; production needs data-flow mapping, agreements, encryption, and retention policy — **not** proven by this spec.
- **Malware:** Real samples imply isolation, legal constraints, scanning, and retention procedures. The product now tracks handling state, but organizational procedure still matters.

---

## Part I — Structured review procedure (for the critic)

Complete in order; record pass/fail/partial and **evidence** (log excerpt, screenshot, test name) for each.

### I.1 Scoping and intake

| Step | Action                                                                                            | Record |
| ---- | ------------------------------------------------------------------------------------------------- | ------ |
| 1    | Confirm review **objective** (demo integrity vs production readiness).                            | ☐      |
| 2    | Obtain **organizational** requirements: compliance frame, data classes, allowed deployment zones. | ☐      |
| 3    | Freeze **software version** (commit, build, config) under review.                                 | ☐      |

### I.2 Trust and identity

| Step | Action                                                                            | Record |
| ---- | --------------------------------------------------------------------------------- | ------ |
| 4    | Map **every** mutating HTTP method to required **auth mode** and membership role. | ☐      |
| 5    | Attempt access **without** valid identity where policy says it should fail.       | ☐      |
| 6    | Document **SSE** and any **token-in-URL** exposure paths.                         | ☐      |

### I.3 Integrity and logging

| Step | Action                                                                                                                                            | Record |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| 7    | Run **audit verify** across a session; restart the server; confirm tenant-scoped audit entries persist via SQL rather than legacy snapshot state. | ☐      |
| 8    | Assess **log content** for secrets, tokens, or sample data leakage.                                                                               | ☐      |

### I.4 ML and FL honesty

| Step | Action                                                                                                                                             | Record |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| 9    | Compare **UI claims** (accuracy, drift, client health) to **API payloads** and **known demo/research** endpoints.                                  | ☐      |
| 10   | Decide whether **federation**, **poisoning defense**, and **secure aggregation** are **in scope** or **explicitly out of scope** for this release. | ☐      |
| 11   | Review **weight provenance** and **who can change** active model.                                                                                  | ☐      |

### I.5 Forensics and copilot (deep dive)

| Step | Action                                                                                                                       | Record |
| ---- | ---------------------------------------------------------------------------------------------------------------------------- | ------ |
| 12   | Trace **forensics** upload, lifecycle transitions, storage, and signed download; confirm isolation and retention procedures. | ☐      |
| 13   | Review **BastionBot** data retention, retrieval sources, and any third-party model usage.                                    | ☐      |

### I.6 Residual risk

| Step | Action                                                                                                                                                                 | Record |
| ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| 14   | Produce **threat scenarios** (credential theft, model swap, poisoned weights, dev-mode abuse, connector secret leakage) and map to **compensating controls** or **gaps**. | ☐      |

---

## Part J — Deliverable template (for the critic’s written assessment)

The reviewer should produce a short report using the following skeleton.

**1. Executive summary**  
One paragraph: fit for purpose (demo / pilot / production), top 3 risks, top 3 strengths.

**2. Verdict table**  
For each **Part D** row: **Aligned / Partially aligned / Not aligned** with real-world SOC or FL expectations, **rationale**, **severity** (Critical / High / Medium / Low / Informational).

**3. Evidence appendix**  
Pointers to test runs, log snippets, OpenAPI excerpts, or meeting notes — **not** replaceable by this markdown file.

**4. Dependencies on the organization**  
List **open questions** that only the product owner can answer (risk appetite, HIPAA scope, clinical use, internet exposure).

**5. Recommendations**  
Prioritized: **must-fix** before any production-adjacent deploy; **should-fix** for pilot; **nice-to-have**.

---

## Part K — Suggested deep-dive checklist (condensed)

- [ ] Trust boundaries: browser ↔ API ↔ ML ↔ Storage/Redis ↔ optional external connectors — mark trust and threat per hop.
- [ ] Authorization matrix: membership roles vs mutating operations vs org IAM (note: **ingest admin** and **FL model activate** require `owner` or `admin`).
- [ ] Acceptability of audit chain durability: tenant-scoped `audit_log` + export vs requirement for enterprise WORM / SIEM / legal hold.
- [ ] Explicit statement that **synthetic per-client drift** is non-operational unless replaced.
- [ ] Alignment of **static** UI metrics with **API** metrics and documented eval set.
- [ ] Source of **alerts** in any real deployment (ingest path and deployed connectors), if this UI were fronting a SOC.

---

## Part L — Hardening targets (when moving beyond demo)

1. Replace stub authentication with **verified** tokens from the chosen identity provider.
   - **Status:** _Filled_ — Firebase JWT verification is implemented on the API. Runtime still depends on `PyJWT[crypto]` being installed in the deployed environment, and authorization depth should still be reviewed.
2. Persist operational entities and audit trail in a **durable**, **backed-up** store with access control.
   - **Status:** _Filled / partially external_ — tenant-scoped normalized SQL tables store operational entities, BastionBot persists in `bot_*`, Supabase Storage holds large binaries, and `audit_log` provides verify/export product artifacts. Backups, IAM, RTO/RPO, WORM, and legal hold remain **organizational** responsibilities.
3. Label or remove **synthetic** drift data from APIs consumed by operators.
   - **Status:** _Filled_ — per-client drift is labeled **demo/research** in current API behavior and should remain so unless replaced with real telemetry.
4. Reconcile **FV drift** mathematics in code with the **documented** statistical intent (z-score vs raw magnitude).
   - **Status:** _Filled_ — unified runtime drift is documented as **round-accuracy heuristic** with API-visible `driftMethod` and [`ML_DRIFT_SEMANTICS.md`](./ML_DRIFT_SEMANTICS.md); z-score FV drift is scoped to the optional Hunain reference tree unless deployed separately.

### L.1 Database / artifact closure checklist vs this spec

| Spec location             | Topic                                   | Required DB / storage setup? | Closure                                                                                                                                                                   |
| ------------------------- | --------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Part C                    | Durable product + copilot state         | Yes                          | **Filled** — normalized Postgres tables + `bot_*` when configured.                                                                                                        |
| Part C                    | SSE bus                                 | Redis                        | **Filled** — Upstash with tenant-scoped channels when configured.                                                                                                         |
| Part C                    | Object storage for binaries             | Supabase Storage             | **Filled** — private buckets + SQL-linked metadata + signed download path when configured.                                                                                |
| Part D                    | Audit durability on restart             | SQL + audit table            | **Filled** for product durability via `audit_log`; **Partial** vs enterprise WORM/SIEM expectations.                                                                      |
| Part D                    | Forensics binary handling               | Storage + SQL metadata       | **Partially filled** — upload, lifecycle metadata, signed download, and audit custody are implemented; scanning / legal / isolation still require independent validation. |
| Part E / L.1              | Cryptographic identity on API           | No (auth code)               | **Filled** — verified Firebase tokens on FastAPI.                                                                                                                         |
| Part D / Part L           | Ingest-ready operational data model     | SQL + HTTP API               | **Filled** for tenant-scoped schema and `/api/ingest/*`; **Partial** for real connector deployment and monitoring.                                                        |
| Mapping doc / PRD wording | “Every domain in normalized SQL tables” | DB provisioned               | **Filled** — current runtime uses normalized tenant-scoped SQL tables.                                                                                                    |
| Mapping doc               | “Storage via supabase-py”               | N/A                          | **N/A** — code uses `httpx`; docs aligned.                                                                                                                                |
| Mapping doc               | “Admin SDK verify on API”               | N/A                          | **Filled in effect** — the backend verifies Firebase JWTs cryptographically; implementation does not depend on the Firebase Admin SDK specifically.                       |

---

_This specification supports review and structuring of analysis; it is not a compliance attestation and does not replace independent verification, testing, or organizational risk acceptance._
