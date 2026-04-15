# ML drift semantics (unified API vs reference code)

This document reconciles **what the unified BastionFed API computes** for federated-learning drift with **older or alternate documentation** that may describe z-score feature-vector (FV) drift.

## Unified runtime (`GET /api/fl/drift`, `GET /api/fl/drift/clients`)

The production FastAPI service derives per-client drift from **tenant-scoped FL rounds and client rows** (in-memory snapshot or PostgreSQL), not from embedding or FV z-scores.

- **Method identifier:** `ROUND_ACCURACY_HEURISTIC` (also returned as `driftMethod` in JSON).
- **Computation (summary):** For each client, `driftScore` is a small positive number based on the difference between a **baseline round accuracy** (six rounds back when enough history exists, else the latest) and **latest round accuracy**, plus a fixed heuristic increment; clients in `DEGRADED` or `POISONING_SUSPECT` receive a larger increment.
- **Scope:** Responses are labeled `DEMO_RESEARCH` where applicable. This is **not** a substitute for real per-site telemetry from hospital nodes unless that pipeline is integrated and validated separately.

## Hunain reference implementation (optional, not the unified default)

The tree `backend/hunain_implementation/` includes `app/ml/drift.py`, which can compute **FV and image drift** using reference statistics and **mean |z-score|**-style semantics for feature vectors. That path is **not** wired as the default drift engine for the unified app under `backend/app/`.

Reviewers comparing **documentation** to **behavior** should:

1. Prefer **`driftMethod` and related fields** on the live API response, and this file, for the unified service.
2. Treat Hunain drift code as **reference / alternate stack** unless explicitly deployed instead of the unified backend.

## UI and reporting

Any UI or report that describes “z-score FV drift” for the unified deployment should be checked against the API’s `driftMethod` and `zScoreFvDriftNote` fields; if they still say z-score while `driftMethod` is `ROUND_ACCURACY_HEURISTIC`, the copy is stale relative to the implementation.
