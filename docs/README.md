# BastionFed — Documentation index

Start here after [SETUP_GUIDE.md](../SETUP_GUIDE.md).

## Governance

| Document | Purpose |
|----------|---------|
| [../LICENSE](../LICENSE) | MIT license |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Contribution workflow |
| [../SECURITY.md](../SECURITY.md) | Security policy |
| [../CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md) | Code of conduct |
| [../CHANGELOG.md](../CHANGELOG.md) | Changelog |

## Getting started

| Document | Purpose |
|----------|---------|
| [SETUP_GUIDE.md](../SETUP_GUIDE.md) | Clone, env vars, run frontend + unified backend |
| [LOCAL_TESTING.md](./LOCAL_TESTING.md) | Pytest, manual smoke checks, live-server tests |
| [backend/README.md](../backend/README.md) | Unified FastAPI: env, Vercel notes, ingest |
| [backend/DATA_DIRECTORY.md](../backend/DATA_DIRECTORY.md) | Local `backend/data/` tree (gitignored) |

## Product & API

| Document | Purpose |
|----------|---------|
| [BACKEND_PRD.md](./BACKEND_PRD.md) | Full HTTP API contract (36 endpoints) |
| [API_ENDPOINTS_IMPLEMENTATION_SPLIT.md](./API_ENDPOINTS_IMPLEMENTATION_SPLIT.md) | Original Faheem / Hunain / Hammad route split |
| [BLUE_TEAM_APPLICATION_SPEC.md](./BLUE_TEAM_APPLICATION_SPEC.md) | Claims vs operational reality for assessors |
| [BASTIONBOT_ASK_MODE.md](./BASTIONBOT_ASK_MODE.md) | BastionBot design and behavior |
| [TODO.md](./TODO.md) | Active team backlog |

## Data plane & deployment

| Document | Purpose |
|----------|---------|
| [FIREBASE_DATA_PLANE_MAPPING.md](./FIREBASE_DATA_PLANE_MAPPING.md) | Firebase + Supabase + Upstash provisioning |
| [DATA_PLANE_VERIFICATION.md](./DATA_PLANE_VERIFICATION.md) | Verification commands and findings log |
| [DEPLOYMENT_HARDENING_CHECKLIST.md](./DEPLOYMENT_HARDENING_CHECKLIST.md) | Production hardening checklist |
| [UNIFIED_BACKEND_CONFLICTS.md](./UNIFIED_BACKEND_CONFLICTS.md) | How contributor backends were merged |

## Operations runbooks

| Document | Purpose |
|----------|---------|
| [CONNECTOR_ONBOARDING_RUNBOOK.md](./CONNECTOR_ONBOARDING_RUNBOOK.md) | Ingest source setup |
| [FORENSICS_HANDLING_SOP.md](./FORENSICS_HANDLING_SOP.md) | Malware sample handling |
| [AUDIT_EXPORT_AND_EVIDENCE.md](./AUDIT_EXPORT_AND_EVIDENCE.md) | Audit chain export |
| [ML_DRIFT_SEMANTICS.md](./ML_DRIFT_SEMANTICS.md) | Drift monitoring semantics |

## Contributor notes (historical)

The unified backend at `backend/` is the **default entrypoint**. Per-contributor folders under `backend/*_implementation/` remain for isolated testing.

| Member | Implementation | TODO |
|--------|----------------|------|
| Faheem | [FAHEEM/FAHEEM_BACKEND_IMPLEMENTATION.md](./FAHEEM/FAHEEM_BACKEND_IMPLEMENTATION.md) | [FAHEEM/FAHEEM_BACKEND_TODO.md](./FAHEEM/FAHEEM_BACKEND_TODO.md) |
| Hunain | [HUNAIN/HUNAIN_BACKEND_IMPLEMENTATION.md](./HUNAIN/HUNAIN_BACKEND_IMPLEMENTATION.md) | [HUNAIN/HUNAIN_BACKEND_TODO.md](./HUNAIN/HUNAIN_BACKEND_TODO.md) |
| Hammad | [HAMMAD/HAMMAD_BACKEND_IMPLEMENTATION.md](./HAMMAD/HAMMAD_BACKEND_IMPLEMENTATION.md) | [HAMMAD/HAMMAD_BACKEND_TODO.md](./HAMMAD/HAMMAD_BACKEND_TODO.md) |
